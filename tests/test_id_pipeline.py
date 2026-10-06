"""
ThemeSync — ID Card Pipeline Integration Test
==============================================
Validates the full end-to-end pipeline for the identification card domain
(A6-proportioned event ID, 744 × 1052 px).

Assertions:
  - All resolved nodes are within canvas boundaries
  - No overlapping bboxes between singular (non-repeating) nodes
  - All node IDs in the payload appear in the resolved output
  - Candidate ranking is sorted ascending by C_total

Run with:
  python tests/test_id_pipeline.py
"""

import sys
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ("models", "solvers", "renderers", "data_preprocessing"):
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CANVAS_W = 744
CANVAS_H = 1052
PAYLOAD  = os.path.join(_ROOT, "data", "raw", "id_payload.json")


# ---------------------------------------------------------------------------
# Shared pipeline runner
# ---------------------------------------------------------------------------

def _boxes_overlap(b1: list, b2: list) -> bool:
    """Returns True if two [x, y, w, h] boxes have any area overlap."""
    x1, y1, w1, h1 = b1
    x2, y2, w2, h2 = b2
    return not (
        x1 + w1 <= x2 or x2 + w2 <= x1 or
        y1 + h1 <= y2 or y2 + h2 <= y1
    )


def _run_id_pipeline(use_gnn: bool = True):
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

def test_all_id_nodes_within_canvas():
    resolved, ranked = _run_id_pipeline()
    # Check the ranked winner too, not just the first solve: the winner is
    # re-solved by the candidate explorer, which once silently used a
    # 1200x900 landscape canvas for IDs because it wasn't given the size.
    for node in resolved + ranked[0]["nodes"]:
        x, y, w, h = node["bbox"]
        assert x >= 0,              f"Node {node['node_id']} x={x} is off left edge"
        assert y >= 0,              f"Node {node['node_id']} y={y} is off top edge"
        assert x + w <= CANVAS_W + 1, f"Node {node['node_id']} overflows right edge ({x+w} > {CANVAS_W})"
        assert y + h <= CANVAS_H + 1, f"Node {node['node_id']} overflows bottom edge ({y+h} > {CANVAS_H})"
    print("  ✔  test_all_id_nodes_within_canvas passed")


def test_no_id_node_overlap():
    resolved, _ = _run_id_pipeline()
    singular = [n for n in resolved if n.get("structural_class") != "repeating_group"]
    overlaps = []
    for i in range(len(singular)):
        for j in range(i + 1, len(singular)):
            if _boxes_overlap(singular[i]["bbox"], singular[j]["bbox"]):
                overlaps.append((singular[i]["node_id"], singular[j]["node_id"]))
    assert len(overlaps) == 0, f"Overlapping ID card node pairs: {overlaps}"
    print("  ✔  test_no_id_node_overlap passed")


def test_all_payload_nodes_resolved():
    """Every variable_schema key in the payload must appear in the resolved output."""
    import json
    with open(PAYLOAD, "r") as f:
        payload = json.load(f)

    schema = payload.get("variable_schema", {})
    expected_ids = set()
    for var_name, props in schema.items():
        count = props.get("instantiation_count", 1)
        if count > 1:
            for i in range(count):
                expected_ids.add(f"{var_name}_{i}")
        else:
            expected_ids.add(var_name)

    resolved, _ = _run_id_pipeline()
    resolved_ids = {n["node_id"] for n in resolved}

    missing = expected_ids - resolved_ids
    assert len(missing) == 0, f"Missing node IDs in resolved output: {missing}"
    print(f"  ✔  test_all_payload_nodes_resolved passed ({len(resolved_ids)} nodes)")


def test_id_ranking_is_sorted():
    _, ranked = _run_id_pipeline()
    costs = [c["c_total"] for c in ranked]
    assert costs == sorted(costs), f"ID candidates not sorted by C_total: {costs}"
    print("  ✔  test_id_ranking_is_sorted passed")


def test_id_portrait_canvas():
    """Verify the pipeline correctly uses a portrait (H > W) canvas for ID cards."""
    assert CANVAS_H > CANVAS_W, (
        f"ID canvas should be portrait (H > W), got {CANVAS_W}×{CANVAS_H}"
    )
    resolved, _ = _run_id_pipeline()
    for node in resolved:
        x, y, w, h = node["bbox"]
        assert w <= CANVAS_W, f"Node {node['node_id']} width {w} exceeds portrait canvas width {CANVAS_W}"
    print(f"  ✔  test_id_portrait_canvas passed (canvas: {CANVAS_W}×{CANVAS_H} portrait)")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  ThemeSync — ID Card Pipeline Tests")
    print("=" * 60)

    failed = 0
    tests = [
        test_all_id_nodes_within_canvas,
        test_no_id_node_overlap,
        test_all_payload_nodes_resolved,
        test_id_ranking_is_sorted,
        test_id_portrait_canvas,
    ]

    for test_fn in tests:
        try:
            test_fn()
        except AssertionError as e:
            print(f"  ✘  {test_fn.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✘  {test_fn.__name__} ERROR: {type(e).__name__}: {e}")
            failed += 1

    print()
    if failed == 0:
        print("  All tests passed ✅")
    else:
        print(f"  {failed} test(s) failed ❌")
    print()
