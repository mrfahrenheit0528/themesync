"""
ThemeSync — Layout Evaluation Report
=====================================
Scores one finished layout, the one a designer leaves on the dashboard's
canvas, against the evaluation metrics of Chapter 3 (pp. 55-58). It feeds
the dashboard's Step 3 (src/dashboard/views/report.py); evaluate.py uses
the same F1.

  - Heuristic fitness (Formula 3.11): the four penalties, weighted, for the
    designer's layout next to ThemeSync's recommendation, and its rank
    among the ranked candidates.
  - Structural accuracy (F1, p.56), node by node:
      TP  a payload node placed with no collision and inside the canvas,
          and, if Hard, still where the designer left it;
      FP  a node the algorithm placed that overlaps another (a locked one
          included) or protrudes beyond the canvas, or a Hard node the
          solver moved;
      FN  a node the content payload mandates that is missing.
    Where the designer put a Hard node is their call, not the algorithm's:
    a Hard node overlapping or off the canvas is noted, not counted.
  - Non-destructive refinement (pp.42-43, p.54): every re-solve in the
    state chain is checked; each manual edit in effect must survive it.
  - Algorithmic latency (p.55): the pipeline's stages and every
    human-in-the-loop event, in ms.
  - Hybrid Visual DNA correctness (pp.42-43): the K-Means elbow (WCSS per
    k) and the schema validations.

IoU (p.55) needs ground-truth boxes and MOS (pp.57-58) needs experts, so
neither applies to one user's layout: they are Phase 1 and Phase 4
measures.
"""

import datetime
import os
import statistics

from optimization_engine import HeuristicEvaluator

TOLERANCE_PX = 1.0   # solver float noise: boxes that touch don't overlap
EDIT_EVENTS = ("on-drop", "on-resize-complete", "lock-toggle")
RESTORE_EVENTS = ("restore", "undo", "redo")

# Formula 3.11's terms: (label, metrics key, weight attribute, formula)
FITNESS_TERMS = [("Collision", "P_collision", "alpha", "3.12"),
                 ("Alignment", "P_align", "beta", "3.13"),
                 ("Whitespace", "P_space", "gamma", "3.14"),
                 ("Legibility", "P_legibility", "delta", "3.15")]


def node_name(node: dict) -> str:
    if node.get("structural_class") == "decor":
        return f"Motif {int(node['node_id'].rsplit('_', 1)[1]) + 1}"
    return node["node_id"].replace("{", "").replace("}", "").replace("_", " ").strip()


def _box(values) -> list:
    return [round(float(v), 1) for v in values]


def _overlap(a: list, b: list) -> float:
    """Overlapping area of two [x, y, w, h] boxes; 0 when they only touch."""
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return w * h if w > TOLERANCE_PX and h > TOLERANCE_PX else 0.0


def _outside(box: list, canvas_w: float, canvas_h: float) -> bool:
    x, y, w, h = box
    return (x < -TOLERANCE_PX or y < -TOLERANCE_PX
            or x + w > canvas_w + TOLERANCE_PX or y + h > canvas_h + TOLERANCE_PX)


# ---------------------------------------------------------------------------
# Manual edits through the state chain
# ---------------------------------------------------------------------------

def manual_boxes(states: list) -> list:
    """
    For each state in the chain, node id → the box the designer gave it
    (moved, resized or locked there), as in effect at that state. Restore,
    undo and redo bring back an earlier state's edits; choosing a candidate
    starts again from its fresh, all-Soft layout.
    """
    index = {s["state_id"]: i for i, s in enumerate(states)}
    history = []
    for state in states:
        event = state.get("event") or {}
        kind = event.get("type")
        current = dict(history[-1]) if history else {}
        if kind in EDIT_EVENTS:
            if event.get("constraint_type") == "Hard":
                current[event["node_id"]] = [float(v) for v in event["after"]]
            else:
                current.pop(event["node_id"], None)
        elif kind in RESTORE_EVENTS and event.get("restored") in index:
            current = dict(history[index[event["restored"]]])
        elif kind in ("init", "candidate"):
            current = {}
        history.append(current)
    return history


def retention_check(states: list, history: list = None) -> dict:
    """Every re-solve (a move, resize or lock) must leave every manual edit
    in effect exactly where the designer put it (1 px)."""
    history = history or manual_boxes(states)
    resolves, checked, violations = 0, 0, []
    for state, manual in zip(states, history):
        if (state.get("event") or {}).get("type") not in EDIT_EVENTS:
            continue
        resolves += 1
        boxes = {n["node_id"]: n["bbox"] for n in state["nodes"]}
        for node_id, want in manual.items():
            checked += 1
            got = boxes.get(node_id)
            if got is None or max(abs(a - b) for a, b in zip(got, want)) > TOLERANCE_PX:
                violations.append({"state_id": state["state_id"], "node_id": node_id,
                                   "designer_box": _box(want), "box": _box(got) if got else None})
    return {"resolves": resolves, "edits_checked": checked, "violations": violations}


# ---------------------------------------------------------------------------
# Structural accuracy (F1, p.56)
# ---------------------------------------------------------------------------

def structural_accuracy(nodes: list, canvas_w: float, canvas_h: float,
                        mandated: list, manual: dict = None) -> dict:
    """
    Scores every node the content payload mandates as TP, FP or FN (p.56;
    definitions in the module docstring). `manual` maps a Hard node's id
    to the box the designer gave it. Returns the counts, precision, recall,
    F1 and one row per node with the reasons.
    """
    manual = manual or {}
    present = {n["node_id"]: n for n in nodes}
    rows = []
    for node_id in mandated:
        node = present.get(node_id)
        if node is None:
            rows.append({"node_id": node_id, "name": node_name({"node_id": node_id}), "placed_by": None,
                         "result": "FN", "reasons": ["missing from the canvas"], "notes": []})
            continue
        box = [float(v) for v in node["bbox"]]
        hard = node.get("constraint_type") == "Hard"
        problems = []
        if hard and node_id in manual:
            want = manual[node_id]
            if max(abs(a - b) for a, b in zip(box, want)) > TOLERANCE_PX:
                problems.append(f"moved from where the designer put it ({_box(want)} → {_box(box)})")
        if _outside(box, canvas_w, canvas_h):
            problems.append("protrudes beyond the canvas")
        for other in nodes:
            if other is node:
                continue
            area = _overlap(box, [float(v) for v in other["bbox"]])
            if area:
                locked = " (locked)" if other.get("constraint_type") == "Hard" else ""
                problems.append(f"overlaps {node_name(other)}{locked} by {area:,.0f} px²")
        # A Hard node's box is the designer's choice: only "moved" counts.
        counted = [p for p in problems if not hard or p.startswith("moved")]
        rows.append({"node_id": node_id, "name": node_name(node),
                     "placed_by": "designer" if hard else "algorithm",
                     "result": "FP" if counted else "TP", "reasons": counted,
                     "notes": [p for p in problems if p not in counted]})

    tp = sum(r["result"] == "TP" for r in rows)
    fp = sum(r["result"] == "FP" for r in rows)
    fn = sum(r["result"] == "FN" for r in rows)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(precision, 4),
            "recall": round(recall, 4), "f1": round(f1, 4), "nodes": rows}


# ---------------------------------------------------------------------------
# The whole report
# ---------------------------------------------------------------------------

def _fitness_rows(metrics: dict, weights: HeuristicEvaluator) -> list:
    return [{"term": label, "formula": formula, "weight": getattr(weights, attr),
             "penalty": round(metrics.get(key, 0.0), 4),
             "weighted": round(getattr(weights, attr) * metrics.get(key, 0.0), 4)}
            for label, key, attr, formula in FITNESS_TERMS]


def _ms_summary(values: list) -> dict:
    values = [v for v in values if v is not None]
    if not values:
        return {"n": 0, "median_ms": None, "max_ms": None}
    return {"n": len(values), "median_ms": round(statistics.median(values), 1),
            "max_ms": round(max(values), 1)}


def build_report(session) -> dict:
    """The report for the session's current canvas (an OrchestrationSession
    from src/pipeline.py); JSON-serializable."""
    from pipeline import STAGE_LABELS

    states = session.chain.states
    current = session.chain.current
    history = manual_boxes(states)
    weights = HeuristicEvaluator(canvas_width=session.canvas_w, canvas_height=session.canvas_h)

    # Fitness: the designer's canvas next to ThemeSync's recommendation
    recommended = session.candidates[0]
    mine = current.get("fitness") or {}
    total = mine.get("Total_Cost")
    better = sum(c["c_total"] < total - 1e-9 for c in session.candidates) if total is not None else None
    fitness = {
        "weights": {attr: getattr(weights, attr) for _, _, attr, _ in FITNESS_TERMS},
        "yours": {"c_total": total, "terms": _fitness_rows(mine, weights)},
        "recommended": {"candidate_id": recommended["candidate_id"], "label": recommended["label"],
                        "c_total": recommended["c_total"],
                        "terms": _fitness_rows(recommended["metrics"], weights)},
        "rank": better + 1 if better is not None else None,
        "candidates": len(session.candidates),
    }

    # Structural accuracy and retention of the manual edits
    # The format's elements, less any the designer deleted (notes §3.56)
    removed = set(getattr(session, "removed", ()))
    mandated = [n["node_id"] for n in session.base_nodes if n["node_id"] not in removed]
    accuracy = structural_accuracy(current["nodes"], session.canvas_w, session.canvas_h,
                                   mandated, history[-1])
    retention = retention_check(states, history)

    # Latency: the pipeline's stages, then each event
    stages = [{"stage": label, "ms": round(session.timings.get(key, 0.0) * 1000, 1)}
              for key, label in STAGE_LABELS.items()]
    events = []
    for state in states[2:]:  # State_00/01 are the pipeline's own run
        event = state.get("event") or {}
        events.append({"state_id": state["state_id"], "type": event.get("type"),
                       "summary": event.get("summary") or state["label"],
                       "solve_ms": (event.get("latency_ms") or {}).get("solve"),
                       "total_ms": session.event_ms.get(state["state_id"])})
    resolves = [e for e in events if e["type"] in EDIT_EVENTS]
    latency = {
        "stages": stages,
        "pipeline_total_ms": round(sum(session.timings.values()) * 1000, 1),
        "events": events,
        "event_total": _ms_summary([e["total_ms"] for e in events]),
        "resolve_solver": _ms_summary([e["solve_ms"] for e in resolves]),
    }

    # Hybrid Visual DNA correctness
    ingestion = session.ingestion or {}
    checks = [{"check": f"{name.title()} (pre-orchestration)", "result": "passed" if v["valid"] else "rejected",
               "errors": v["errors"]} for name, v in (session.validation or {}).items()]
    revalidated = [s for s in states if (s.get("event") or {}).get("schema_validation") == "passed"
                   and s["event"].get("type") in ("text-edit", "typography")]
    dna = {"palette": ingestion.get("palette_hex"), "elbow": ingestion.get("elbow"),
           "schema_checks": checks, "revalidated_edits": len(revalidated)}

    edits = sum((s.get("event") or {}).get("type") in EDIT_EVENTS + ("text-edit",) for s in states)
    return {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "layout": {"format": session.domain, "canvas": [session.canvas_w, session.canvas_h],
                   "state_id": current["state_id"], "label": current["label"],
                   "condition": session.condition, "states": len(states), "designer_edits": edits,
                   "hard_nodes": current.get("hard_nodes", []),
                   "rendered": os.path.basename(session.rendered_path),
                   "state_chain": os.path.basename(session.chain_path)},
        "fitness": fitness,
        "structural_accuracy": accuracy,
        "retention": retention,
        "latency": latency,
        "visual_dna": dna,
    }
