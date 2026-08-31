import json
import os

class HeuristicEvaluator:
    def __init__(self, canvas_width=1200, canvas_height=900):
        self.canvas_w = float(canvas_width)
        self.canvas_h = float(canvas_height)
        
        # Static scalar weights calibrated per Chapter 3 (§3.2 / Formula 3.11)
        # alpha is assigned the highest weight to strictly penalize element overlap
        self.alpha = 50.0   # P_collision weight
        self.beta = 2.0     # P_alignment weight
        self.gamma = 1.0    # P_whitespace weight
        self.delta = 1.5    # P_legibility weight
        self.r_target = 0.65 # Optimal whitespace ratio

    def _clamp_coordinates(self, bbox):
        x, y, w, h = bbox
        clamped_x = max(0.0, min(float(x), self.canvas_w - w))
        clamped_y = max(0.0, min(float(y), self.canvas_h - h))
        return [clamped_x, clamped_y, float(w), float(h)]

    def calculate_collision_penalty(self, nodes):
        """
        Formula 3.12: P_collision = sum_{i=1}^N sum_{j=i+1}^N Area(B_i \cap B_j)
        Calculates total overlapping area between all pairs of bounding boxes.
        """
        total_overlap_area = 0.0
        n = len(nodes)
        
        for i in range(n):
            b1 = self._clamp_coordinates(nodes[i]['bbox'])
            x1_min, y1_min, w1, h1 = b1
            x1_max, y1_max = x1_min + w1, y1_min + h1
            
            for j in range(i + 1, n):
                b2 = self._clamp_coordinates(nodes[j]['bbox'])
                x2_min, y2_min, w2, h2 = b2
                x2_max, y2_max = x2_min + w2, y2_min + h2
                
                inter_w = max(0.0, min(x1_max, x2_max) - max(x1_min, x2_min))
                inter_h = max(0.0, min(y1_max, y2_max) - max(y1_min, y2_min))
                
                if inter_w > 0 and inter_h > 0:
                    total_overlap_area += (inter_w * inter_h)
                    
        # Normalize relative to canvas area
        canvas_area = self.canvas_w * self.canvas_h
        return (total_overlap_area / canvas_area) if canvas_area > 0 else 0.0

    def calculate_alignment_penalty(self, nodes):
        """
        Formula 3.13: Measures pixel variance from the primary symmetry axis (centerline).
        """
        center_axis = self.canvas_w / 2.0
        penalty_sum = 0.0
        valid_nodes = 0
        
        for node in nodes:
            if node.get('structural_class') == 'repeating_group':
                continue
                
            clamped_bbox = self._clamp_coordinates(node['bbox'])
            node_cx = clamped_bbox[0] + (clamped_bbox[2] / 2.0)
            
            deviation = abs(center_axis - node_cx)
            penalty_sum += deviation / self.canvas_w
            valid_nodes += 1
            
        return (penalty_sum / valid_nodes) if valid_nodes > 0 else 0.0

    def calculate_whitespace_penalty(self, nodes):
        """
        Formula 3.14: Evaluates whitespace ratio against target R_target.
        """
        canvas_area = self.canvas_w * self.canvas_h
        if canvas_area <= 0:
            return 0.0
            
        total_element_area = sum(float(n['bbox'][2]) * float(n['bbox'][3]) for n in nodes)
        whitespace_ratio = (canvas_area - total_element_area) / canvas_area
        return abs(whitespace_ratio - self.r_target)

    def calculate_legibility_penalty(self, nodes):
        """
        Formula 3.15: Penalizes elements placed too close to canvas boundaries
        or colliding with margin safety boundaries.
        """
        penalty = 0.0
        margin_threshold = 40.0
        
        for node in nodes:
            x, y, w, h = node['bbox']
            # Penalize protruding beyond margins
            if x < margin_threshold:
                penalty += (margin_threshold - x) / self.canvas_w
            if (x + w) > (self.canvas_w - margin_threshold):
                penalty += ((x + w) - (self.canvas_w - margin_threshold)) / self.canvas_w
            if y < margin_threshold:
                penalty += (margin_threshold - y) / self.canvas_h
            if (y + h) > (self.canvas_h - margin_threshold):
                penalty += ((y + h) - (self.canvas_h - margin_threshold)) / self.canvas_h
                
        return penalty

    def evaluate_layout(self, filepath_or_nodes):
        if isinstance(filepath_or_nodes, str):
            if not os.path.exists(filepath_or_nodes):
                raise FileNotFoundError(f"State file not found at {filepath_or_nodes}")
            with open(filepath_or_nodes, 'r') as f:
                nodes = json.load(f)
        else:
            nodes = filepath_or_nodes
            
        p_collision = self.calculate_collision_penalty(nodes)
        p_align = self.calculate_alignment_penalty(nodes)
        p_space = self.calculate_whitespace_penalty(nodes)
        p_leg = self.calculate_legibility_penalty(nodes)
        
        # Formula 3.11: F_layout = alpha*P_collision + beta*P_align + gamma*P_whitespace + delta*P_legibility
        c_total = (self.alpha * p_collision) + (self.beta * p_align) + (self.gamma * p_space) + (self.delta * p_leg)
        
        return {
            "P_collision": round(p_collision, 4),
            "P_align": round(p_align, 4),
            "P_space": round(p_space, 4),
            "P_legibility": round(p_leg, 4),
            "Total_Cost": round(c_total, 4)
        }

def test_optimization():
    print("Executing Phase 3: Heuristic Layout Evaluation (Fortified)...")
    evaluator = HeuristicEvaluator()
    state_file = "data/processed/layout_state_v1.json"
    
    if os.path.exists(state_file):
        scores = evaluator.evaluate_layout(state_file)
        print("\nHeuristic Penalties Calculated:")
        print(f" -> Collision Penalty (P_collision): {scores['P_collision']}")
        print(f" -> Alignment Penalty (P_align): {scores['P_align']}")
        print(f" -> Whitespace Penalty (P_space): {scores['P_space']}")
        print(f" -> Legibility Penalty (P_legibility): {scores['P_legibility']}")
        print(f"\nTotal Layout Cost (C_total): {scores['Total_Cost']}")

if __name__ == "__main__":
    test_optimization()