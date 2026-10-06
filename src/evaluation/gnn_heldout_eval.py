"""
ThemeSync — GNN held-out evaluation (v1, v2, v3)
=================================================
Scores each GNN checkpoint the way the pipeline uses it, on the same
held-out CGL layouts (the seeded 5% of CGL train that v2 and v3 never
trained on — CGL's own test split has no annotations), against the real
positions:

  v1 as deployed     every node starts at (0, 0) (what Stage 1 handed it
                     before notes §3.22), themesync_gnn_v1.pth
  naive stack        no model: the no-master starting arrangement (and the
                     no-GNN baseline's arrangement)
  v2 (positions)     naive stack in, trained on positions only (ablation)
  v2                 naive stack in, positions + consecutive offsets
  v3, naive input    themesync_gnn_v3.pth (the pipeline default) with no
                     master structure to start from
  structure start    no model: the layout's own structure as a master
                     mapping delivers it — anchors moved, scaled and
                     jittered, half the elements unmapped
                     (graph_builder.distorted_structure_start); the
                     "mapping only" ablation (notes §3.26)
  v2, structure in   v2 given that start (it was never trained on one)
  v3, structure in   v3 given that start — how the pipeline runs it on a
                     master layout

Metrics (fractions of the canvas): position MAE, gap MAE between
consecutive elements, share of consecutive pairs kept in reading order, and
mean pairwise overlap.

A second table asks what the pipeline needs on a real master, where the
mapped anchors ARE the positions to keep: each held-out layout's elements
anchored at their real centres, up to half left unmapped (interpolated),
and the vertical-centre error split into anchored and unmapped elements —
for the start itself (mapping only), the raw GNN, and the GNN registered to
the anchors (graph_builder.register_to_anchors, what Stage 2 does).

Writes results/gnn_heldout_eval.json.

Usage:
  python src/evaluation/gnn_heldout_eval.py
"""

import json
import os
import sys

_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_EVAL_DIR)
_ROOT = os.path.dirname(_SRC)
for _sub in ("models", "solvers"):
    _p = os.path.join(_SRC, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import datasets as ds  # noqa: E402
import torch  # noqa: E402

from gnn_model import ThemeSyncGNN  # noqa: E402
import numpy as np  # noqa: E402

from graph_builder import GNN_CGL_CATEGORIES, LayoutGraphBuilder, register_to_anchors, structure_start  # noqa: E402
from train_gnn import build_graphs, evaluate  # noqa: E402

CHECKPOINTS = {
    "v1": os.path.join(_ROOT, "themesync_gnn_v1.pth"),
    "v2_posonly": os.path.join(_ROOT, "themesync_gnn_v2_posonly.pth"),
    "v2": os.path.join(_ROOT, "themesync_gnn_v2.pth"),
    "v3": os.path.join(_ROOT, "themesync_gnn_v3.pth"),
}
METRICS = ("mae_xy", "mae_gap", "order_kept", "overlap")


def zero_start_graph(builder: LayoutGraphBuilder, layout: dict):
    """The same layout as cgl_graph() builds, but with every element at
    (0, 0) — v1's input at inference time."""
    W, H = float(layout["width"]), float(layout["height"])
    nodes = [n for n in layout["extracted_nodes"]
             if n["semantic_category"]["name"] in GNN_CGL_CATEGORIES
             and n["bbox"][2] > 0 and n["bbox"][3] > 0]
    if len(nodes) < 2:
        return None
    nodes.sort(key=lambda n: (n["bbox"][1] + n["bbox"][3] / 2.0, n["bbox"][0]))
    graph = builder.build_graph({
        "extracted_nodes": [{"bbox": [0.0, 0.0, n["bbox"][2], n["bbox"][3]]} for n in nodes],
        "extracted_color_centroids": layout["extracted_color_centroids"],
        "extracted_saliency_weight": layout["extracted_saliency_weight"],
        "canvas_w": W, "canvas_h": H,
    })
    graph.target = torch.tensor([[n["bbox"][0] / W, n["bbox"][1] / H] for n in nodes],
                                dtype=torch.float32)
    return graph


def exact_anchor_cases(builder: LayoutGraphBuilder, layouts: list, seed: int = 7) -> list:
    """Per layout: the graph started from EXACT anchors (real centres, up to
    half the elements unmapped and interpolated), with what scoring needs."""
    rng = np.random.default_rng(seed)
    cases = []
    for layout in layouts:
        W, H = float(layout["width"]), float(layout["height"])
        nodes = sorted((n for n in layout["extracted_nodes"]
                        if n["semantic_category"]["name"] in GNN_CGL_CATEGORIES
                        and n["bbox"][2] > 0 and n["bbox"][3] > 0),
                       key=lambda n: (n["bbox"][1] + n["bbox"][3] / 2.0, n["bbox"][0]))
        k = len(nodes)
        sizes = [(n["bbox"][2] / W, n["bbox"][3] / H) for n in nodes]
        real = [(n["bbox"][0] / W, n["bbox"][1] / H) for n in nodes]
        unmapped = set(rng.choice(k, size=min(int(rng.integers(0, max(1, k // 2) + 1)), k - 1),
                                  replace=False).tolist())
        anchors = {i: (real[i][0] + sizes[i][0] / 2.0, real[i][1] + sizes[i][1] / 2.0)
                   for i in range(k) if i not in unmapped}
        start = structure_start(sizes, anchors)
        graph = builder.build_graph({
            "extracted_nodes": [{"bbox": [sx * W, sy * H, n["bbox"][2], n["bbox"][3]]}
                                for n, (sx, sy) in zip(nodes, start)],
            "extracted_color_centroids": layout["extracted_color_centroids"],
            "extracted_saliency_weight": layout["extracted_saliency_weight"],
            "canvas_w": W, "canvas_h": H,
        })
        cases.append({"graph": graph, "h": [h for _, h in sizes], "real": [y for _, y in real],
                      "start": [y for _, y in start], "anchors": anchors, "unmapped": unmapped})
    return cases


@torch.no_grad()
def exact_anchor_errors(model, cases: list, device) -> dict:
    """Mean |vertical centre − real| for anchored and unmapped elements."""
    errs = {name: {"anchored": [], "unmapped": []}
            for name in ("start (mapping only)", "GNN raw", "GNN registered")}
    for c in cases:
        pred = model(c["graph"].to(device))[:, 1].cpu().tolist()
        h = c["h"]
        real = [y + hh / 2.0 for y, hh in zip(c["real"], h)]
        raw = [y + hh / 2.0 for y, hh in zip(pred, h)]
        variants = {"start (mapping only)": [y + hh / 2.0 for y, hh in zip(c["start"], h)],
                    "GNN raw": raw, "GNN registered": register_to_anchors(raw, c["anchors"])}
        for name, cys in variants.items():
            for i, (cy, r) in enumerate(zip(cys, real)):
                errs[name]["unmapped" if i in c["unmapped"] else "anchored"].append(abs(cy - r))
    return {name: {"anchored": float(np.mean(e["anchored"])), "unmapped": float(np.mean(e["unmapped"])),
                   "all": float(np.mean(e["anchored"] + e["unmapped"]))} for name, e in errs.items()}


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dataset = ds.load_from_disk(os.path.join(_ROOT, "data", "processed", "cgl_tensor_dataset"))
    # Exactly train_gnn.py's graphs (same filter, same seeded structure
    # distortions) and its held-out split by layout.
    layouts = build_graphs(dataset["train"], ("naive", "structure"))
    builder = LayoutGraphBuilder()
    zero = [g for g in (zero_start_graph(builder, layout)
                        for layout in dataset["train"].remove_columns(["image"])) if g is not None]
    assert len(zero) == len(layouts)
    order = torch.randperm(len(layouts), generator=torch.Generator().manual_seed(2026)).tolist()
    held = order[:len(layouts) // 20]
    naive_held = [layouts[i][0] for i in held]
    structure_held = [layouts[i][1] for i in held]
    zero_held = [zero[i] for i in held]

    def model(path):
        m = ThemeSyncGNN(num_layers=3, node_dim=8, edge_dim=4, hidden_dim=64).to(device)
        m.load_state_dict(torch.load(path, map_location=device, weights_only=True))
        return m

    def pick(r):
        return {k: r[k] for k in METRICS}

    results = {}
    results["v1 as deployed (0,0 start)"] = pick(evaluate(model(CHECKPOINTS["v1"]), zero_held, device))
    v2 = evaluate(model(CHECKPOINTS["v2"]), naive_held, device)
    results["naive stack (no model)"] = {"mae_xy": v2["naive_mae_xy"], "mae_gap": v2["naive_mae_gap"],
                                         "order_kept": 1.0, "overlap": v2["naive_overlap"]}
    results["v2, positions only"] = pick(evaluate(model(CHECKPOINTS["v2_posonly"]), naive_held, device))
    results["v2, positions + relations"] = pick(v2)
    results["v3, naive input"] = pick(evaluate(model(CHECKPOINTS["v3"]), naive_held, device))
    v3s = evaluate(model(CHECKPOINTS["v3"]), structure_held, device)
    # the start itself, scored like a prediction (order: its own y order)
    start_order = sum(float((g.x[1:, 1] >= g.x[:-1, 1]).float().sum()) for g in structure_held) / sum(
        g.x.shape[0] - 1 for g in structure_held)
    results["structure start (no model)"] = {"mae_xy": v3s["naive_mae_xy"], "mae_gap": v3s["naive_mae_gap"],
                                             "order_kept": start_order, "overlap": v3s["naive_overlap"]}
    results["v2, structure input"] = pick(evaluate(model(CHECKPOINTS["v2"]), structure_held, device))
    results["v3, structure input (default)"] = pick(v3s)

    raw = [layout for layout in dataset["train"].remove_columns(["image"])
           if sum(1 for n in layout["extracted_nodes"] if n["semantic_category"]["name"] in GNN_CGL_CATEGORIES
                  and n["bbox"][2] > 0 and n["bbox"][3] > 0) >= 2]
    assert len(raw) == len(layouts)
    cases = exact_anchor_cases(builder, [raw[i] for i in held])
    exact = {}
    for name, key in (("v3", "v3"), ("v2", "v2")):
        for row, e in exact_anchor_errors(model(CHECKPOINTS[key]), cases, device).items():
            if row == "start (mapping only)" and row in exact:
                continue
            exact[row if row.startswith("start") else f"{name}, {row.split(' ', 1)[1]}"] = e

    out = {"heldout_layouts": len(naive_held),
           "heldout": "seeded 5% of CGL train, never trained on (CGL test has no annotations)",
           "units": "fractions of the canvas (0-1); order_kept is a share of consecutive pairs",
           "results": {k: {m: round(v, 4) for m, v in r.items()} for k, r in results.items()},
           "exact_anchors": {
               "setup": "real centres as anchors, up to half the elements unmapped (seed 7); "
                        "vertical-centre error, fractions of the height",
               "anchored_elements": sum(len(c["anchors"]) for c in cases),
               "unmapped_elements": sum(len(c["unmapped"]) for c in cases),
               "results": {k: {m: round(v, 4) for m, v in r.items()} for k, r in exact.items()}}}
    path = os.path.join(_ROOT, "results", "gnn_heldout_eval.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Held-out CGL layouts: {len(naive_held)}")
    print(f"{'model':<34} {'pos MAE':>8} {'gap MAE':>8} {'order':>7} {'overlap':>8}")
    for name, r in out["results"].items():
        print(f"{name:<34} {r['mae_xy']:>8.4f} {r['mae_gap']:>8.4f} {r['order_kept']:>7.3f} {r['overlap']:>8.4f}")
    print(f"\nExact anchors ({out['exact_anchors']['anchored_elements']} anchored / "
          f"{out['exact_anchors']['unmapped_elements']} unmapped elements), vertical-centre error:")
    print(f"{'':<34} {'anchored':>9} {'unmapped':>9} {'all':>9}")
    for name, r in out["exact_anchors"]["results"].items():
        print(f"{name:<34} {r['anchored']:>9.4f} {r['unmapped']:>9.4f} {r['all']:>9.4f}")
    print(f"Saved → {path}")


if __name__ == "__main__":
    main()
