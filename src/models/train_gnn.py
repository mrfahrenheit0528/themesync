import torch
import torch.optim as optim
import datasets as ds
from torch_geometric.loader import DataLoader
from gnn_model import ThemeSyncGNN
import sys
import os

# Append solvers directory to access the optimization engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'solvers')))
from optimization_engine import HeuristicEvaluator
from graph_builder import LayoutGraphBuilder

def execute_training():
    print("Initializing HPC Training Environment...")
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Target Hardware: {device}")

    # 1. Load the preprocessed dataset
    dataset = ds.load_from_disk("data/processed/cgl_tensor_dataset")
    builder = LayoutGraphBuilder()
    
    # Compile PyTorch Geometric graphs
    graphs = []
    for layout in dataset['train']:
        graph = builder.build_graph(layout)
        if graph is not None:
            graphs.append(graph)
            
    loader = DataLoader(graphs, batch_size=32, shuffle=True)
    
    # 2. Initialize the Model and Optimizer
    model = ThemeSyncGNN(num_layers=3, node_dim=8, edge_dim=4, hidden_dim=64).to(device)
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    evaluator = HeuristicEvaluator()
    
    epochs = 100
    model.train()
    
    print("\nCommencing Backpropagation Loop...")
    for epoch in range(epochs):
        total_loss = 0.0
        
        for batch in loader:
            batch = batch.to(device)
            optimizer.zero_grad()
            
            # Forward Pass: Predict new coordinates
            predicted_x = model(batch)
            
            # Note: In a fully differentiable pipeline, the predicted tensors 
            # must be mathematically scored by the heuristic evaluator here.
            # For this prototype structure, we simulate the loss calculation:
            loss = torch.nn.functional.mse_loss(predicted_x, batch.x) # Baseline MSE for structural stability
            
            # Backward Pass
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            
        avg_loss = total_loss / len(loader)
        if (epoch + 1) % 10 == 0:
            print(f" -> Epoch [{epoch+1}/{epochs}] | Mathematical Loss: {avg_loss:.4f}")

if __name__ == "__main__":
    execute_training()