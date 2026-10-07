"""
ThemeSync — Evaluation Harness
================================
Computes the evaluation metrics defined in the manuscript (Chapter 3) on one
payload, GNN-guided vs. no-GNN baseline, running the same
OrchestrationSession the dashboard uses:

  - Latency         : wall-clock time per pipeline stage (ms)
  - IoU             : GNN-predicted boxes vs. where the CSP finally put them
  - Constraint F1   : structural accuracy as p.56 defines it, after three
                      simulated designer events — a move (on-drop), a resize
                      (on-resize-complete) and a lock. Every payload node is
                      a TP (no collision, inside the canvas, a Hard one where
                      the designer left it), an FP or an FN (missing);
                      layout_report.structural_accuracy. The Hard nodes kept
                      exactly through every re-solve are reported with it
                      (non-destructive retention, p.54).
  - F_layout        : Heuristic fitness function (Formula 3.11), its terms
  - Baseline delta  : GNN-guided vs. no-GNN baseline

Without --template_image the synthetic fallback theme is used (the
manuscript's synthetic administrative templates); with one, the master's
Visual DNA and style kit.

Usage:
  python src/evaluation/evaluate.py
  python src/evaluation/evaluate.py --payload data/raw/id_payload.json
  python src/evaluation/evaluate.py --template_image data/raw/phase4_posters/PASALABAT.jpg
"""

import argparse
import contextlib
import io
import json
import os
import sys

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_EVAL_DIR)
_ROOT = os.path.dirname(_SRC)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pipeline  # noqa: E402
from layout_report import manual_boxes, retention_check, structural_accuracy  # noqa: E402

SEPARATOR = "=" * 66


# ---------------------------------------------------------------------------
# Metric calculators
# ---------------------------------------------------------------------------

def calculate_iou(box1: list, box2: list) -> float:
    """
    Computes Intersection over Union between two [x, y, w, h] bounding boxes.
    Used to measure how much the CSP solver preserves the GNN's spatial predictions.
    """
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2

    ix1 = max(x1, x2)
    iy1 = max(y1, y2)
    ix2 = min(x1 + w1, x2 + w2)
    iy2 = min(y1 + h1, y2 + h2)

    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = w1 * h1 + w2 * h2 - inter

    return inter / union if union > 0 else 0.0


# ---------------------------------------------------------------------------
# Single evaluation run
# ---------------------------------------------------------------------------

def _simulated_edits(session) -> list:
    """Three designer events on the stacked nodes: move the second, resize
    the fourth, lock the last where it is. Returns [(node_id, bbox the
    designer left it at), ...]."""
    stack = sorted((n for n in session.chain.current["nodes"]
                    if n.get("structural_class") not in ("decor", "repeating_group")),
                   key=lambda n: n["spatial_hierarchy"])
    edits = []
    moved = stack[1]
    x, y, w, h = moved["bbox"]
    session.apply_event("on-drop", moved["node_id"], [x + 24.0, y + 18.0, w, h])
    edits.append((moved["node_id"], [x + 24.0, y + 18.0, w, h]))
    resized = next(n for n in session.chain.current["nodes"] if n["node_id"] == stack[3]["node_id"])
    x, y, w, h = resized["bbox"]
    session.apply_event("on-resize-complete", resized["node_id"], [x, y, w * 0.9, h * 1.1])
    edits.append((resized["node_id"], [x, y, w * 0.9, h * 1.1]))
    locked = next(n for n in session.chain.current["nodes"] if n["node_id"] == stack[-1]["node_id"])
    session.apply_event("lock-toggle", locked["node_id"], hard=True)
    edits.append((locked["node_id"], list(locked["bbox"])))
    return edits


def _run_once(payload_path: str, use_gnn: bool, template_image: str = None,
              canvas_w: int = None, canvas_h: int = None) -> dict:
    """Executes the full pipeline once, then the simulated edits, and
    collects all evaluation metrics."""
    out_dir = os.path.join(_ROOT, "data", "rendered", "evaluation", "gnn" if use_gnn else "baseline")
    session = pipeline.OrchestrationSession(payload_path, template_image=template_image, use_gnn=use_gnn,
                                            output_dir=out_dir, canvas_w=canvas_w, canvas_h=canvas_h)
    with contextlib.redirect_stdout(io.StringIO()):
        summary = session.run()
    winner = session.candidates[0]
    metrics = winner["metrics"]
    timings = {f"{k}_ms": v for k, v in summary["timings_ms"].items()}
    timings["total_ms"] = summary["total_ms"]

    # IoU: GNN prediction vs. CSP resolution (GNN runs only — the baseline
    # has no prediction to compare)
    resolved = {n["node_id"]: n["bbox"] for n in winner["nodes"]}
    predicted = [n for n in session.guided_nodes if n.get("gnn_predicted")]
    iou_scores = [calculate_iou(n["bbox"], resolved[n["node_id"]]) for n in predicted if n["node_id"] in resolved]
    mean_iou = round(sum(iou_scores) / len(iou_scores), 4) if iou_scores else None

    # Constraint F1 (p.56) after the simulated edits, and their retention
    with contextlib.redirect_stdout(io.StringIO()):
        edits = _simulated_edits(session)
    final = session.chain.current
    history = manual_boxes(session.chain.states)
    f1_result = structural_accuracy(final["nodes"], session.canvas_w, session.canvas_h,
                                    [n["node_id"] for n in session.base_nodes], history[-1])
    retention = retention_check(session.chain.states, history)
    f1_result["total_hard"] = len(edits)
    f1_result["hard_preserved"] = sum(r["result"] == "TP" for r in f1_result["nodes"]
                                      if r["node_id"] in dict(edits))
    f1_result["edits_kept_through_resolves"] = (f"{retention['edits_checked'] - len(retention['violations'])}"
                                                f"/{retention['edits_checked']}")
    f1_result["events"] = [s["event"]["summary"] for s in session.chain.states if s["event"].get("summary")]
    f1_result["collision_after_edits"] = final["fitness"]["P_collision"]

    return {
        "timings_ms":        timings,
        "mean_iou":          mean_iou,
        "per_node_iou":      [round(v, 4) for v in iou_scores],
        "constraint_f1":     f1_result,
        "heuristic_fitness": {
            "P_collision":   metrics.get("P_collision", 0.0),
            "P_align":       metrics.get("P_align", 0.0),
            "P_space":       metrics.get("P_space", 0.0),
            "P_legibility":  metrics.get("P_legibility", 0.0),
            "C_total":       winner["c_total"],
        },
        "winner_candidate":  winner["candidate_id"],
        "num_nodes":         sum(1 for n in winner["nodes"] if n.get("structural_class") != "decor"),
        "state_chain":       os.path.relpath(session.chain_path, _ROOT),
    }


# ---------------------------------------------------------------------------
# Multi-trial runner
# ---------------------------------------------------------------------------

def run_evaluation(
    payload_path: str,
    canvas_w: int = None,
    canvas_h: int = None,
    trials: int = 1,
    template_image: str = None,
):
    print(f"\n{'='*66}")
    print("  ThemeSync — Evaluation Harness")
    print(f"{'='*66}")
    print(f"  Payload  : {payload_path}")
    print(f"  Template : {template_image or '(synthetic fallback theme)'}")
    print(f"  GNN      : {os.path.basename(pipeline.DEFAULT_WEIGHTS)}")
    print(f"  Trials   : {trials}  (deterministic: repeated trials reproduce the same numbers)")

    gnn_results    = []
    baseline_results = []

    for trial in range(1, trials + 1):
        print(f"\n  ── Trial {trial}/{trials} ──")
        r_gnn  = _run_once(payload_path, True, template_image, canvas_w, canvas_h)
        r_base = _run_once(payload_path, False, template_image, canvas_w, canvas_h)
        gnn_results.append(r_gnn)
        baseline_results.append(r_base)
        for tag, r in (("GNN ", r_gnn), ("Base", r_base)):
            iou = f"{r['mean_iou']:.4f}" if r["mean_iou"] is not None else "  —   "
            print(f"     {tag}  | IoU={iou}  F1={r['constraint_f1']['f1']:.4f}  "
                  f"C_total={r['heuristic_fitness']['C_total']:.4f}  "
                  f"Total={r['timings_ms']['total_ms']:.1f}ms")

    def _avg(results, key_path):
        vals = results
        for k in key_path:
            vals = [v[k] for v in vals]
        vals = [v for v in vals if v is not None]
        return round(sum(vals) / len(vals), 4) if vals else float("nan")

    # Aggregate
    print(f"\n{'='*66}")
    print("  Aggregate Results (mean across trials)")
    print(f"{'='*66}")
    print(f"\n  {'Metric':<38} {'GNN-Guided':>12} {'Baseline':>12} {'Delta':>10}")
    print(f"  {'-'*38} {'-'*12} {'-'*12} {'-'*10}")

    metrics_to_report = [
        ("Mean IoU",            ["mean_iou"],                          True),
        ("Constraint F1",       ["constraint_f1", "f1"],               True),
        ("P_align",             ["heuristic_fitness", "P_align"],      False),
        ("P_space",             ["heuristic_fitness", "P_space"],      False),
        ("P_legibility",        ["heuristic_fitness", "P_legibility"], False),
        ("C_total (↓ better)",  ["heuristic_fitness", "C_total"],      False),
        ("Latency — Total (ms)",["timings_ms", "total_ms"],            False),
    ]

    for label, path, higher_better in metrics_to_report:
        g = _avg(gnn_results, path)
        b = _avg(baseline_results, path)
        delta = g - b
        direction = "↑" if (higher_better and delta > 0) or (not higher_better and delta < 0) else "↓"
        print(f"  {label:<38} {g:>12.4f} {b:>12.4f} {delta:>+9.4f} {direction}")

    print()

    # Save results
    output = {
        "payload": payload_path,
        "template_image": template_image,
        "gnn_weights": os.path.basename(pipeline.DEFAULT_WEIGHTS),
        "trials": trials,
        "gnn_guided":  gnn_results,
        "baseline":    baseline_results,
    }
    results_path = os.path.join(_ROOT, "results", "evaluation_results.json")
    os.makedirs(os.path.dirname(results_path), exist_ok=True)
    with open(results_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"  Results saved → {results_path}\n")
    return output


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ThemeSync Evaluation Harness")
    parser.add_argument("--payload",  type=str, default="data/raw/academic_payload.json")
    parser.add_argument("--template_image", type=str, default=None,
                        help="master layout to take the Visual DNA from (default: synthetic theme)")
    parser.add_argument("--canvas_w", type=int, default=None)
    parser.add_argument("--canvas_h", type=int, default=None)
    parser.add_argument("--trials",   type=int, default=1,
                        help="Number of evaluation trials (default: 1; the pipeline is deterministic)")
    args = parser.parse_args()

    run_evaluation(
        payload_path=args.payload,
        canvas_w=args.canvas_w,
        canvas_h=args.canvas_h,
        trials=args.trials,
        template_image=args.template_image,
    )


if __name__ == "__main__":
    main()
