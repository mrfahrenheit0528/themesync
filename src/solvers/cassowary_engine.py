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

    def execute_relational_logic(self, instantiated_nodes):
        sorted_nodes = sorted(instantiated_nodes, key=lambda n: n['spatial_hierarchy'])
        
        singular_nodes = [n for n in sorted_nodes if n['structural_class'] != 'repeating_group']
        repeating_nodes = [n for n in sorted_nodes if n['structural_class'] == 'repeating_group']
        
        # 1. Apply Hard Constraints and Variable Initialization
        for node in sorted_nodes:
            node_id = node['node_id']
            tensor_w, tensor_h = node['bbox'][2], node['bbox'][3]
            current_var = self._initialize_node_variables(node_id, tensor_w, tensor_h)
            
            if node.get('constraint_type') == "Hard":
                # Isolate the human-edited coordinates and lock them strictly
                human_x, human_y = node['bbox'][0], node['bbox'][1]
                self.solver.addConstraint(current_var['left'] == human_x)
                self.solver.addConstraint(current_var['top'] == human_y)

        # 2. Compute Fluid Vertical Flow for Soft Singular Nodes
        for i, node in enumerate(singular_nodes):
            if node.get('constraint_type') == "Hard":
                continue # Bypass relational positioning for locked nodes
                
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
        
        print(f"Optimal Vertical Gap Calculated: {round(self.v_gap.value(), 2)} pixels")
        
        resolved_nodes = []
        for node in instantiated_nodes:
            v = self.variables[node['node_id']]
            node['bbox'][0] = round(v['left'].value(), 2)
            node['bbox'][1] = round(v['top'].value(), 2)
            resolved_nodes.append(node)
            
        return resolved_nodes

def test_state_ingestion():
    print("Executing Phase 2: State Synchronization and Recalculation...")
    engine = ConstraintSolverEngine()
    
    state_file = "data/processed/layout_state_v1_edited.json"
    
    if not os.path.exists(state_file):
        print(f"Error: {state_file} missing. Run state_manager.py first.")
        return
        
    try:
        with open(state_file, 'r') as f:
            edited_nodes = json.load(f)
            
        recalculated_nodes = engine.execute_relational_logic(edited_nodes)
        
        print("\nSpatial Coordinates Recalculated with Hard Constraints:")
        for n in recalculated_nodes:
            print(f" -> Node: {n['node_id']} | Computed [X, Y]: [{n['bbox'][0]}, {n['bbox'][1]}] | Constraint: {n.get('constraint_type', 'Soft')}")
            
    except Exception as e:
        print(f"Constraint Solver Failure: {e}")

if __name__ == "__main__":
    test_state_ingestion()