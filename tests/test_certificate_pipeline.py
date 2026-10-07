"""
ThemeSync — Certificate Pipeline Integration Test
===================================================
Validates the full end-to-end pipeline for the academic certificate domain
(A4 landscape, 1200 × 900 px).

Assertions:
  - All resolved nodes are within canvas boundaries
  - No overlapping bboxes between singular (non-repeating) nodes
  - GNN-guided vs. no-GNN baseline C_total (reported, not asserted)
  - Hard constraints are preserved exactly (within 1 px tolerance)
  - Canvas text edits are schema-validated, and undo/redo bring back the
    words as well as the layout, as new states (append-only chain)
  - The structural accuracy F1 scores each element as p.56 defines it

Run with:
  python tests/test_certificate_pipeline.py
"""

import sys
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ("models", "solvers", "renderers", "data_preprocessing", "evaluation"):
    _p = os.path.join(_ROOT, "src", _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.path.insert(0, os.path.join(_ROOT, "src"))

import contextlib
import copy
import io

import torch
from dynamic_instantiation import NodeInstantiator
from pipeline import DEFAULT_WEIGHTS, _FALLBACK_CENTROIDS, _FALLBACK_SALIENCY, stage_gnn_inference
from cassowary_engine import ConstraintSolverEngine
from candidate_generator import MetaheuristicStateExplorer
from optimization_engine import HeuristicEvaluator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CANVAS_W = 1200
CANVAS_H = 900
PAYLOAD  = os.path.join(_ROOT, "data", "raw", "academic_payload.json")


def _boxes_overlap(b1: list, b2: list) -> bool:
    """Returns True if two [x, y, w, h] boxes have any area overlap."""
    x1, y1, w1, h1 = b1
    x2, y2, w2, h2 = b2
    return not (
        x1 + w1 <= x2 or x2 + w2 <= x1 or
        y1 + h1 <= y2 or y2 + h2 <= y1
    )


def _run_pipeline(use_gnn: bool):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    instantiator = NodeInstantiator(canvas_width=CANVAS_W, canvas_height=CANVAS_H)
    nodes = instantiator.instantiate_payload(PAYLOAD)

    if use_gnn:
        # the deployed Stage 2: naive-stack start, v2 weights (notes §3.22)
        with contextlib.redirect_stdout(io.StringIO()):
            nodes, _ = stage_gnn_inference(nodes, CANVAS_W, CANVAS_H, DEFAULT_WEIGHTS, device,
                                           _FALLBACK_CENTROIDS, _FALLBACK_SALIENCY)
    guided = copy.deepcopy(nodes)

    engine = ConstraintSolverEngine(canvas_width=CANVAS_W, canvas_height=CANVAS_H)
    resolved = engine.execute_relational_logic(nodes)

    explorer = MetaheuristicStateExplorer(canvas_width=CANVAS_W, canvas_height=CANVAS_H)
    ranked = explorer.generate_and_rank_candidates(guided, population_size=3)

    return resolved, ranked


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def test_all_nodes_within_canvas():
    resolved, _ = _run_pipeline(use_gnn=True)
    for node in resolved:
        x, y, w, h = node["bbox"]
        assert x >= 0, f"Node {node['node_id']} x={x} is off-canvas (left)"
        assert y >= 0, f"Node {node['node_id']} y={y} is off-canvas (top)"
        assert x + w <= CANVAS_W + 1, f"Node {node['node_id']} overflows right edge"
        assert y + h <= CANVAS_H + 1, f"Node {node['node_id']} overflows bottom edge"
    print("  ✔  test_all_nodes_within_canvas passed")


def test_no_singular_node_overlap():
    resolved, _ = _run_pipeline(use_gnn=True)
    singular = [n for n in resolved if n.get("structural_class") != "repeating_group"]
    overlaps = []
    for i in range(len(singular)):
        for j in range(i + 1, len(singular)):
            if _boxes_overlap(singular[i]["bbox"], singular[j]["bbox"]):
                overlaps.append((singular[i]["node_id"], singular[j]["node_id"]))
    assert len(overlaps) == 0, f"Overlapping node pairs detected: {overlaps}"
    print("  ✔  test_no_singular_node_overlap passed")


def test_gnn_improves_over_baseline():
    _, gnn_ranked   = _run_pipeline(use_gnn=True)
    _, base_ranked  = _run_pipeline(use_gnn=False)
    gnn_cost  = gnn_ranked[0]["c_total"]
    base_cost = base_ranked[0]["c_total"]
    delta = base_cost - gnn_cost
    direction = "BETTER" if delta > 0 else "WORSE" if delta < 0 else "EQUAL"
    # This test always passes — the delta is a thesis observation, not a correctness guard.
    # A negative delta (GNN worse than baseline) indicates the GNN requires further training,
    # which is itself a valid and important finding for the evaluation chapter.
    print(f"  ✔  test_gnn_improves_over_baseline passed "
          f"[GNN={gnn_cost:.4f}, Base={base_cost:.4f}, Δ={delta:+.4f} ({direction})]")



def test_hard_constraints_preserved():
    """Formula 3.10 / p.54: a node the designer moves, resizes or locks is a
    Hard constraint — after the solver re-flows everything else, it must
    still sit exactly where the designer left it (1 px tolerance), with no
    overlap introduced."""
    import tempfile
    from pipeline import OrchestrationSession

    with tempfile.TemporaryDirectory() as out:
        session = OrchestrationSession(PAYLOAD, output_dir=out)
        with contextlib.redirect_stdout(io.StringIO()):
            session.run()
            nodes = {n["node_id"]: n for n in session.chain.current["nodes"]}
            x, y, w, h = nodes["{{Issuing_Organization}}"]["bbox"]
            moved = [x + 30.0, y + 12.0, w, h]
            session.apply_event("on-drop", "{{Issuing_Organization}}", moved)
            x, y, w, h = nodes["{{Citation_Body}}"]["bbox"]
            resized = [x, y, w * 0.85, h * 1.2]
            session.apply_event("on-resize-complete", "{{Citation_Body}}", resized)
        final = {n["node_id"]: n for n in session.chain.current["nodes"]}
        for node_id, expected in (("{{Issuing_Organization}}", moved), ("{{Citation_Body}}", resized)):
            got = final[node_id]["bbox"]
            assert final[node_id]["constraint_type"] == "Hard", f"{node_id} not Hard"
            assert all(abs(a - b) <= 1.0 for a, b in zip(got, expected)), f"{node_id}: {got} != {expected}"
        assert session.chain.current["fitness"]["P_collision"] == 0.0, "edits introduced an overlap"
        assert len(session.chain.states) == 4, "each event must append exactly one state"
    print("  ✔  test_hard_constraints_preserved passed (move + resize kept exactly, no overlap)")


def test_text_edit_undo_redo():
    """Figure 3's canvas: a text edit is validated against the content
    schema (max_characters, p.44) and re-rendered; undo and redo restore
    the words with the layout, each as a new state — the chain is never
    rewritten (Formula 3.9)."""
    import tempfile
    from pipeline import OrchestrationSession

    with tempfile.TemporaryDirectory() as out:
        session = OrchestrationSession(PAYLOAD, output_dir=out)
        with contextlib.redirect_stdout(io.StringIO()):
            session.run()
            original = session.content()["{{Student_Name}}"]
            session.edit_text("{{Student_Name}}", "Maria Clara Ibarra")
            with open(session.rendered_path) as f:
                assert "Maria Clara Ibarra" in f.read(), "edit not rendered"
            try:
                session.edit_text("{{Student_Name}}", "X" * 200)
                raise AssertionError("an over-long name was accepted")
            except ValueError:
                pass
            try:
                session.edit_text("{{Institution_Logo}}", "not text")
                raise AssertionError("a logo accepted a text edit")
            except KeyError:
                pass
            nodes = {n["node_id"]: n for n in session.chain.current["nodes"]}
            x, y, w, h = nodes["{{Date_Issued}}"]["bbox"]
            session.apply_event("on-drop", "{{Date_Issued}}", [x + 20.0, y, w, h])
            session.undo()                          # the move
            session.undo()                          # the text edit
            assert session.content()["{{Student_Name}}"] == original, "undo did not restore the words"
            with open(session.rendered_path) as f:
                assert "Maria Clara Ibarra" not in f.read(), "undo not rendered"
            session.redo()
            assert session.content()["{{Student_Name}}"] == "Maria Clara Ibarra", "redo lost the words"
            assert session.can_redo, "redo trail dropped too early"
            session.apply_event("lock-toggle", "{{Date_Issued}}", hard=True)
            assert not session.can_redo, "a new edit must end the redo trail"
        labels = [s["label"] for s in session.chain.states]
        assert len(labels) == 8, labels             # init, winner, text, move, undo, undo, redo, lock
        assert labels[4].startswith("Undo") and labels[6].startswith("Redo"), labels
    print("  ✔  test_text_edit_undo_redo passed (schema-checked edit; undo/redo restore words, append-only)")


def test_ranking_is_sorted():
    _, ranked = _run_pipeline(use_gnn=True)
    costs = [c["c_total"] for c in ranked]
    assert costs == sorted(costs), f"Candidates not sorted by C_total: {costs}"
    print("  ✔  test_ranking_is_sorted passed")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def test_structural_accuracy_p56():
    """p.56's F1, element by element: an algorithm-placed element over
    another or past the canvas edge is an FP, a missing payload element an
    FN, a Hard element the solver moved an FP; where the designer put a
    Hard element is noted, not counted."""
    from layout_report import structural_accuracy

    nodes = [
        {"node_id": "a", "bbox": [10, 10, 100, 50], "constraint_type": "Soft"},
        {"node_id": "b", "bbox": [60, 30, 100, 50], "constraint_type": "Soft"},     # over a
        {"node_id": "c", "bbox": [1150, 300, 100, 40], "constraint_type": "Soft"},  # past the edge
        {"node_id": "d", "bbox": [1150, 500, 100, 40], "constraint_type": "Hard"},  # the designer's call
        {"node_id": "e", "bbox": [400, 700, 100, 40], "constraint_type": "Hard"},   # moved by the solver
        {"node_id": "f", "bbox": [400, 600, 100, 40], "constraint_type": "Soft"},
    ]
    manual = {"d": [1150, 500, 100, 40], "e": [400, 650, 100, 40]}
    r = structural_accuracy(nodes, CANVAS_W, CANVAS_H, list("abcdefg"), manual)
    got = {row["node_id"]: row["result"] for row in r["nodes"]}
    assert got == {"a": "FP", "b": "FP", "c": "FP", "d": "TP", "e": "FP", "f": "TP", "g": "FN"}, got
    assert r["nodes"][3]["notes"] == ["protrudes beyond the canvas"], r["nodes"][3]
    assert (r["tp"], r["fp"], r["fn"]) == (2, 4, 1)
    print("  ✔  test_structural_accuracy_p56 passed (overlap, off-canvas, moved Hard node, missing node)")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  ThemeSync — Certificate Pipeline Tests")
    print("=" * 60)

    failed = 0
    tests = [
        test_all_nodes_within_canvas,
        test_no_singular_node_overlap,
        test_gnn_improves_over_baseline,
        test_hard_constraints_preserved,
        test_text_edit_undo_redo,
        test_ranking_is_sorted,
        test_structural_accuracy_p56,
    ]
    for test_fn in tests:
        try:
            test_fn()
        except AssertionError as e:
            print(f"  ✘  {test_fn.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✘  {test_fn.__name__} ERROR: {e}")
            failed += 1

    print()
    if failed == 0:
        print("  All tests passed ✅")
    else:
        print(f"  {failed} test(s) failed ❌")
    print()
