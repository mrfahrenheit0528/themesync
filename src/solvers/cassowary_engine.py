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
        
        # Registry to detect overlapping Hard Constraints
        locked_coordinates = set()
        
        # 1. Apply Hard Constraints and Variable Initialization
        for node in sorted_nodes:
            node_id = node['node_id']
            tensor_w = node['bbox'][2]
            
            # Dynamically recalculate height to prevent text overflow
            tensor_h = self._calculate_dynamic_height(node, tensor_w, node['bbox'][3])
            
            current_var = self._initialize_node_variables(node_id, tensor_w, tensor_h)
            
            if node.get('constraint_type') == "Hard":
                human_x, human_y = node['bbox'][0], node['bbox'][1]
                coord_key = f"{human_x}_{human_y}"
                
                # Spatial Conflict Resolution
                if coord_key in locked_coordinates:
                    print(f"Warning: Hard Constraint Collision detected for {node_id} at [{human_x}, {human_y}]. Applying spatial offset.")
                    # Offset the node and downgrade to a strong soft constraint to prevent a solver crash
                    self.solver.addConstraint((current_var['left'] == human_x + 20) | kiwi.strength.strong)
                    self.solver.addConstraint((current_var['top'] == human_y + tensor_h + 10) | kiwi.strength.strong)
                else:
                    self.solver.addConstraint(current_var['left'] == human_x)
                    self.solver.addConstraint(current_var['top'] == human_y)
                    locked_coordinates.add(coord_key)

        # 2. Compute Fluid Vertical Flow for Soft Singular Nodes
        for i, node in enumerate(singular_nodes):
            if node.get('constraint_type') == "Hard":
                continue 
                
            node_id = node['node_id']
            current_var = self.variables[node_id]
            tensor_w = node['bbox'][2]
            
            center_x = (self.canvas_w - tensor_w) / 2
            self.solver.addConstraint(current_var['left'] == center_x)
            
            if i == 0:
                self.solver.addConstraint(current_var['top'] == 40)
            else:
                prev_var = self.variables[singular_nodes[i-1]['node_id']]
                self.solver.addConstraint(current_var['top'] >= prev_var['bottom'] + self.v_gap)

        # 3. Compute Horizontal Distribution for Soft Repeating Groups
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
                    self.solver.addConstraint(current_var['top'] >= last_singular_var['bottom'] + self.v_gap)
                
                self.solver.addConstraint(current_var['left'] == current_x)
                current_x += (tensor_w + gap)

        self.solver.updateVariables()
        
        resolved_nodes = []
        for node in instantiated_nodes:
            v = self.variables[node['node_id']]
            node['bbox'][0] = round(v['left'].value(), 2)
            node['bbox'][1] = round(v['top'].value(), 2)
            # Serialize the potentially recalculated dynamic height
            node['bbox'][3] = round(v['bottom'].value() - v['top'].value(), 2) 
            resolved_nodes.append(node)
            
        return resolved_nodes