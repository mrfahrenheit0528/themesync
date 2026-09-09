import torch
import torch.optim as optim
import torch.nn as nn
import datasets as ds
from torch_geometric.loader import DataLoader
from gnn_model import ThemeSyncGNN
from tqdm import tqdm
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'solvers')))
from graph_builder import LayoutGraphBuilder
from optimization_engine import HeuristicEvaluator

class DifferentiableHeuristicLoss(nn.Module):
    """
    Differentiable analogue of HeuristicEvaluator (optimization_engine.py,
    Formula 3.11): F_layout = alpha*P_collision + beta*P_align + delta*P_legibility.

    Weights are read directly from HeuristicEvaluator instead of being
    re-declared here, so training can never again optimize a different
    objective than the one candidates are ranked on at inference time
    (previously: no collision term at all, and mismatched ad-hoc weights).

    P_whitespace (gamma) is intentionally omitted — it depends only on each
    node's fixed w/h, never on the predicted x/y, so it contributes zero
    gradient and would just be a constant offset.
    """
    def __init__(self, canvas_w=1.0, canvas_h=1.0):
        """
        canvas_w/canvas_h default to 1.0: LayoutGraphBuilder.build_graph now
        normalizes node bbox coordinates to fractions of each layout's own
        canvas, so the model's predicted x/y (and this loss) operate in that
        same unit-square space, not raw pixels.
        """
        super().__init__()
        self.canvas_w = canvas_w
        self.canvas_h = canvas_h
        # Weights are canvas-independent scalars — default canvas here is
        # irrelevant, we only read alpha/beta/delta off the evaluator.
        _ref = HeuristicEvaluator()
        self.alpha = _ref.alpha  # P_collision weight
        self.beta = _ref.beta    # P_align weight
        self.delta = _ref.delta  # P_legibility weight

    def forward(self, predicted, batch):
        """
        predicted : [N, 8] model output for the batch — only the x, y columns
                    (0, 1) are used. w, h are taken from `batch.x` (the true,
                    fixed tensor dimensions used everywhere downstream), not
                    from the model's own output — otherwise the model could
                    trivially minimize the boundary/collision terms by
                    hallucinating degenerate sizes instead of learning good
                    positions.
        batch     : the PyG Batch the predictions were produced from, giving
                    access to the true w/h (`batch.x`), the same-graph edge
                    topology (`batch.edge_index`, never crosses graphs after
                    PyG collation) and the graph count (`batch.num_graphs`).
        """
        x = predicted[:, 0]
        y = predicted[:, 1]
        w = batch.x[:, 2]
        h = batch.x[:, 3]

        # 1. Differentiable Alignment Penalty (P_align) — Formula 3.13
        centers_x = x + (w / 2.0)
        target_center = self.canvas_w / 2.0
        p_align = torch.mean(torch.abs(centers_x - target_center)) / self.canvas_w

        # 2. Differentiable Legibility / Boundary Penalty (P_legibility) — Formula 3.15
        # Utilizes Rectified Linear Units (ReLU) to penalize coordinates protruding off-canvas
        p_bound_left = torch.relu(-x)
        p_bound_right = torch.relu((x + w) - self.canvas_w)
        p_bound_top = torch.relu(-y)
        p_bound_bottom = torch.relu((y + h) - self.canvas_h)
        p_legibility = torch.mean(p_bound_left + p_bound_right + p_bound_top + p_bound_bottom)

        # 3. Differentiable Collision Penalty (P_collision) — Formula 3.12.
        # This is the term the eval fitness function weights 50x — omitted
        # entirely from the previous loss, so the model had zero incentive to
        # avoid overlapping placements.
        p_collision = self._pairwise_collision(x, y, w, h, batch.edge_index, batch.num_graphs)

        return (self.alpha * p_collision) + (self.beta * p_align) + (self.delta * p_legibility)

    def _pairwise_collision(self, x, y, w, h, edge_index, num_graphs):
        """
        Soft overlap penalty summed over the graph's existing fully-connected
        edges (built per-layout in LayoutGraphBuilder, so PyG batching never
        introduces cross-graph edges) — avoids materializing a dense N x N
        matrix over the whole batch.
        """
        if edge_index.numel() == 0:
            return x.new_zeros(())

        src, dst = edge_index[0], edge_index[1]

        x1_min, y1_min = x[src], y[src]
        x1_max, y1_max = x1_min + w[src], y1_min + h[src]
        x2_min, y2_min = x[dst], y[dst]
        x2_max, y2_max = x2_min + w[dst], y2_min + h[dst]

        inter_w = torch.clamp(torch.min(x1_max, x2_max) - torch.max(x1_min, x2_min), min=0.0)
        inter_h = torch.clamp(torch.min(y1_max, y2_max) - torch.max(y1_min, y2_min), min=0.0)
        inter_area = inter_w * inter_h

        canvas_area = self.canvas_w * self.canvas_h
        # Each unordered pair is traversed twice (i->j and j->i); halve to
        # avoid double-counting, then average across graphs in the batch.
        total_overlap = inter_area.sum() / 2.0
        return (total_overlap / canvas_area) / max(num_graphs, 1)

def execute_training():
    print("Initializing Fortified HPC Training Environment...")
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    dataset = ds.load_from_disk("data/processed/cgl_tensor_dataset")
    builder = LayoutGraphBuilder()

    print("Constructing PyTorch Geometric graphs...")
    graphs = []
    for layout in dataset['train']:
        graph = builder.build_graph(layout)
        if graph is not None:
            graphs.append(graph)

    # Hardware Optimization: VRAM Saturation via Batch Scaling
    loader = DataLoader(graphs, batch_size=1024, shuffle=True)
    
    model = ThemeSyncGNN(num_layers=3, node_dim=8, edge_dim=4, hidden_dim=64).to(device)
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    criterion = DifferentiableHeuristicLoss().to(device)
    
    epochs = 100
    model.train()
    
    print(f"\nCommencing Backpropagation Loop on {device} (Batch Size: 1024)...")
    
    for epoch in range(epochs):
        total_loss = 0.0
        
        # User Experience Optimization: Dynamic progress tracking
        progress_bar = tqdm(loader, desc=f"Epoch {epoch+1}/{epochs}", leave=False)
        
        for batch in progress_bar:
            batch = batch.to(device)
            optimizer.zero_grad()
            
            # Forward Pass
            predicted_x = model(batch)

            # Differentiable Heuristic Calculation
            loss = criterion(predicted_x, batch)
            
            # Backward Pass
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            progress_bar.set_postfix({'Loss': f"{loss.item():.4f}"})
            
        avg_loss = total_loss / len(loader)
        if (epoch + 1) % 10 == 0:
            print(f" -> Epoch [{epoch+1}/{epochs}] | Converged Loss: {avg_loss:.4f}")

# APPEND THIS TO SAVE THE CONVERGED WEIGHTS
    save_path = "themesync_gnn_v1.pth"
    torch.save(model.state_dict(), save_path)
    print(f"\nTraining Complete. Neural Network weights serialized to: {save_path}")

if __name__ == "__main__":
    execute_training()