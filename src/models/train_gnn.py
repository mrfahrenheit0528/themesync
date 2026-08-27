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

class DifferentiableHeuristicLoss(nn.Module):
    def __init__(self, canvas_w=1200.0, canvas_h=900.0):
        super().__init__()
        self.canvas_w = canvas_w
        self.canvas_h = canvas_h
        
    def forward(self, predicted_tensors):
        """
        Executes heuristic minimization via differentiable tensor operations.
        predicted_tensors format: [X, Y, W, H, C1, C2, C3, Saliency]
        """
        x = predicted_tensors[:, 0]
        y = predicted_tensors[:, 1]
        w = predicted_tensors[:, 2]
        h = predicted_tensors[:, 3]
        
        # 1. Differentiable Alignment Penalty (P_align)
        # Calculates absolute variance from the central vertical axis
        centers_x = x + (w / 2.0)
        target_center = self.canvas_w / 2.0
        p_align = torch.mean(torch.abs(centers_x - target_center)) / self.canvas_w
        
        # 2. Differentiable Boundary Enforcement (P_space / Soft Constraints)
        # Utilizes Rectified Linear Units (ReLU) to penalize coordinates protruding off-canvas
        p_bound_left = torch.relu(-x)
        p_bound_right = torch.relu((x + w) - self.canvas_w)
        p_bound_top = torch.relu(-y)
        p_bound_bottom = torch.relu((y + h) - self.canvas_h)
        
        p_boundary = torch.mean(p_bound_left + p_bound_right + p_bound_top + p_bound_bottom)
        
        # Aggregate the global scalar cost (C_total)
        return p_align + (p_boundary * 2.0)

def execute_training():
    print("Initializing Fortified HPC Training Environment...")
    device = torch.device('cuda:2' if torch.cuda.is_available() else 'cpu')
    
    dataset = ds.load_from_disk("data/processed/cgl_tensor_dataset")
    builder = LayoutGraphBuilder()
    
    print("Constructing PyTorch Geometric graphs...")
    graphs = [builder.build_graph(layout) for layout in dataset['train'] if builder.build_graph(layout) is not None]
            
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
            loss = criterion(predicted_x)
            
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