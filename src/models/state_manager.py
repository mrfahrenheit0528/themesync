import json
import os
import sys
import datetime
from enum import Enum, auto

# Explicitly map the solvers directory to the system path for cross-module execution
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'solvers')))


# ---------------------------------------------------------------------------
# LayoutFSM — Finite State Machine (as specified in the ThemeSync manuscript)
# ---------------------------------------------------------------------------
# States:    IDLE → INSTANTIATION → GNN_PREDICTION → CSP_RESOLUTION → RENDERING
# Transitions are strictly guarded: illegal jumps raise a RuntimeError.
# ---------------------------------------------------------------------------

class LayoutState(Enum):
    IDLE            = auto()
    INSTANTIATION   = auto()
    GNN_PREDICTION  = auto()
    CSP_RESOLUTION  = auto()
    RENDERING       = auto()

# Define legal one-way transitions (source → set of allowed targets)
_LEGAL_TRANSITIONS = {
    LayoutState.IDLE:           {LayoutState.INSTANTIATION},
    LayoutState.INSTANTIATION:  {LayoutState.GNN_PREDICTION, LayoutState.CSP_RESOLUTION},
    LayoutState.GNN_PREDICTION: {LayoutState.CSP_RESOLUTION},
    LayoutState.CSP_RESOLUTION: {LayoutState.RENDERING, LayoutState.INSTANTIATION},
    LayoutState.RENDERING:      {LayoutState.IDLE},  # Allows reset / re-run
}


class LayoutFSM:
    """
    Formal 5-state Finite State Machine governing the ThemeSync orchestration lifecycle.

    State diagram (from manuscript, Chapter 3):
        IDLE
          └─► INSTANTIATION
                ├─► GNN_PREDICTION
                │     └─► CSP_RESOLUTION
                │           ├─► RENDERING ──► IDLE  (normal completion)
                │           └─► INSTANTIATION       (human-in-the-loop re-run)
                └─► CSP_RESOLUTION  (when GNN is disabled / baseline mode)
    """

    def __init__(self):
        self._state: LayoutState = LayoutState.IDLE
        self._history: list[dict] = []
        self._log_transition(None, self._state, event="INIT")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> LayoutState:
        """Returns the current FSM state."""
        return self._state

    @property
    def state_name(self) -> str:
        """Returns the current state as a human-readable string."""
        return self._state.name

    def transition(self, target: LayoutState, event: str = "") -> None:
        """
        Executes a guarded state transition.

        Parameters
        ----------
        target : LayoutState
            The target state to transition to.
        event : str
            A descriptive label for the triggering event (for history logging).

        Raises
        ------
        RuntimeError
            If the transition from the current state to the target is not defined
            in the legal transition table.
        """
        allowed = _LEGAL_TRANSITIONS.get(self._state, set())
        if target not in allowed:
            raise RuntimeError(
                f"[LayoutFSM] Illegal transition: {self._state.name} → {target.name}. "
                f"Allowed targets from '{self._state.name}': "
                f"{[s.name for s in allowed] or 'none (terminal state)'}"
            )
        prev = self._state
        self._state = target
        self._log_transition(prev, target, event=event)

    def reset(self) -> None:
        """
        Resets the FSM to IDLE unconditionally.
        Used when starting a completely new orchestration session.
        """
        prev = self._state
        self._state = LayoutState.IDLE
        self._log_transition(prev, LayoutState.IDLE, event="RESET")

    def get_state_history(self) -> list[dict]:
        """
        Returns the full timestamped transition history for this FSM instance.

        Returns
        -------
        list[dict]
            Each entry contains:
              - 'timestamp'  : ISO-8601 string
              - 'from_state' : name of the previous state (or None at INIT)
              - 'to_state'   : name of the new state
              - 'event'      : event label string
        """
        return list(self._history)

    def print_history(self) -> None:
        """Prints the full transition history to stdout in a readable format."""
        print("\n  LayoutFSM — Transition History")
        print(f"  {'#':<4} {'Timestamp':<26} {'From':<18} {'→'} {'To':<18} Event")
        print(f"  {'-'*4} {'-'*26} {'-'*18} {'-'} {'-'*18} {'-'*20}")
        for i, entry in enumerate(self._history):
            frm = entry["from_state"] or "—"
            print(
                f"  {i:<4} {entry['timestamp']:<26} {frm:<18} → "
                f"{entry['to_state']:<18} {entry['event']}"
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log_transition(self, from_state, to_state: LayoutState, event: str) -> None:
        self._history.append({
            "timestamp":  datetime.datetime.now().isoformat(timespec="milliseconds"),
            "from_state": from_state.name if from_state else None,
            "to_state":   to_state.name,
            "event":      event,
        })


# ---------------------------------------------------------------------------
# StateChain — the immutable JSON state chain (Formulas 3.9-3.10)
# ---------------------------------------------------------------------------

class StateChain:
    """
    The Bi-directional State Machine's serialized history (Chapter 3,
    pp. 42-43; Figure 3's "State Timeline (JSON Sync)"): an append-only list
    of canvas states.

    Each designer action is one discrete, terminal event e_t — on-drop,
    on-resize-complete, or a lock toggle, never a drag stream — producing
    S_{t+1} = δ(S_t, e_t) (Formula 3.9). Every state records which nodes are
    Hard (manually adjusted, U_manual) and which are Soft (algorithmic,
    A_algorithmic) (Formula 3.10). No state is ever overwritten; restoring an
    earlier canvas appends a new state that copies it, so the history itself
    is never rewritten either. Serializes to and loads from JSON.
    """

    def __init__(self, states: list = None):
        self.states = list(states or [])

    def append(self, label: str, event: dict, nodes: list, fitness: dict = None, **extra) -> dict:
        import copy
        state = {
            "state_id":   f"State_{len(self.states):02d}",
            "label":      label,
            "timestamp":  datetime.datetime.now().isoformat(timespec="milliseconds"),
            "event":      dict(event or {}),
            "nodes":      copy.deepcopy(nodes),
            "fitness":    dict(fitness) if fitness else None,
            "hard_nodes": [n["node_id"] for n in nodes if n.get("constraint_type") == "Hard"],
        }
        state.update(extra)
        self.states.append(state)
        return state

    @property
    def current(self) -> dict:
        return self.states[-1] if self.states else None

    def to_json(self) -> str:
        return json.dumps({"state_chain": self.states}, indent=2)

    def save(self, path: str) -> str:
        """Writes the chain to a temporary file, then swaps it in: a failed
        write (a full disk, 2026-10-07) leaves the previous chain intact
        instead of a truncated file."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = f"{path}.tmp"
        try:
            with open(tmp, "w") as f:
                f.write(self.to_json())
            os.replace(tmp, path)
        except OSError:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
        return path

    @classmethod
    def load(cls, path: str) -> "StateChain":
        with open(path) as f:
            return cls(json.load(f)["state_chain"])


# ---------------------------------------------------------------------------
# StateManager — serialization and human-in-the-loop helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_fsm():
    """Validates all legal transitions and one illegal transition guard."""
    print("\nTesting LayoutFSM...")
    fsm = LayoutFSM()
    assert fsm.state == LayoutState.IDLE

    fsm.transition(LayoutState.INSTANTIATION, event="payload_loaded")
    fsm.transition(LayoutState.GNN_PREDICTION, event="graph_built")
    fsm.transition(LayoutState.CSP_RESOLUTION, event="gnn_inferred")
    fsm.transition(LayoutState.RENDERING, event="constraints_resolved")
    fsm.transition(LayoutState.IDLE, event="render_complete")

    # Test illegal transition guard
    try:
        fsm.transition(LayoutState.GNN_PREDICTION, event="should_fail")
        raise AssertionError("Guard failed: illegal transition was allowed!")
    except RuntimeError as e:
        print(f"  ✔  Illegal transition correctly blocked: {e}")

    fsm.print_history()
    print("  ✔  FSM test passed.\n")


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
    test_fsm()
    test_state_machine()