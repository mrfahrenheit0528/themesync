import json
import os

class HeuristicEvaluator:
    def __init__(self, canvas_width=1200, canvas_height=900):
        self.canvas_w = canvas_width
        self.canvas_h = canvas_height
        
        # Static scalar weights (alpha, beta, gamma)
        self.alpha = 1.0  
        self.beta = 0.5   
        self.gamma = 2.0  

    def calculate_alignment_penalty(self, nodes):
        """Penalizes deviation from the vertical center axis."""
        center_axis = self.canvas_w / 2.0
        penalty = 0.0
        
        for node in nodes:
            # Skip repeating groups for central axis calculation
            if node.get('structural_class') == 'repeating_group':
                continue
                
            node_cx = node['bbox'][0] + (node['bbox'][2] / 2.0)
            deviation = abs(center_axis - node_cx)
            penalty += deviation / self.canvas_w
            
        return penalty

    def calculate_whitespace_penalty(self, nodes):
        """Evaluates spatial distribution by measuring vertical crowding."""
        penalty = 0.0
        
        # Sort vertically to measure sequential gaps
        sorted_nodes = sorted(nodes, key=lambda n: n['bbox'][1])
        
        for i in range(len(sorted_nodes) - 1):
            current_bottom = sorted_nodes[i]['bbox'][1] + sorted_nodes[i]['bbox'][3]
            next_top = sorted_nodes[i+1]['bbox'][1]
            gap = next_top - current_bottom
            
            # Penalize exceptionally tight spatial gaps
            if gap < 10 and gap >= 0:
                penalty += 1.0
            elif gap > 100:
                penalty += 0.5
                
        return penalty

    def calculate_legibility_penalty(self, nodes):
        """
        Penalizes text nodes placed in structurally risky zones.
        In a full run, this evaluates overlap with the SIFT saliency map.
        """
        penalty = 0.0
        
        for node in nodes:
            if node.get('structural_class') == 'text_node':
                x, y, w, h = node['bbox']
                # Penalize text pushing into the 50px outer margins
                if x < 50 or (x + w) > (self.canvas_w - 50):
                    penalty += 0.8
                    
        return penalty

    def evaluate_layout(self, filepath):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"State file not found at {filepath}")
            
        with open(filepath, 'r') as f:
            nodes = json.load(f)
            
        p_align = self.calculate_alignment_penalty(nodes)
        p_space = self.calculate_whitespace_penalty(nodes)
        p_leg = self.calculate_legibility_penalty(nodes)
        
        c_total = (self.alpha * p_align) + (self.beta * p_space) + (self.gamma * p_leg)
        
        return {
            "P_align": round(p_align, 4),
            "P_space": round(p_space, 4),
            "P_legibility": round(p_leg, 4),
            "Total_Cost": round(c_total, 4)
        }

def test_optimization():
    print("Executing Phase 3: Heuristic Layout Evaluation...")
    evaluator = HeuristicEvaluator()
    
    # Target the layout state file edited during Phase 2
    state_file = "data/processed/layout_state_v1_edited.json"
    
    try:
        scores = evaluator.evaluate_layout(state_file)
        print("\nHeuristic Penalties Calculated:")
        print(f" -> Alignment Penalty (P_align): {scores['P_align']}")
        print(f" -> Whitespace Penalty (P_space): {scores['P_space']}")
        print(f" -> Legibility Penalty (P_legibility): {scores['P_legibility']}")
        print(f"\nTotal Layout Cost (C_total): {scores['Total_Cost']}")
        print("Objective: The GNN will be trained to minimize this C_total variable.")
        
    except Exception as e:
        print(f"Optimization Engine Failure: {e}")

if __name__ == "__main__":
    test_optimization()