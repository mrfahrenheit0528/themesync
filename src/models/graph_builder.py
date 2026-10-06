import torch
import numpy as np
import datasets as ds
from torch_geometric.data import Data

# CGL-Dataset element classes the GNN is trained on (`semantic_category.name`):
# 0 = logo, 1 = text. Underlays (2) and embellishments (3) are decoration,
# which ThemeSync's renderer places from the master layout itself.
GNN_CGL_CATEGORIES = (0, 1)

# Gap between consecutive elements in the starting arrangement, as a
# fraction of canvas height.
NAIVE_GAP = 0.02


def naive_stack(sizes: list, gap: float = NAIVE_GAP) -> list:
    """
    The shared starting arrangement the GNN refines, in fractions of the
    canvas: each element centred horizontally, stacked top to bottom in
    reading order with a uniform gap, the stack centred vertically.

    Training (CGL layouts, in reading order) and inference (certificate /
    event-ID nodes, in spatial_hierarchy order) both start from this, so the
    model is never shown a starting point at inference that it never saw in
    training. It is also the arrangement the CSP builds on its own in
    baseline (no-GNN) mode, so the GNN's contribution is exactly its
    learned departure from it.

    sizes: [(w, h), ...] as fractions of the canvas. Returns [(x, y), ...].
    """
    n = len(sizes)
    if n == 0:
        return []
    content = sum(h for _, h in sizes)
    if n > 1 and content + gap * (n - 1) > 1.0:
        gap = max(0.0, (1.0 - content) / (n - 1))
    y = max(0.0, (1.0 - content - gap * (n - 1)) / 2.0)
    starts = []
    for w, h in sizes:
        starts.append((max(0.0, (1.0 - w) / 2.0), y))
        y += h + gap
    return starts


def structure_start(sizes: list, anchors: dict) -> list:
    """
    Starting arrangement from a master layout's structure (notes §3.26):
    each element with a counterpart on the master starts centred where that
    counterpart sits (`anchors`: {index: (cx, cy)} as fractions of the
    canvas); the others are placed in reading order between them, centred
    horizontally, spaced as in the naive stack beyond the first/last anchor.
    Centres never decrease down the reading order.

    Used at inference with anchors mapped from the master's detections, and
    in training with anchors taken from a CGL layout's real positions,
    distorted the way a cross-format mapping distorts them.

    sizes: [(w, h), ...] fractions of the canvas, in reading order.
    Returns [(x, y), ...] top-left starting positions.
    """
    n = len(sizes)
    if not anchors:
        return naive_stack(sizes)
    naive = naive_stack(sizes)
    naive_cy = [y + h / 2.0 for (_, y), (_, h) in zip(naive, sizes)]
    cys = [None] * n
    cxs = [None] * n
    for i, (cx, cy) in anchors.items():
        if 0 <= i < n:
            cxs[i], cys[i] = float(cx), float(cy)
    last = None
    for i in range(n):  # keep reading order
        if cys[i] is not None:
            if last is not None and cys[i] < last:
                cys[i] = last
            last = cys[i]
    known = [i for i in range(n) if cys[i] is not None]
    for i in range(n):
        if cys[i] is not None:
            continue
        prev = max((k for k in known if k < i), default=None)
        nxt = min((k for k in known if k > i), default=None)
        if prev is not None and nxt is not None:
            t = (i - prev) / float(nxt - prev)
            cys[i] = cys[prev] + t * (cys[nxt] - cys[prev])
        elif prev is not None:
            cys[i] = cys[prev] + (naive_cy[i] - naive_cy[prev])
        else:
            cys[i] = cys[nxt] - (naive_cy[nxt] - naive_cy[i])
    starts = []
    for i, (w, h) in enumerate(sizes):
        cx = cxs[i] if cxs[i] is not None else 0.5
        starts.append((min(max(0.0, cx - w / 2.0), max(0.0, 1.0 - w)),
                       min(max(0.0, cys[i] - h / 2.0), max(0.0, 1.0 - h))))
    return starts


def _monotone_anchor_cys(anchors: dict, n: int) -> dict:
    """{index: cy} for the anchors, raised where needed so centres never
    decrease down the reading order (as structure_start places them)."""
    out, last = {}, None
    for i in sorted(k for k in anchors if 0 <= k < n):
        cy = float(anchors[i][1])
        if last is not None and cy < last:
            cy = last
        out[i] = last = cy
    return out


def register_to_anchors(pred_cys: list, anchors: dict) -> list:
    """
    The GNN's refined arrangement, registered to the master's anchors
    (notes §3.26): each anchored element goes back to its counterpart's
    position on the master, and each unmapped element goes between its
    neighbouring anchors in proportion to where the GNN put it (beyond the
    first/last anchor, at the GNN's distance from it).

    So the transferred composition is kept exactly and the GNN decides the
    rest. On 2,900 held-out CGL layouts with exact anchors, v3's raw output
    moved the anchors by 2.6% of the height and placed the unmapped
    elements no better than interpolation (0.084 vs. 0.081 error); registered,
    it keeps the anchors and places the unmapped elements 8% better (0.075).

    pred_cys: predicted vertical centres, fractions of the height, in
    reading order. anchors: {index: (cx, cy)} as for structure_start.
    Returns the registered vertical centres.
    """
    n = len(pred_cys)
    fixed = _monotone_anchor_cys(anchors, n)
    if not fixed:
        return list(pred_cys)
    idx = sorted(fixed)
    out = list(pred_cys)
    for i in idx:
        out[i] = fixed[i]
    for j in range(n):
        if j in fixed:
            continue
        lo = max((i for i in idx if i < j), default=None)
        hi = min((i for i in idx if i > j), default=None)
        if lo is not None and hi is not None:
            span = pred_cys[hi] - pred_cys[lo]
            t = (pred_cys[j] - pred_cys[lo]) / span if abs(span) > 1e-6 else (j - lo) / float(hi - lo)
            out[j] = fixed[lo] + min(max(t, 0.0), 1.0) * (fixed[hi] - fixed[lo])
        elif lo is not None:
            out[j] = fixed[lo] + (pred_cys[j] - pred_cys[lo])
        else:
            out[j] = fixed[hi] + (pred_cys[j] - pred_cys[hi])
    return out


def distorted_structure_start(sizes: list, positions: list, rng) -> list:
    """
    Training input for the structure-conditioned GNN: a layout's real
    positions as a master-to-target mapping would deliver them — the whole
    composition rescaled (0.75-1.25) and shifted (±8%) vertically, each
    element jittered (σ 2.5% vertically, 3% horizontally), and up to half of
    the elements (never all) left unmapped, to be placed in order by
    structure_start. `rng` is a numpy Generator.
    """
    n = len(sizes)
    centres = [(x + w / 2.0, y + h / 2.0) for (x, y), (w, h) in zip(positions, sizes)]
    scale, shift = rng.uniform(0.75, 1.25), rng.uniform(-0.08, 0.08)
    n_unmapped = int(rng.integers(0, max(1, n // 2) + 1))
    unmapped = set(rng.choice(n, size=min(n_unmapped, n - 1), replace=False).tolist()) if n > 1 else set()
    anchors = {}
    for i, (cx, cy) in enumerate(centres):
        if i in unmapped:
            continue
        cy = 0.5 + (cy - 0.5) * scale + shift + rng.normal(0.0, 0.025)
        cx = cx + rng.normal(0.0, 0.03)
        anchors[i] = (min(max(cx, 0.0), 1.0), min(max(cy, 0.0), 1.0))
    return structure_start(sizes, anchors)


class LayoutGraphBuilder:
    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    def calculate_iou(self, box1, box2):
        """Calculates the Intersection over Union (IoU) between two bounding boxes."""
        x1_min, y1_min, w1, h1 = box1
        x2_min, y2_min, w2, h2 = box2
        
        x1_max, y1_max = x1_min + w1, y1_min + h1
        x2_max, y2_max = x2_min + w2, y2_min + h2

        inter_x_min = max(x1_min, x2_min)
        inter_y_min = max(y1_min, y2_min)
        inter_x_max = min(x1_max, x2_max)
        inter_y_max = min(y1_max, y2_max)

        inter_area = max(0, inter_x_max - inter_x_min) * max(0, inter_y_max - inter_y_min)
        box1_area = w1 * h1
        box2_area = w2 * h2
        union_area = box1_area + box2_area - inter_area

        return inter_area / union_area if union_area > 0 else 0.0

    def calculate_alignment(self, box1, box2):
        """
        Calculates an alignment score (0 to 1) based on shared axis coordinates.
        1.0 implies perfect center or edge alignment.
        """
        x1, y1, w1, h1 = box1
        x2, y2, w2, h2 = box2
        
        cx1, cy1 = x1 + w1/2, y1 + h1/2
        cx2, cy2 = x2 + w2/2, y2 + h2/2
        
        dx = abs(cx1 - cx2) / max(w1, w2, 1)
        dy = abs(cy1 - cy2) / max(h1, h2, 1)
        
        align_score = max(0, 1.0 - min(dx, dy))
        return align_score

    def validate_bounding_tensor(self, bbox, category):
        """
        Mathematically validates the bounding box tensor to prevent 
        ZeroDivisionError during IoU adjacency calculations.
        """
        x, y, w, h = bbox
        if w <= 0 or h <= 0:
            print(f"Anomaly Detected: Node '{category}' possesses corrupt dimensions [w: {w}, h: {h}]. Filtering from graph.")
            return False
        return True

    def build_graph(self, layout_data):
        """
        Constructs the h_i node vectors and e_ij edge matrices.

        Positional features (bbox, dx/dy) are normalized by the layout's own
        canvas dimensions so they sit on the same ~[0, 1] scale as colour
        (/255) and saliency (already [0, 1]). Without this, raw pixel-scale
        coordinates (up to 1000+) swamp the other features and the GRU-based
        message passing degenerates to a near-constant output. Canvas size is
        read from `canvas_w`/`canvas_h` (inference call sites) or falls back
        to the CGL dataset's own `width`/`height` fields (training data),
        then to the 1200x900 certificate default.
        """
        raw_nodes = layout_data['extracted_nodes']

        # Apply the mathematical filter to reject negative or zero-area tensors
        nodes = [n for n in raw_nodes if self.validate_bounding_tensor(n['bbox'], n.get('semantic_category', 'unknown'))]
        num_nodes = len(nodes)

        if num_nodes == 0:
            return None

        canvas_w = float(layout_data.get('canvas_w', layout_data.get('width', 1200.0)) or 1200.0)
        canvas_h = float(layout_data.get('canvas_h', layout_data.get('height', 900.0)) or 900.0)

        # 1. Construct Node Feature Vector: h_i = [x, y, w, h, c_r, c_g, c_b, s]
        node_features = []
        centroids = layout_data['extracted_color_centroids']
        saliency = layout_data['extracted_saliency_weight']

        primary_color = centroids[0] if len(centroids) > 0 else [0.0, 0.0, 0.0]
        norm_color = [c / 255.0 for c in primary_color]

        for node in nodes:
            bbox = node['bbox']
            norm_bbox = [bbox[0] / canvas_w, bbox[1] / canvas_h, bbox[2] / canvas_w, bbox[3] / canvas_h]
            h_i = norm_bbox + norm_color + [saliency]
            node_features.append(h_i)

        x = torch.tensor(node_features, dtype=torch.float32)

        # 2. Construct Edge Index and Edge Features (e_ij)
        edge_indices = []
        edge_attr = []

        for i in range(num_nodes):
            for j in range(num_nodes):
                if i != j:
                    box_i = nodes[i]['bbox']
                    box_j = nodes[j]['bbox']

                    dx = (box_j[0] - box_i[0]) / canvas_w
                    dy = (box_j[1] - box_i[1]) / canvas_h

                    iou = self.calculate_iou(box_i, box_j)
                    alignment = self.calculate_alignment(box_i, box_j)

                    edge_indices.append([i, j])
                    edge_attr.append([dx, dy, iou, alignment])

        edge_index = torch.tensor(edge_indices, dtype=torch.long).t().contiguous()
        edge_attr = torch.tensor(edge_attr, dtype=torch.float32)

        graph = Data(x=x, edge_index=edge_index, edge_attr=edge_attr)
        return graph

    @staticmethod
    def apply_predictions(nodes, predicted_coords, canvas_w, canvas_h):
        """
        Writes the GNN's predicted (x, y) back onto each node's bbox and marks
        it with `gnn_predicted = True`, so downstream solvers (CSP) can tell a
        real prediction apart from the untouched [0, 0] instantiation default
        instead of guessing from the coordinate value.

        The model predicts x, y as fractions of canvas_w/canvas_h (see
        `build_graph`'s normalization) — this scales them back to pixels
        before clamping to the node's valid on-canvas range.

        Assumes `predicted_coords` is aligned 1:1 with `nodes` by index — true
        as long as no node was filtered out by `build_graph`'s bbox validation.
        """
        for idx, node in enumerate(nodes):
            pred_x = predicted_coords[idx][0].item() * canvas_w
            pred_y = predicted_coords[idx][1].item() * canvas_h
            node["bbox"][0] = round(max(0.0, min(pred_x, canvas_w - node["bbox"][2])), 2)
            node["bbox"][1] = round(max(0.0, min(pred_y, canvas_h - node["bbox"][3])), 2)
            node["gnn_predicted"] = True
        return nodes


def test_builder():
    print("Loading processed tensor dataset...")
    dataset = ds.load_from_disk("data/processed/cgl_tensor_dataset")
    
    print("Initializing LayoutGraphBuilder...")
    builder = LayoutGraphBuilder()
    
    # Iteratively search for the first valid layout containing structural nodes
    sample_graph = None
    for i in range(len(dataset['train'])):
        sample_graph = builder.build_graph(dataset['train'][i])
        if sample_graph is not None:
            print(f"Valid layout identified at dataset index {i}.")
            break
            
    if sample_graph is None:
        print("Diagnostic Failure: No valid layouts found in the dataset.")
        return
    
    print("\nGraph Construction Successful:")
    print(f"Node Tensor (x) Shape: {sample_graph.x.shape} -> Represents {sample_graph.x.shape[0]} nodes with {sample_graph.x.shape[1]} encoded features.")
    print(f"Edge Index Shape: {sample_graph.edge_index.shape}")
    print(f"Edge Attributes Tensor (edge_attr) Shape: {sample_graph.edge_attr.shape} -> Represents delta_x, delta_y, IoU, alignment.")

if __name__ == "__main__":
    test_builder()