import json
import os
import sys

# Explicitly map the solvers directory to the system path for cross-module execution
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'solvers')))

class StateManager:
    def __init__(self, state_dir="data/processed"):
        """Initializes the directory for layout state tracking."""
        self.state_dir = state_dir
        os.makedirs(self.state_dir, exist_ok=True)

    def serialize_state(self, resolved_nodes, version="v1"):
        """
        Exports the computed tensors to a JSON state file.
        This serves as the rendering payload and the baseline for human edits.
        """
        filepath = os.path.join(self.state_dir, f"layout_state_{version}.json")
        with open(filepath, 'w') as f:
            json.dump(resolved_nodes, f, indent=4)
        print(f"State version {version} successfully serialized to {filepath}")
        return filepath

    def simulate_human_intervention(self, filepath, target_node_id, manual_x, manual_y):
        """
        Simulates a designer manually moving an element in the UI.
        Mutates the node's constraint priority to strictly override the solver.
        """
        with open(filepath, 'r') as f:
            nodes = json.load(f)

        for node in nodes:
            if node['node_id'] == target_node_id:
                # Apply the manual coordinates
                node['bbox'][0] = manual_x
                node['bbox'][1] = manual_y
                # Elevate the constraint priority to prevent the solver from overwriting it
                node['constraint_type'] = "Hard"
                print(f"Human Edit Applied: {target_node_id} locked to [{manual_x}, {manual_y}] as a Hard Constraint.")
                break

        updated_filepath = filepath.replace(".json", "_edited.json")
        with open(updated_filepath, 'w') as f:
            json.dump(nodes, f, indent=4)
            
        return updated_filepath

def test_state_machine():
    from cassowary_engine import ConstraintSolverEngine
    from dynamic_instantiation import NodeInstantiator
    
    print("Initializing Phase 2: State Synchronization...")
    
    # 1. Run initial solver
    instantiator = NodeInstantiator()
    engine = ConstraintSolverEngine()
    raw_nodes = instantiator.instantiate_payload("data/raw/academic_payload.json")
    resolved_nodes = engine.execute_relational_logic(raw_nodes)
    
    # 2. Serialize initial state
    manager = StateManager()
    baseline_file = manager.serialize_state(resolved_nodes, version="v1")
    
    # 3. Simulate human intervention (e.g., Designer moves Logo to the top-left corner)
    print("\nSimulating Human-in-the-Loop Intervention...")
    manager.simulate_human_intervention(baseline_file, "{{Institution_Logo}}", manual_x=40.0, manual_y=40.0)

if __name__ == "__main__":
    test_state_machine()