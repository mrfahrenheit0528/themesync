import kiwisolver as kiwi
import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models')))
from dynamic_instantiation import NodeInstantiator

class ConstraintSolverEngine:
    def __init__(self, canvas_width=1200, canvas_height=900, margin=50.0, default_vgap=16.0):
        self.canvas_w = float(canvas_width)
        self.canvas_h = float(canvas_height)
        self.margin_x = float(margin)
        self.margin_y = float(margin)
        self.default_vgap = float(default_vgap)
        self.solver = kiwi.Solver()
        self.variables = {}

    def _initialize_node_variables(self, node_id, width, height):
        v = {
            'left': kiwi.Variable(f"{node_id}_left"),
            'top': kiwi.Variable(f"{node_id}_top"),
            'right': kiwi.Variable(f"{node_id}_right"),
            'bottom': kiwi.Variable(f"{node_id}_bottom"),
        }
        self.variables[node_id] = v
        
        # Dimensions are exact for the given tensor
        self.solver.addConstraint(v['right'] == v['left'] + width)
        self.solver.addConstraint(v['bottom'] == v['top'] + height)
        
        # Margins & boundary containment
        self.solver.addConstraint((v['left'] >= self.margin_x) | kiwi.strength.strong)
        self.solver.addConstraint((v['top'] >= self.margin_y) | kiwi.strength.strong)
        self.solver.addConstraint((v['right'] <= self.canvas_w - self.margin_x) | kiwi.strength.strong)
        self.solver.addConstraint((v['bottom'] <= self.canvas_h - self.margin_y) | kiwi.strength.strong)
        
        return v

    def execute_relational_logic(self, instantiated_nodes):
        self.solver = kiwi.Solver()
        self.variables = {}
        
        self.v_gap = kiwi.Variable('vertical_gap')
        self.solver.addConstraint(self.v_gap >= 6.0)
        self.solver.addConstraint((self.v_gap == self.default_vgap) | kiwi.strength.medium)

        sorted_nodes = sorted(instantiated_nodes, key=lambda n: n['spatial_hierarchy'])
        singular_nodes = [n for n in sorted_nodes if n.get('structural_class') != 'repeating_group']
        repeating_nodes = [n for n in sorted_nodes if n.get('structural_class') == 'repeating_group']
        
        locked_coordinates = set()
        
        # 1. Singular Nodes Initialization and Centering
        for node in singular_nodes:
            node_id = node['node_id']
            tensor_w = float(node['bbox'][2])
            tensor_h = float(node['bbox'][3])
            
            current_var = self._initialize_node_variables(node_id, tensor_w, tensor_h)
            human_x, human_y = float(node['bbox'][0]), float(node['bbox'][1])
            coord_key = f"{human_x}_{human_y}"
            
            if node.get('constraint_type') == "Hard":
                self.solver.addConstraint(current_var['left'] == human_x)
                self.solver.addConstraint(current_var['top'] == human_y)
                locked_coordinates.add(coord_key)
            elif node.get('gnn_predicted', False):
                # Honor the GNN's spatial prediction as the primary soft preference
                # for both axes. Strength is `medium` — strong enough to actually
                # win (nothing else competes for x/y at this tier), but still
                # yields to margins/containment and the non-overlap stacking
                # order, which stay at `strong`/`required`.
                self.solver.addConstraint((current_var['left'] == human_x) | kiwi.strength.medium)
                self.solver.addConstraint((current_var['top'] == human_y) | kiwi.strength.medium)
            else:
                # No GNN prediction available (baseline mode) — fall back to
                # center alignment for x; y is left to the stacking order below.
                target_center_x = max(self.margin_x, (self.canvas_w - tensor_w) / 2.0)
                self.solver.addConstraint((current_var['left'] == target_center_x) | kiwi.strength.medium)

        # 2. Strict Top-to-Bottom Stacking (Non-Overlap)
        for i in range(1, len(singular_nodes)):
            curr_var = self.variables[singular_nodes[i]['node_id']]
            prev_var = self.variables[singular_nodes[i-1]['node_id']]
            self.solver.addConstraint((curr_var['top'] >= prev_var['bottom'] + self.v_gap) | kiwi.strength.strong)

        # 3. Repeating Groups (Signature Blocks)
        if repeating_nodes:
            count = len(repeating_nodes)
            total_w = sum(float(n['bbox'][2]) for n in repeating_nodes)
            avail_w = max(0.0, self.canvas_w - (2.0 * self.margin_x))
            gap = max(15.0, (avail_w - total_w) / (count + 1))
            
            first_rep_var = None
            for i, node in enumerate(repeating_nodes):
                node_id = node['node_id']
                tensor_w = float(node['bbox'][2])
                tensor_h = float(node['bbox'][3])
                
                current_var = self._initialize_node_variables(node_id, tensor_w, tensor_h)
                
                if first_rep_var is None:
                    first_rep_var = current_var
                else:
                    self.solver.addConstraint((current_var['top'] == first_rep_var['top']) | kiwi.strength.strong)

                if node.get('constraint_type') == "Hard":
                    human_x, human_y = float(node['bbox'][0]), float(node['bbox'][1])
                    self.solver.addConstraint(current_var['left'] == human_x)
                    self.solver.addConstraint(current_var['top'] == human_y)
                else:
                    # Distribute repeating nodes evenly across the width
                    target_x = self.margin_x + gap + (i * (tensor_w + gap))
                    self.solver.addConstraint((current_var['left'] == target_x) | kiwi.strength.strong)
                    self.solver.addConstraint((current_var['bottom'] <= self.canvas_h - self.margin_y) | kiwi.strength.strong)
                
                # Must be strictly below the last singular element
                if singular_nodes:
                    last_singular_var = self.variables[singular_nodes[-1]['node_id']]
                    self.solver.addConstraint((current_var['top'] >= last_singular_var['bottom'] + self.v_gap) | kiwi.strength.strong)

        self.solver.updateVariables()
        
        resolved_nodes = []
        for node in instantiated_nodes:
            v = self.variables[node['node_id']]
            node['bbox'][0] = round(v['left'].value(), 2)
            node['bbox'][1] = round(v['top'].value(), 2)
            node['bbox'][3] = round(v['bottom'].value() - v['top'].value(), 2) 
            resolved_nodes.append(node)
            
        return resolved_nodes