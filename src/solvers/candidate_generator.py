import json
import os
import copy
import random
import sys
import torch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models')))
from dynamic_instantiation import NodeInstantiator
from optimization_engine import HeuristicEvaluator
from cassowary_engine import ConstraintSolverEngine
from gnn_model import ThemeSyncGNN
from graph_builder import LayoutGraphBuilder

class MetaheuristicStateExplorer:
    def __init__(self, output_dir="data/processed/"):
        self.output_dir = output_dir
        self.evaluator = HeuristicEvaluator()
        os.makedirs(self.output_dir, exist_ok=True)

    def _stochastic_spatial_mutation(self, nodes, search_radius=60.0):
        mutated_nodes = copy.deepcopy(nodes)
        for node in mutated_nodes:
            if node.get('structural_class') == 'repeating_group':
                continue
                
            dx = random.uniform(-search_radius, search_radius)
            dy = random.uniform(-search_radius, search_radius)
            
            node['bbox'][0] = max(0.0, node['bbox'][0] + dx)
            node['bbox'][1] = max(0.0, node['bbox'][1] + dy)
                
        return mutated_nodes

    def generate_and_rank_candidates(self, base_nodes, population_size=5):
        results = []
        
        filepath = os.path.join(self.output_dir, "Candidate_0_GNN_Baseline.json")
        with open(filepath, 'w') as f:
            json.dump(base_nodes, f, indent=4)
        
        baseline_scores = self.evaluator.evaluate_layout(filepath)
        results.append({
            "candidate_id": "Candidate_0_GNN_Baseline",
            "filepath": filepath,
            "c_total": baseline_scores["Total_Cost"],
            "metrics": baseline_scores
        })
        
        for i in range(1, population_size):
            mutated_nodes = self._stochastic_spatial_mutation(base_nodes, search_radius=120.0)
            name = f"Candidate_{i}_Metaheuristic"
            filepath = os.path.join(self.output_dir, f"{name}.json")
            
            with open(filepath, 'w') as f:
                json.dump(mutated_nodes, f, indent=4)
                
            scores = self.evaluator.evaluate_layout(filepath)
            results.append({
                "candidate_id": name,
                "filepath": filepath,
                "c_total": scores["Total_Cost"],
                "metrics": scores
            })
            
        results.sort(key=lambda x: x["c_total"])
        return results

def execute_exploration():
    print("Initializing AI-Driven State-Space Exploration...")
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # 1. Instantiate 
    instantiator = NodeInstantiator(canvas_width=1200, canvas_height=900)
    raw_nodes = instantiator.instantiate_payload("data/raw/academic_payload.json")
    
    # 2. Execute GNN Inference
    print(" -> Loading GNN Weights for Spatial Prediction...")
    model = ThemeSyncGNN(num_layers=3, node_dim=8, edge_dim=4, hidden_dim=64).to(device)
    
    # Ensure secure loading of the model weights
    weights_path = "themesync_gnn_v1.pth"
    if os.path.exists(weights_path):
        model.load_state_dict(torch.load(weights_path, map_location=device, weights_only=True))
    else:
        print(f"Warning: {weights_path} missing. Proceeding with untrained initialization.")
        
    model.eval()
    builder = LayoutGraphBuilder()
    
    # Inject the structural nodes AND the required stylistic/saliency tensors
    gnn_payload = {
        "extracted_nodes": raw_nodes,
        "extracted_color_centroids": [
            [0.0, 51.0, 102.0],    # Primary (e.g., #003366)
            [255.0, 204.0, 0.0],   # Accent  (e.g., #FFCC00)
            [255.0, 255.0, 255.0]  # Background (e.g., #FFFFFF)
        ],
        "extracted_saliency_weight": 0.75  # Simulated SIFT keypoint density
    }
    
    # Construct relational graph for the new payload
    graph_data = builder.build_graph(gnn_payload)
    
    if graph_data:
        graph_data = graph_data.to(device)
        with torch.no_grad():
            predicted_coords = model(graph_data)
            
        # Update payload with intelligent predictions (Slice strictly the first 4 spatial tensors)
        # Update payload with intelligent predictions (Strict X, Y isolation)
        for idx, node in enumerate(raw_nodes):
            # 1. Extract the predicted origins
            pred_x = predicted_coords[idx][0].item()
            pred_y = predicted_coords[idx][1].item()
            
            # 2. Preserve the mathematically instantiated footprints
            original_w = node['bbox'][2]
            original_h = node['bbox'][3]
            
            # 3. Reconstruct the tensor: [Predicted X, Predicted Y, Static W, Static H]
            node['bbox'] = [round(pred_x, 2), round(pred_y, 2), original_w, original_h]
            
    # 3. Resolve Constraints via Cassowary
    print(" -> Enforcing Hard Constraints via Cassowary...")
    engine = ConstraintSolverEngine(canvas_width=1200, canvas_height=900)
    resolved_nodes = engine.execute_relational_logic(raw_nodes)
    
    # 4. Metaheuristic Ranking
    print(" -> Executing AAPA Heuristic Evaluation...")
    explorer = MetaheuristicStateExplorer()
    ranked_candidates = explorer.generate_and_rank_candidates(resolved_nodes, population_size=5)
    
    print("\nAesthetic-Aware Preference Alignment (AAPA) Rankings:")
    for rank, candidate in enumerate(ranked_candidates):
        print(f" [Rank {rank + 1}] {candidate['candidate_id']}")
        print(f"    -> Total Cost (C_total): {candidate['c_total']:.4f}")

if __name__ == "__main__":
    execute_exploration()