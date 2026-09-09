import json
import os

class HeuristicEvaluator:
    def __init__(self, canvas_width=1200, canvas_height=900, saliency_map=None,
                 fallback_saliency=0.75, grid_margin=50.0):
        self.canvas_w = float(canvas_width)
        self.canvas_h = float(canvas_height)

        # Static scalar weights calibrated per Chapter 3 (§3.2 / Formula 3.11)
        # alpha is assigned the highest weight to strictly penalize element overlap
        self.alpha = 50.0   # P_collision weight
        self.beta = 2.0     # P_alignment weight
        self.gamma = 1.0    # P_whitespace weight
        self.delta = 1.5    # P_legibility weight
        self.r_target = 0.65 # Optimal whitespace ratio

        # Formula 3.13: margin used to derive the dynamic structural grid G.
        self.grid_margin = float(grid_margin)

        # Formula 3.15: per-region background visual-noise density, from
        # VisionExtractor.calculate_saliency_map. When no real template image
        # is available (synthetic-fallback pipeline runs), a flat density is
        # used instead of leaving the penalty at a permanent zero.
        self.saliency_map = saliency_map
        self.fallback_saliency = float(fallback_saliency)

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
        Formula 3.13: distance from each node's baseline x-coordinate to the
        nearest gridline in a dynamically generated structural grid G. G is
        derived from the canvas width and grid_margin (left margin, quarter,
        center, three-quarter, right margin) rather than a single fixed
        centerline, so nodes aligned to any structural column are rewarded,
        not only ones aligned to dead-center.
        """
        span = max(0.0, self.canvas_w - (2.0 * self.grid_margin))
        grid = [
            self.grid_margin,
            self.grid_margin + span / 4.0,
            self.grid_margin + span / 2.0,
            self.grid_margin + (3.0 * span) / 4.0,
            self.canvas_w - self.grid_margin,
        ]

        penalty_sum = 0.0
        valid_nodes = 0

        for node in nodes:
            if node.get('structural_class') == 'repeating_group':
                continue

            clamped_bbox = self._clamp_coordinates(node['bbox'])
            node_cx = clamped_bbox[0] + (clamped_bbox[2] / 2.0)

            nearest_dist = min(abs(node_cx - g) for g in grid)
            penalty_sum += nearest_dist / self.canvas_w
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
        Formula 3.15: cross-references each text node's bbox (B_t) against the
        SIFT/SURF-derived background Saliency Map (S) — text sitting over a
        visually busy background is penalized, regardless of its distance
        from the canvas margin (margin containment is already strictly
        enforced by the CSP solver itself, so it isn't duplicated here).

        Averaged across text nodes (rather than summed, as the raw pixel-sum
        in Formula 3.15 would be) to keep this term on the same ~[0, 1] scale
        as P_align/P_space/P_collision — otherwise, with alpha=50 weighting
        collision as the dominant term by design, an unnormalized sum here
        would silently swamp collision whenever it's near-zero (the CSP
        guarantees zero overlap by construction), which contradicts that
        design intent.
        """
        text_nodes = [n for n in nodes if n.get('structural_class') == 'text_node']
        if not text_nodes:
            return 0.0

        penalty_sum = sum(self._mean_saliency_in_bbox(n['bbox']) for n in text_nodes)
        return penalty_sum / len(text_nodes)

    def _mean_saliency_in_bbox(self, bbox):
        """
        Samples the saliency heatmap over the region a text node's bbox
        covers, scaling from canvas coordinates to the heatmap's native image
        dimensions. Returns a flat fallback density when no real per-image
        saliency map was supplied (synthetic-fallback pipeline runs).
        """
        if self.saliency_map is None:
            return self.fallback_saliency

        heatmap = self.saliency_map.get("heatmap") or []
        rows = len(heatmap)
        cols = len(heatmap[0]) if rows else 0
        if rows == 0 or cols == 0:
            return self.fallback_saliency

        img_w, img_h = self.saliency_map.get("image_wh", (self.canvas_w, self.canvas_h))
        scale_x = (img_w / self.canvas_w) if self.canvas_w > 0 else 1.0
        scale_y = (img_h / self.canvas_h) if self.canvas_h > 0 else 1.0

        x, y, w, h = bbox
        x0, y0 = x * scale_x, y * scale_y
        x1, y1 = (x + w) * scale_x, (y + h) * scale_y

        col_start = max(0, min(cols - 1, int((x0 / img_w) * cols))) if img_w > 0 else 0
        col_end   = max(0, min(cols - 1, int((x1 / img_w) * cols))) if img_w > 0 else 0
        row_start = max(0, min(rows - 1, int((y0 / img_h) * rows))) if img_h > 0 else 0
        row_end   = max(0, min(rows - 1, int((y1 / img_h) * rows))) if img_h > 0 else 0

        values = [
            heatmap[r][c]
            for r in range(row_start, row_end + 1)
            for c in range(col_start, col_end + 1)
        ]
        return (sum(values) / len(values)) if values else self.fallback_saliency

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