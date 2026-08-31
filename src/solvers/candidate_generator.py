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
    def __init__(self, canvas_width=1200, canvas_height=900, output_dir="data/processed/"):
        self.canvas_w = float(canvas_width)
        self.canvas_h = float(canvas_height)
        self.output_dir = output_dir
        self.evaluator = HeuristicEvaluator(canvas_width=canvas_width, canvas_height=canvas_height)
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_and_rank_candidates(self, base_nodes, population_size=5):
        """
        Explores diverse layout state candidates by varying parametric constraints
        (margins, vertical gaps, element density) and solving each variation 
        strictly through the Cassowary Constraint Solver to guarantee zero overlap.
        """
        results = []
        
        # Variation parameter configurations (each represents an aesthetically distinct candidate)
        variations = [
            {"name": "Candidate_0_GNN_Baseline",     "margin": 60.0, "vgap": 18.0},
            {"name": "Candidate_1_Compact_Formal",   "margin": 75.0, "vgap": 12.0},
            {"name": "Candidate_2_Spaced_Grand",     "margin": 50.0, "vgap": 26.0},
            {"name": "Candidate_3_Dynamic_Balanced",  "margin": 65.0, "vgap": 22.0},
            {"name": "Candidate_4_High_Margin_Focus", "margin": 80.0, "vgap": 16.0},
        ]
        
        for i in range(min(population_size, len(variations))):
            var_cfg = variations[i]
            candidate_id = var_cfg["name"]
            
            # Fresh solver instance with candidate's specific spatial parameters
            solver_engine = ConstraintSolverEngine(
                canvas_width=self.canvas_w,
                canvas_height=self.canvas_h,
                margin=var_cfg["margin"],
                default_vgap=var_cfg["vgap"]
            )
            
            # Deepcopy base nodes to ensure isolation
            candidate_input_nodes = copy.deepcopy(base_nodes)
            resolved_candidate_nodes = solver_engine.execute_relational_logic(candidate_input_nodes)
            
            filepath = os.path.join(self.output_dir, f"{candidate_id}.json")
            with open(filepath, 'w') as f:
                json.dump(resolved_candidate_nodes, f, indent=4)
                
            scores = self.evaluator.evaluate_layout(filepath)
            results.append({
                "candidate_id": candidate_id,
                "filepath": filepath,
                "c_total": scores["Total_Cost"],
                "metrics": scores,
                "nodes": resolved_candidate_nodes
            })
            
        # Rank ascending by Total Cost (minimization objective)
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
    weights_path = "themesync_gnn_v1.pth"
    if os.path.exists(weights_path):
        model.load_state_dict(torch.load(weights_path, map_location=device, weights_only=True))
    model.eval()
    
    builder = LayoutGraphBuilder()
    gnn_payload = {
        "extracted_nodes": raw_nodes,
        "extracted_color_centroids": [
            [0.0, 51.0, 102.0],
            [255.0, 204.0, 0.0],
            [255.0, 255.0, 255.0]
        ],
        "extracted_saliency_weight": 0.75
    }
    
    graph_data = builder.build_graph(gnn_payload)
    if graph_data:
        graph_data = graph_data.to(device)
        with torch.no_grad():
            predicted_coords = model(graph_data)
            
        for idx, node in enumerate(raw_nodes):
            pred_x = max(0.0, min(predicted_coords[idx][0].item(), 1200.0 - node['bbox'][2]))
            pred_y = max(0.0, min(predicted_coords[idx][1].item(), 900.0 - node['bbox'][3]))
            node['bbox'] = [round(pred_x, 2), round(pred_y, 2), node['bbox'][2], node['bbox'][3]]
            
    # 3. Metaheuristic Ranking
    print(" -> Executing AAPA Heuristic Evaluation...")
    explorer = MetaheuristicStateExplorer(canvas_width=1200, canvas_height=900)
    ranked_candidates = explorer.generate_and_rank_candidates(raw_nodes, population_size=5)
    
    print("\nAesthetic-Aware Preference Alignment (AAPA) Rankings:")
    for rank, candidate in enumerate(ranked_candidates):
        print(f" [Rank {rank + 1}] {candidate['candidate_id']}")
        print(f"    -> Total Cost (C_total): {candidate['c_total']:.4f}")

if __name__ == "__main__":
    execute_exploration()