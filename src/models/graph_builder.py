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
        
        # Check center alignment
        cx1, cy1 = x1 + w1/2, y1 + h1/2
        cx2, cy2 = x2 + w2/2, y2 + h2/2
        
        dx = abs(cx1 - cx2) / max(w1, w2, 1)
        dy = abs(cy1 - cy2) / max(h1, h2, 1)
        
        align_score = max(0, 1.0 - min(dx, dy))
        return align_score

    def build_graph(self, layout_data):
        """
        Constructs the h_i node vectors and e_ij edge matrices.
        """
        nodes = layout_data['extracted_nodes']
        num_nodes = len(nodes)
        
        if num_nodes == 0:
            return None

        # 1. Construct Node Feature Vector: h_i = [x, y, w, h, c_r, c_g, c_b, s]
        node_features = []
        centroids = layout_data['extracted_color_centroids']
        saliency = layout_data['extracted_saliency_weight']
        
        # Flatten primary centroid for embedding (using the first dominant color for simplicity)
        primary_color = centroids[0] if len(centroids) > 0 else [0.0, 0.0, 0.0]

        for node in nodes:
            bbox = node['bbox']
            # Feature encoding format
            h_i = [bbox[0], bbox[1], bbox[2], bbox[3]] + primary_color + [saliency]
            node_features.append(h_i)
            
        x = torch.tensor(node_features, dtype=torch.float32)

        # 2. Construct Edge Index and Edge Features (e_ij)
        edge_indices = []
        edge_attr = []

        # Fully connected graph for layout relationships
        for i in range(num_nodes):
            for j in range(num_nodes):
                if i != j:
                    box_i = nodes[i]['bbox']
                    box_j = nodes[j]['bbox']
                    
                    # delta x, delta y
                    dx = box_j[0] - box_i[0]
                    dy = box_j[1] - box_i[1]
                    
                    iou = self.calculate_iou(box_i, box_j)
                    alignment = self.calculate_alignment(box_i, box_j)
                    
                    edge_indices.append([i, j])
                    edge_attr.append([dx, dy, iou, alignment])

        edge_index = torch.tensor(edge_indices, dtype=torch.long).t().contiguous()
        edge_attr = torch.tensor(edge_attr, dtype=torch.float32)

        # Assemble the PyTorch Geometric Data object
        graph = Data(x=x, edge_index=edge_index, edge_attr=edge_attr)
        return graph


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