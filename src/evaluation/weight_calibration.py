"""
ThemeSync — Fitness weight calibration (Phase 3; revision item 3.25)
=====================================================================
Formula 3.11's weights (alpha, beta, gamma, delta) are "static scalar weights
empirically calibrated during Phase 3 testing to prioritize critical layout
rules (e.g., alpha is assigned the highest weight to strictly penalize
element overlap)" (p.43), "iteratively calibrated" until "the generated
coordinate predictions consistently align with strict architectural
constraints and human-centric design rules" (p.52).

This script runs that calibration as an analysis. It never changes the
deployed weights (optimization_engine.HeuristicEvaluator): the Phase 4
experts rated the layouts those weights chose, and they won't re-score.

Test set: the Phase 3 battery, i.e. the 16 Phase 4 posters x 2 formats x
2 conditions (GNN, no-GNN baseline) = 64 pipeline runs, generated exactly
as the Phase 4 packet generated them. The weights only rank the six
candidates; they don't change how a candidate is solved. So each run is
generated once and its candidates are re-ranked under any weights.

Criteria, fixed before the first run (2026-10-08):

  A. Constraints first (p.43). A candidate breaks the constraints if any
     element overlaps another or leaves the canvas (p.56's FP/FN, or
     P_collision > 0). The chosen layout must keep the constraints in every
     run where one of its options does, and alpha must stay the highest
     weight.
  B. Design rules (p.52). The loop starts from the deployed weights. Each
     round tries multiplying one weight by 0.25, 0.5, 2 or 4. A change is
     kept only if it makes the chosen layouts better on average on at least
     one design rule (alignment, whitespace, legibility: Formulas 3.13-3.15)
     and worse on none, without breaking criterion A. The loop stops when
     no change qualifies.

  The deployed weights count as calibrated if criterion A holds and the
  loop keeps no change. "Chosen" means what the deployed system shows: the
  fittest candidate of the layout type the master's composition calls for
  (revision item 3.23). The plain fitness ranking (lowest C_total of all
  six, the no-master case) is reported beside it.

Usage:
  python src/evaluation/weight_calibration.py           # generate the 64 runs, then analyse
  python src/evaluation/weight_calibration.py --reuse   # analyse the saved runs again

Writes results/weight_calibration.json.
"""

import argparse
import contextlib
import csv
import datetime
import io
import json
import os
import statistics
import sys

_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_EVAL_DIR)
_ROOT = os.path.dirname(_SRC)
for _p in (_EVAL_DIR, _SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import phase4_packet as p4                 # noqa: E402 — imports rasterize (fonts) first
import pipeline                            # noqa: E402
from candidate_generator import ARCHETYPES, solver_for       # noqa: E402 — on the path via pipeline
from layout_report import structural_accuracy                # noqa: E402
from optimization_engine import HeuristicEvaluator           # noqa: E402

RESULT_PATH = os.path.join(_ROOT, "results", "weight_calibration.json")
RUNS_DIR = os.path.join(_ROOT, "data", "rendered", "calibration")
WEIGHTS = ("alpha", "beta", "gamma", "delta")
RULES = ("P_align", "P_space", "P_legibility")       # Formulas 3.13-3.15
STEPS = (0.25, 0.5, 2.0, 4.0)                        # the loop's one-weight changes
SWEEP = (0.0, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 10.0)   # the sensitivity table
TOL = 1e-4                                           # C_total is kept to 4 decimals


def deployed_weights() -> dict:
    e = HeuristicEvaluator()
    return {k: getattr(e, k) for k in WEIGHTS}


# ---------------------------------------------------------------------------
# Generating the runs
# ---------------------------------------------------------------------------

def _candidate_record(session, cand: dict, order: int) -> dict:
    """A candidate's raw penalties, rebuilt the way MetaheuristicStateExplorer
    scores it, plus its p.56 constraint check."""
    var = cand["variation"]
    arch = ARCHETYPES[var.get("archetype", "classic")]
    solver = solver_for(var, session.canvas_w, session.canvas_h, session.structure_guided)
    ev = HeuristicEvaluator(canvas_width=session.canvas_w, canvas_height=session.canvas_h,
                            saliency_map=cand["saliency_map"],
                            grid_bounds=(solver.left_bound, solver.right_bound),
                            content_region=(arch["region"][0] * session.canvas_w,
                                            arch["region"][1] * session.canvas_w))
    nodes = cand["nodes"]
    raw = {"P_collision": ev.calculate_collision_penalty(nodes),
           "P_align": ev.calculate_alignment_penalty(nodes),
           "P_space": ev.calculate_whitespace_penalty(nodes),
           "P_legibility": ev.calculate_legibility_penalty(nodes)}
    reproduced = all(round(raw[k], 4) == cand["metrics"][k] for k in raw)
    accuracy = structural_accuracy(nodes, session.canvas_w, session.canvas_h,
                                   [n["node_id"] for n in session.base_nodes])
    problems = [f"{r['name']}: {'; '.join(r['reasons'])}" for r in accuracy["nodes"] if r["result"] != "TP"]
    return {"candidate_id": cand["candidate_id"], "order": order,
            "archetype": var.get("archetype", "classic"), **raw,
            "constraints_ok": not problems and raw["P_collision"] == 0.0,
            "problems": problems, "reproduced": reproduced}


def generate_runs() -> list:
    rows = sorted([r for r in p4.read_manifest(p4.POSTERS_DIR) if r.get("poster_file")],
                  key=lambda r: r["poster_file"])
    runs = []
    for i, row in enumerate(rows):
        poster = os.path.join(p4.POSTERS_DIR, row["poster_file"])
        stem = os.path.splitext(row["poster_file"])[0]
        content = p4.content_for(row, i)
        for fmt, payload in p4.FORMATS.items():
            for cond in p4.CONDITIONS:
                session = pipeline.OrchestrationSession(
                    payload, template_image=poster, content_data=content[fmt],
                    use_gnn=(cond == "gnn"), output_dir=os.path.join(RUNS_DIR, stem, f"{fmt}_{cond}"),
                    logo_images=p4.logo_paths(row, p4.POSTERS_DIR),
                    use_wordmark=p4.use_title_artwork(row),
                    motif_paths=None if p4.use_motifs(row) else [])
                with contextlib.redirect_stdout(io.StringIO()):
                    session.run()
                by_order = sorted(session.candidates, key=lambda c: c["candidate_id"])
                runs.append({"poster": row["poster_file"], "format": fmt, "condition": cond,
                             "preferred_archetype": session.preferred_archetype,
                             "deployed_winner": session.candidates[0]["candidate_id"],
                             "candidates": [_candidate_record(session, c, k) for k, c in enumerate(by_order)]})
                print(f"  [{len(runs):>2}/{len(rows) * 4}] {stem[:28]:<28} {fmt:<11} {cond:<8} "
                      f"→ {runs[-1]['deployed_winner']}", flush=True)
    return runs


# ---------------------------------------------------------------------------
# Re-ranking under other weights
# ---------------------------------------------------------------------------

def total(c: dict, w: dict) -> float:
    return round(w["alpha"] * c["P_collision"] + w["beta"] * c["P_align"]
                 + w["gamma"] * c["P_space"] + w["delta"] * c["P_legibility"], 4)


def options(run: dict, rule: str) -> list:
    """The candidates a rule chooses from: the preferred layout type's
    (deployed, when the master calls for one that exists), or all six."""
    if rule == "deployed":
        same = [c for c in run["candidates"] if c["archetype"] == run["preferred_archetype"]]
        if same:
            return same
    return run["candidates"]


def choose(run: dict, w: dict, rule: str) -> dict:
    # Python's sort is stable: ties keep generation order, as in the pipeline.
    return sorted(options(run, rule), key=lambda c: total(c, w))[0]


def evaluate(runs: list, w: dict, rule: str, reference: dict = None) -> dict:
    chosen = [choose(r, w, rule) for r in runs]
    possible = [i for i, r in enumerate(runs) if any(c["constraints_ok"] for c in options(r, rule))]
    out = {"constraints_kept": sum(chosen[i]["constraints_ok"] for i in possible),
           "constraints_possible": len(possible),
           "alpha_highest": w["alpha"] > max(w["beta"], w["gamma"], w["delta"]),
           **{k: round(statistics.mean(c[k] for c in chosen), 5) for k in RULES}}
    if reference is not None:
        out["outputs_changed"] = sum(c["candidate_id"] != choose(r, reference, rule)["candidate_id"]
                                     for r, c in zip(runs, chosen))
    return out


def criterion_a(m: dict) -> bool:
    return m["constraints_kept"] == m["constraints_possible"] and m["alpha_highest"]


def better(new: dict, old: dict) -> bool:
    """Better on at least one design rule, worse on none, criterion A kept."""
    return (criterion_a(new)
            and all(new[k] <= old[k] + TOL for k in RULES)
            and any(new[k] < old[k] - TOL for k in RULES))


def calibration_loop(runs: list, start: dict, rule: str, max_rounds: int = 12) -> list:
    """Coordinate search from the deployed weights; each round keeps the
    qualifying change with the largest relative gain."""
    w, path = dict(start), []
    current = evaluate(runs, w, rule)
    for _ in range(max_rounds):
        best = None
        for k in WEIGHTS:
            for step in STEPS:
                trial = dict(w, **{k: w[k] * step})
                m = evaluate(runs, trial, rule)
                if better(m, current):
                    gain = sum((current[r] - m[r]) / current[r] for r in RULES if current[r] > 0)
                    if best is None or gain > best[0]:
                        best = (gain, k, step, trial, m)
        if best is None:
            break
        _, k, step, w, current = best
        path.append({"change": f"{k} x {step:g}", "weights": dict(w), "metrics": current})
    return path


def alpha_needed(runs: list, w: dict, rule: str):
    """The smallest alpha that ranks every constraint-keeping option above
    every constraint-breaking one (with beta, gamma, delta as in `w`), or
    None when no option ever breaks the constraints."""
    need, seen = 0.0, False
    for r in runs:
        opts = options(r, rule)
        ok = [c for c in opts if c["constraints_ok"]]
        bad = [c for c in opts if not c["constraints_ok"] and c["P_collision"] > 0]
        if not ok or not bad:
            continue
        seen = True
        rest = lambda c: w["beta"] * c["P_align"] + w["gamma"] * c["P_space"] + w["delta"] * c["P_legibility"]
        best_ok = min(rest(c) for c in ok)
        for c in bad:
            need = max(need, (best_ok - rest(c)) / c["P_collision"])
    return round(need, 3) if seen else None


def analyse(runs: list) -> dict:
    w0 = deployed_weights()
    out = {"deployed_weights": w0}

    # Sanity: the re-ranking reproduces what the pipeline (and the packet) chose
    key = {}
    if os.path.exists(p4.KEY_PATH):
        with open(p4.KEY_PATH) as f:
            key = {(r["poster_file"], r["format"], r["condition"]): r["winner_candidate"] for r in csv.DictReader(f)}
    out["sanity"] = {
        "runs": len(runs),
        "penalties_reproduced": sum(all(c["reproduced"] for c in r["candidates"]) for r in runs),
        "choice_matches_pipeline": sum(choose(r, w0, "deployed")["candidate_id"] == r["deployed_winner"] for r in runs),
        "choice_matches_phase4_packet": sum(choose(r, w0, "deployed")["candidate_id"]
                                            == key.get((r["poster"], r["format"], r["condition"])) for r in runs),
        "candidates_breaking_constraints": sum(not c["constraints_ok"] for r in runs for c in r["candidates"]),
        "runs_with_one_option": sum(len(options(r, "deployed")) == 1 for r in runs),
    }

    for rule in ("deployed", "plain"):
        m0 = evaluate(runs, w0, rule)
        path = calibration_loop(runs, w0, rule)
        end = path[-1]["weights"] if path else w0
        sweep = {k: [dict(evaluate(runs, dict(w0, **{k: w0[k] * s}), rule, w0), multiplier=s) for s in SWEEP]
                 for k in WEIGHTS}
        out[rule] = {
            "at_deployed_weights": m0,
            "criterion_a": criterion_a(m0),
            "alpha_needed": alpha_needed(runs, w0, rule),
            "loop": path,
            "loop_end_weights": end,
            "outputs_changed_at_loop_end": evaluate(runs, end, rule, w0)["outputs_changed"],
            "calibrated": criterion_a(m0) and not path,
            "sensitivity": sweep,
        }
    return out


def _print(result: dict) -> None:
    s = result["analysis"]["sanity"]
    print(f"\n  Runs {s['runs']} · penalties reproduced {s['penalties_reproduced']} · "
          f"choice = pipeline {s['choice_matches_pipeline']} · = Phase 4 packet {s['choice_matches_phase4_packet']}")
    print(f"  Candidates breaking the constraints: {s['candidates_breaking_constraints']} · "
          f"runs where the layout type leaves one option: {s['runs_with_one_option']}")
    for rule in ("deployed", "plain"):
        a = result["analysis"][rule]
        m = a["at_deployed_weights"]
        print(f"\n  [{rule}] at the deployed weights: constraints kept {m['constraints_kept']}/{m['constraints_possible']}, "
              + ", ".join(f"{k} {m[k]:.4f}" for k in RULES))
        print(f"    criterion A: {a['criterion_a']} · alpha needed: {a['alpha_needed']}")
        for step in a["loop"]:
            print(f"    loop: {step['change']:<14} → " + ", ".join(f"{k} {step['metrics'][k]:.4f}" for k in RULES))
        print(f"    calibrated: {a['calibrated']} · outputs changed at the loop's end: {a['outputs_changed_at_loop_end']}")
        for k in WEIGHTS:
            print(f"    {k:<6} x " + "  ".join(f"{row['multiplier']:g}:{row['outputs_changed']}" for row in a["sensitivity"][k]))


def main():
    parser = argparse.ArgumentParser(description="ThemeSync fitness weight calibration (item 3.25)")
    parser.add_argument("--reuse", action="store_true", help="analyse the runs saved in the last result")
    args = parser.parse_args()

    if args.reuse:
        with open(RESULT_PATH) as f:
            runs = json.load(f)["runs"]
    else:
        print(f"  Generating the Phase 3 battery (GNN {os.path.basename(pipeline.DEFAULT_WEIGHTS)}, "
              f"YOLO {os.path.basename(pipeline.DEFAULT_YOLO_WEIGHTS)})")
        runs = generate_runs()
    result = {"timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
              "criteria": __doc__.split("Criteria, fixed")[1].split("Usage:")[0].strip(),
              "analysis": analyse(runs), "runs": runs}
    os.makedirs(os.path.dirname(RESULT_PATH), exist_ok=True)
    with open(RESULT_PATH, "w") as f:
        json.dump(result, f, indent=1)
    _print(result)
    print(f"\n  Saved → {os.path.relpath(RESULT_PATH, _ROOT)}")


if __name__ == "__main__":
    main()
