import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models')))
from dynamic_instantiation import NodeInstantiator
from cassowary_engine import ConstraintSolverEngine

def execute_vertical_diagnostic():
    print("Initializing Phase 2: Cassowary Solver (Vertical ID Domain)...")
    
    # 1. Instantiate the nodes with CR80 baseline dimensions
    instantiator = NodeInstantiator(canvas_width=638, canvas_height=1014)
    payload_path = "data/raw/id_payload.json"
    
    if not os.path.exists(payload_path):
        print(f"Error: {payload_path} missing. Ensure the file is created.")
        return
        
    id_nodes = instantiator.instantiate_payload(payload_path)
    
    # 2. Execute the constraint solver using matching CR80 canvas limits
    engine = ConstraintSolverEngine(canvas_width=638, canvas_height=1014)
    
    try:
        resolved_nodes = engine.execute_relational_logic(id_nodes)
        
        print("\nSpatial Coordinates Recalculated for CR80 Vertical Canvas:")
        for n in resolved_nodes:
            print(f" -> Node: {n['node_id']} | Computed [X, Y]: [{n['bbox'][0]}, {n['bbox'][1]}] | Tensor [W, H]: [{n['bbox'][2]}, {n['bbox'][3]}]")
            
    except Exception as e:
        print(f"Constraint Solver Failure: {e}")

if __name__ == "__main__":
    execute_vertical_diagnostic()