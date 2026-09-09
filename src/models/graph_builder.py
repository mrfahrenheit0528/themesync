import torch
import numpy as np
import datasets as ds
from torch_geometric.data import Data

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