import torch
import torch.nn as nn
from torch_geometric.nn import MessagePassing

class RelationalLayoutLayer(MessagePassing):
    def __init__(self, node_dim=8, edge_dim=4, hidden_dim=64):
        # The architecture dictates a permutation-invariant aggregation operator, explicitly set to 'mean' pooling
        super(RelationalLayoutLayer, self).__init__(aggr='mean')
        
        # Message Function (Phi): Multilayer Perceptron (MLP)
        # Calculates dependencies by concatenating [h_i, h_j, e_ij]
        self.phi = nn.Sequential(
            nn.Linear(node_dim * 2 + edge_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU()
        )
        
        # Node Update Function (Psi): Gated Recurrent Unit (GRU)
        # Updates the hidden state of the node using the aggregated messages
        self.psi = nn.GRUCell(input_size=hidden_dim, hidden_size=node_dim)

    def forward(self, x, edge_index, edge_attr):
        """
        Executes the forward propagation through the GNN layer.
        Bypasses message calculation if the graph consists of an isolated node.
        """
        if edge_index.shape[1] == 0:
            return x
            
        return self.propagate(edge_index, x=x, edge_attr=edge_attr)

    def message(self, x_i, x_j, edge_attr):
        """
        Constructs the messages to be passed between adjacent nodes.
        x_i: target node features
        x_j: source node features
        edge_attr: spatial relationships (delta x, delta y, IoU, alignment)
        """
        # Formulate input tensor for the MLP
        msg_input = torch.cat([x_i, x_j, edge_attr], dim=1)
        return self.phi(msg_input)

    def update(self, aggr_out, x):
        """
        Executes the state transition for each node.
        aggr_out: the mean-aggregated messages from all neighbors
        x: the current node feature vector
        """
        new_x = self.psi(aggr_out, x)
        return new_x

class ThemeSyncGNN(nn.Module):
    def __init__(self, num_layers=3, node_dim=8, edge_dim=4, hidden_dim=64):
        """
        Compiles the full neural network structure for multi-hop spatial reasoning.
        """
        super(ThemeSyncGNN, self).__init__()
        self.num_layers = num_layers
        
        # Initialize a sequence of RelationalLayoutLayers
        self.layers = nn.ModuleList([
            RelationalLayoutLayer(node_dim, edge_dim, hidden_dim) 
            for _ in range(num_layers)
        ])

    def forward(self, graph_data):
        x, edge_index, edge_attr = graph_data.x, graph_data.edge_index, graph_data.edge_attr
        
        # Iteratively pass node states through the network to evaluate complex dependencies
        for layer in self.layers:
            x = layer(x, edge_index, edge_attr)
            
        return x

def test_gnn():
    """
    Diagnostic sequence to validate the forward propagation of the model architecture.
    """
    from torch_geometric.data import Data
    
    print("Initializing simulated spatial graph...")
    # Simulate 2 nodes with 8 features
    mock_x = torch.rand((2, 8), dtype=torch.float32)
    # Simulate a bi-directional edge between the nodes
    mock_edge_index = torch.tensor([[0, 1], [1, 0]], dtype=torch.long)
    # Simulate 4 edge attributes (dx, dy, IoU, align)
    mock_edge_attr = torch.rand((2, 4), dtype=torch.float32)
    
    mock_graph = Data(x=mock_x, edge_index=mock_edge_index, edge_attr=mock_edge_attr)
    
    print("Initializing ThemeSync GNN (3 Layers)...")
    model = ThemeSyncGNN()
    
    print("Executing forward pass...")
    output = model(mock_graph)
    
    print(f"Initial Tensor Shape: {mock_x.shape}")
    print(f"Output Tensor Shape: {output.shape}")
    print("Diagnostic Complete: Message Passing and Node Updates calculated successfully.")

if __name__ == "__main__":
    test_gnn()