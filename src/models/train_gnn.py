"""
ThemeSync — GNN training on CGL-Dataset (v2)
=============================================
Trains ThemeSyncGNN (Chapter 3, Formulas 3.6-3.8) to refine a naive
starting arrangement into the element positions designers actually used in
the CGL-Dataset.

Why v2 (notes §3.22): v1 was trained with each layout's *true* positions as
input and a loss of only "centred, in bounds, no overlap". At inference every
node started at (0, 0) — inputs it never saw in training — and nothing had
taught it vertical order or spacing, so its y-predictions were degenerate
(the source of the certificates' ~200 px gap under the logo). v2 fixes both:

  - Input: the same naive stack at training and inference time
    (graph_builder.naive_stack): elements centred and stacked in reading
    order, so position features and edge features (dx, dy, IoU, alignment)
    are informative and identically distributed in both.
  - Target: the layout's real CGL positions (supervised), plus the fitness
    function's collision and in-bounds terms (Formula 3.11) as regularisers.
  - Elements: CGL logos and text only (GNN_CGL_CATEGORIES) — what
    certificates and event IDs contain.

Usage:
  python src/models/train_gnn.py                      # writes themesync_gnn_v2.pth
  python src/models/train_gnn.py --relation_weight 0 --out themesync_gnn_v2_posonly.pth

Held-out results (seeded 5% of CGL, 2,900 layouts; results/gnn_v2/):
  model                    position MAE   gap MAE   order kept
  naive stack (baseline)        0.175      0.077        —
  v2, positions only            0.118      0.100      99.8%
  v2, positions + relations     0.121      0.074      99.9%   <- themesync_gnn_v2.pth
"""

import argparse
import json
import os
import sys

import datasets as ds
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch_geometric.loader import DataLoader
from tqdm import tqdm

from gnn_model import ThemeSyncGNN
from graph_builder import (GNN_CGL_CATEGORIES, LayoutGraphBuilder, distorted_structure_start,
                           naive_stack)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'solvers')))
from optimization_engine import HeuristicEvaluator

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DifferentiableHeuristicLoss(nn.Module):
    """
    Differentiable analogue of HeuristicEvaluator's collision and in-bounds
    terms (Formula 3.11), with the weights read from HeuristicEvaluator so
    training can't optimise a different objective than candidates are ranked
    on. Coordinates are fractions of each layout's own canvas (unit square).

    The alignment term (distance of each centre from the canvas midline) is
    no longer used: real CGL layouts are often deliberately off-centre, and
    the supervised target now carries alignment.
    """
    def __init__(self):
        super().__init__()
        _ref = HeuristicEvaluator()
        self.alpha = _ref.alpha  # P_collision weight
        self.delta = _ref.delta  # P_legibility weight (in-bounds here)

    def forward(self, predicted, batch):
        x, y = predicted[:, 0], predicted[:, 1]
        w, h = batch.x[:, 2], batch.x[:, 3]
        p_bounds = torch.mean(torch.relu(-x) + torch.relu(x + w - 1.0) +
                              torch.relu(-y) + torch.relu(y + h - 1.0))
        p_collision = self._pairwise_collision(x, y, w, h, batch.edge_index, batch.num_graphs)
        return (self.alpha * p_collision) + (self.delta * p_bounds)

    @staticmethod
    def _pairwise_collision(x, y, w, h, edge_index, num_graphs):
        """Overlap area summed over each layout's own (fully connected) edges."""
        if edge_index.numel() == 0:
            return x.new_zeros(())
        src, dst = edge_index[0], edge_index[1]
        inter_w = torch.clamp(torch.min(x[src] + w[src], x[dst] + w[dst]) - torch.max(x[src], x[dst]), min=0.0)
        inter_h = torch.clamp(torch.min(y[src] + h[src], y[dst] + h[dst]) - torch.max(y[src], y[dst]), min=0.0)
        return (inter_w * inter_h).sum() / 2.0 / max(num_graphs, 1)


class LayoutRefinementLoss(nn.Module):
    """
    Smooth-L1 distance to the real CGL positions, plus a relational term on
    the offsets between consecutive elements (how far apart, and how
    shifted, each element sits from the one above it — the spacing and
    alignment structure a stacked certificate or ID depends on), plus the
    weighted fitness terms.
    """
    def __init__(self, heuristic_weight: float = 0.1, relation_weight: float = 1.0):
        super().__init__()
        self.heuristic = DifferentiableHeuristicLoss()
        self.heuristic_weight = heuristic_weight
        self.relation_weight = relation_weight

    def forward(self, predicted, batch):
        pos = predicted[:, :2]
        position = F.smooth_l1_loss(pos, batch.target, beta=0.02)
        loss = position + self.heuristic_weight * self.heuristic(predicted, batch)
        if self.relation_weight:
            same = batch.batch[1:] == batch.batch[:-1]   # consecutive pairs, same layout
            if same.any():
                pred_delta = (pos[1:] - pos[:-1])[same]
                real_delta = (batch.target[1:] - batch.target[:-1])[same]
                loss = loss + self.relation_weight * F.smooth_l1_loss(pred_delta, real_delta, beta=0.02)
        return loss


def cgl_graph(builder: LayoutGraphBuilder, layout: dict, start: str = "naive", rng=None):
    """
    One CGL layout as a training graph: logos and text in reading order,
    with their real normalised top-left positions as the target. The input
    positions are the naive stack (`start="naive"`, the no-master case) or
    the layout's own structure as a master mapping would deliver it
    (`start="structure"`: distorted_structure_start, notes §3.26).
    """
    W, H = float(layout["width"]), float(layout["height"])
    nodes = [n for n in layout["extracted_nodes"]
             if n["semantic_category"]["name"] in GNN_CGL_CATEGORIES
             and n["bbox"][2] > 0 and n["bbox"][3] > 0]
    if len(nodes) < 2:
        return None
    nodes.sort(key=lambda n: (n["bbox"][1] + n["bbox"][3] / 2.0, n["bbox"][0]))
    sizes = [(n["bbox"][2] / W, n["bbox"][3] / H) for n in nodes]
    if start == "structure":
        starts = distorted_structure_start(sizes, [(n["bbox"][0] / W, n["bbox"][1] / H) for n in nodes], rng)
    else:
        starts = naive_stack(sizes)
    graph = builder.build_graph({
        "extracted_nodes": [{"bbox": [sx * W, sy * H, n["bbox"][2], n["bbox"][3]]}
                            for n, (sx, sy) in zip(nodes, starts)],
        "extracted_color_centroids": layout["extracted_color_centroids"],
        "extracted_saliency_weight": layout["extracted_saliency_weight"],
        "canvas_w": W, "canvas_h": H,
    })
    graph.target = torch.tensor([[n["bbox"][0] / W, n["bbox"][1] / H] for n in nodes],
                                dtype=torch.float32)
    return graph


def build_graphs(split, starts=("naive",), seed: int = 2026) -> list:
    """Per usable layout, one graph per requested start kind (same order),
    so a split by layout keeps a layout's variants together."""
    builder = LayoutGraphBuilder()
    rng = np.random.default_rng(seed)
    layouts = []
    for layout in tqdm(split.remove_columns(["image"]), desc="graphs", leave=False):
        variants = [cgl_graph(builder, layout, start=s, rng=rng) for s in starts]
        if variants[0] is not None:
            layouts.append(variants)
    return layouts


@torch.no_grad()
def evaluate(model, graphs, device) -> dict:
    """
    Held-out metrics (5% of CGL train, never trained on), each also computed
    for the naive stack itself (what
    the no-GNN baseline starts from) so the GNN's contribution is explicit:
      mae_xy      mean |position - real CGL position|, fraction of canvas
      mae_gap     mean |gap between consecutive elements - real gap|
      order_kept  share of consecutive pairs kept in real top-to-bottom order
      overlap     mean pairwise overlap area per layout (fraction of canvas)
    """
    model.eval()
    sums = {k: 0.0 for k in ("mae_xy", "mae_gap", "order_kept", "overlap",
                             "naive_mae_xy", "naive_mae_gap", "naive_overlap")}
    counts = {"nodes": 0, "pairs": 0, "graphs": 0}
    for batch in DataLoader(graphs, batch_size=1024):
        batch = batch.to(device)
        pred = model(batch)[:, :2]
        naive = batch.x[:, :2]
        target = batch.target
        h = batch.x[:, 3]
        for name, pos in (("", pred), ("naive_", naive)):
            sums[name + "mae_xy"] += (pos - target).abs().mean(dim=1).sum().item()
        # consecutive pairs within the same graph (nodes are in reading order)
        same = batch.batch[1:] == batch.batch[:-1]
        real_gap = target[1:, 1] - (target[:-1, 1] + h[:-1])
        for name, pos in (("", pred), ("naive_", naive)):
            gap = pos[1:, 1] - (pos[:-1, 1] + h[:-1])
            sums[name + "mae_gap"] += (gap - real_gap).abs()[same].sum().item()
        sums["order_kept"] += (pred[1:, 1] >= pred[:-1, 1])[same].float().sum().item()
        for name, pos in (("", pred), ("naive_", naive)):
            sums[name + "overlap"] += DifferentiableHeuristicLoss._pairwise_collision(
                pos[:, 0], pos[:, 1], batch.x[:, 2], batch.x[:, 3], batch.edge_index, 1).item()
        counts["nodes"] += pred.shape[0]
        counts["pairs"] += int(same.sum().item())
        counts["graphs"] += batch.num_graphs
    return {
        "mae_xy": sums["mae_xy"] / counts["nodes"],
        "naive_mae_xy": sums["naive_mae_xy"] / counts["nodes"],
        "mae_gap": sums["mae_gap"] / counts["pairs"],
        "naive_mae_gap": sums["naive_mae_gap"] / counts["pairs"],
        "order_kept": sums["order_kept"] / counts["pairs"],
        "overlap": sums["overlap"] / counts["graphs"],
        "naive_overlap": sums["naive_overlap"] / counts["graphs"],
        "layouts": counts["graphs"],
    }


def execute_training(epochs: int, out_path: str, batch_size: int, lr: float,
                     heuristic_weight: float, relation_weight: float, starts: tuple = ("naive",)) -> None:
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device} | starts: {starts}")
    dataset = ds.load_from_disk(os.path.join(_ROOT, "data", "processed", "cgl_tensor_dataset"))
    # CGL's own "test" split carries no layout annotations (placeholder
    # boxes only: it is meant for generation), so a seeded 5% of the
    # annotated train layouts is held out for validation instead — split by
    # layout, so no layout's variants land on both sides.
    layouts = build_graphs(dataset["train"], starts)
    order = torch.randperm(len(layouts), generator=torch.Generator().manual_seed(2026)).tolist()
    n_val = len(layouts) // 20
    held = [layouts[i] for i in order[:n_val]]
    train_graphs = [g for i in order[n_val:] for g in layouts[i]]
    test_sets = {kind: [variants[k] for variants in held] for k, kind in enumerate(starts)}
    print(f"Layouts: {len(layouts) - n_val} train ({len(train_graphs)} graphs), {n_val} held out "
          f"(logos + text, ≥2 elements)")

    torch.manual_seed(2026)
    model = ThemeSyncGNN(num_layers=3, node_dim=8, edge_dim=4, hidden_dim=64).to(device)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = LayoutRefinementLoss(heuristic_weight=heuristic_weight,
                                     relation_weight=relation_weight).to(device)
    loader = DataLoader(train_graphs, batch_size=batch_size, shuffle=True)

    best, history = None, []
    for epoch in range(1, epochs + 1):
        model.train()
        total = 0.0
        for batch in loader:
            batch = batch.to(device)
            optimizer.zero_grad()
            loss = criterion(model(batch), batch)
            loss.backward()
            optimizer.step()
            total += loss.item()
        scheduler.step()
        if epoch % 5 == 0 or epoch == epochs:
            metrics = {kind: evaluate(model, graphs, device) for kind, graphs in test_sets.items()}
            entry = {"epoch": epoch, "train_loss": total / len(loader), "heldout": metrics}
            history.append(entry)
            line = "  ".join(f"[{kind}] MAE {m['mae_xy']:.4f} (start {m['naive_mae_xy']:.4f}) "
                             f"gap {m['mae_gap']:.4f} (start {m['naive_mae_gap']:.4f}) order {m['order_kept']:.3f}"
                             for kind, m in metrics.items())
            print(f"epoch {epoch:>3}  loss {entry['train_loss']:.4f}  {line}", flush=True)
            score = sum(m["mae_xy"] + m["mae_gap"] for m in metrics.values())
            if best is None or score < best["score"]:
                best = dict(entry, score=score)
                torch.save(model.state_dict(), out_path)

    report_dir = os.path.join(_ROOT, "results", "gnn_v2")
    os.makedirs(report_dir, exist_ok=True)
    report = os.path.join(report_dir, os.path.splitext(os.path.basename(out_path))[0] + "_training.json")
    with open(report, "w") as f:
        json.dump({"best": best, "history": history, "epochs": epochs, "batch_size": batch_size,
                   "lr": lr, "heuristic_weight": heuristic_weight, "relation_weight": relation_weight,
                   "starts": list(starts), "train_graphs": len(train_graphs), "heldout_layouts": n_val,
                   "heldout": "seeded 5% of CGL train layouts (CGL test has no annotations); "
                              "'naive_*' metrics are the model's input start itself"}, f, indent=2)
    print(f"\nBest (epoch {best['epoch']}) saved to {out_path}; metrics in {report}")


def main():
    parser = argparse.ArgumentParser(description="Train ThemeSyncGNN on CGL-Dataset")
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--batch_size", type=int, default=512)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--heuristic_weight", type=float, default=0.1)
    parser.add_argument("--relation_weight", type=float, default=1.0,
                        help="weight of the consecutive-offset (spacing/alignment) term; 0 disables")
    parser.add_argument("--starts", default="naive,structure",
                        help="input starts to train on: naive (no master), structure (a master's "
                             "mapped composition), or both (default, the v3 model)")
    parser.add_argument("--out", default=os.path.join(_ROOT, "themesync_gnn_v3.pth"))
    args = parser.parse_args()
    execute_training(args.epochs, args.out, args.batch_size, args.lr, args.heuristic_weight,
                     args.relation_weight, tuple(s.strip() for s in args.starts.split(",") if s.strip()))


if __name__ == "__main__":
    main()
