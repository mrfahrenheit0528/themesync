import kiwisolver as kiwi
import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models')))
from dynamic_instantiation import NodeInstantiator

class ConstraintSolverEngine:
    def __init__(self, canvas_width=1200, canvas_height=900):
        self.solver = kiwi.Solver()
        self.canvas_w = canvas_width
        self.canvas_h = canvas_height
        self.variables = {}
        
        self.v_gap = kiwi.Variable('vertical_gap')
        self.solver.addConstraint(self.v_gap >= 5)
        self.solver.addConstraint((self.v_gap == 15) | kiwi.strength.strong)

    def _initialize_node_variables(self, node_id, width, height):
        v = {
            'left': kiwi.Variable(f"{node_id}_left"),
            'top': kiwi.Variable(f"{node_id}_top"),
            'right': kiwi.Variable(f"{node_id}_right"),
            'bottom': kiwi.Variable(f"{node_id}_bottom"),
        }
        self.variables[node_id] = v
        
        self.solver.addConstraint(v['right'] == v['left'] + width)
        self.solver.addConstraint(v['bottom'] == v['top'] + height)
        
        self.solver.addConstraint(v['left'] >= 0)
        self.solver.addConstraint(v['top'] >= 0)
        self.solver.addConstraint(v['right'] <= self.canvas_w)
        self.solver.addConstraint(v['bottom'] <= self.canvas_h)
        
        return v

    def _calculate_dynamic_height(self, node, tensor_w, tensor_h):
        """
        Calculates vertical tensor wrapping if the maximum character limit
        exceeds the estimated horizontal capacity.
        """
        # Retrieve max_characters if it exists in the payload mapping
        max_chars = node.get('max_characters', 0)
        if max_chars > 0 and node.get('structural_class') == 'text_node':
            # Heuristic: Assume average character width is 12 pixels
            estimated_text_width = max_chars * 12.0
            if estimated_text_width > tensor_w:
                rows_required = int((estimated_text_width // tensor_w) + 1)
                # Expand the mathematical height to accommodate the wrapped rows
                return tensor_h * rows_required
        return tensor_h

    def execute_relational_logic(self, instantiated_nodes):
        sorted_nodes = sorted(instantiated_nodes, key=lambda n: n['spatial_hierarchy'])
        
        singular_nodes = [n for n in sorted_nodes if n['structural_class'] != 'repeating_group']
        repeating_nodes = [n for n in sorted_nodes if n['structural_class'] == 'repeating_group']
        
        locked_coordinates = set()
        
        # 1. Initialization and Dynamic Height Calculation
        for node in sorted_nodes:
            node_id = node['node_id']
            tensor_w = node['bbox'][2]
            tensor_h = self._calculate_dynamic_height(node, tensor_w, node['bbox'][3])
            
            current_var = self._initialize_node_variables(node_id, tensor_w, tensor_h)
            
            human_x, human_y = node['bbox'][0], node['bbox'][1]
            coord_key = f"{human_x}_{human_y}"
            
            if node.get('constraint_type') == "Hard":
                if coord_key in locked_coordinates:
                    self.solver.addConstraint((current_var['left'] == human_x + 20) | kiwi.strength.strong)
                    self.solver.addConstraint((current_var['top'] == human_y + tensor_h + 10) | kiwi.strength.strong)
                else:
                    self.solver.addConstraint(current_var['left'] == human_x)
                    self.solver.addConstraint(current_var['top'] == human_y)
                    locked_coordinates.add(coord_key)
            else:
                # 2. THE CORRECTION: Ingest GNN predictions as medium-strength pull constraints
                # This mathematically encourages the solver to respect the neural prediction
                self.solver.addConstraint((current_var['left'] == human_x) | kiwi.strength.medium)
                self.solver.addConstraint((current_var['top'] == human_y) | kiwi.strength.medium)

        # 3. Enforce Strict Non-Overlap (Strong Constraints)
        for i in range(1, len(singular_nodes)):
            curr_var = self.variables[singular_nodes[i]['node_id']]
            prev_var = self.variables[singular_nodes[i-1]['node_id']]
            
            # Prevent occlusion, but allow the GNN's vertical gaps to dictate the final placement
            self.solver.addConstraint((curr_var['top'] >= prev_var['bottom'] + self.v_gap) | kiwi.strength.strong)

        # 4. Compute Horizontal Distribution for Soft Repeating Groups
        if repeating_nodes:
            count = len(repeating_nodes)
            total_w = sum(n['bbox'][2] for n in repeating_nodes)
            gap = (self.canvas_w - total_w) / (count + 1)
            
            current_x = gap
            for i, node in enumerate(repeating_nodes):
                if node.get('constraint_type') == "Hard":
                    continue
                    
                node_id = node['node_id']
                current_var = self.variables[node_id]
                tensor_w = node['bbox'][2]
                
                self.solver.addConstraint(current_var['bottom'] <= self.canvas_h - 40)
                
                if singular_nodes:
                    last_singular_var = self.variables[singular_nodes[-1]['node_id']]
                    self.solver.addConstraint((current_var['top'] >= last_singular_var['bottom'] + self.v_gap) | kiwi.strength.strong)
                
                self.solver.addConstraint((current_var['left'] == current_x) | kiwi.strength.weak)
                current_x += (tensor_w + gap)

        self.solver.updateVariables()
        
        resolved_nodes = []
        for node in instantiated_nodes:
            v = self.variables[node['node_id']]
            node['bbox'][0] = round(v['left'].value(), 2)
            node['bbox'][1] = round(v['top'].value(), 2)
            node['bbox'][3] = round(v['bottom'].value() - v['top'].value(), 2) 
            resolved_nodes.append(node)
            
        return resolved_nodes