"""
ThemeSync — A master-derived R_target for Formula 3.14 (analysis only; M19)
============================================================================
p.47 says the Whitespace Penalty measures a layout's whitespace ratio against
"an optimal target ratio (R_target) established by the master template's
visual DNA". The code fixes R_target at 0.65 for every master
(optimization_engine.HeuristicEvaluator.r_target). The experts rated what
0.65 chose, so the deployed value stays; this script asks how many of the
64 rated outputs a master-derived R_target would have changed, as
weight_calibration.py did for the weights (notes §3.33).

Test set: the 16 Phase 4 posters x 2 formats x GNN/baseline = 64 runs,
generated as the packet generated them (weight_calibration.generate_runs'
recipe), into data/rendered/r_target/ (git-ignored). Nothing in
data/phase4/ is written; the key is read only to confirm the regenerated
choices.

The master's R_target: Formula 3.14 applied to the master itself, over its
whole canvas, with the elements Stage 0b parsed that become the target's
content (logos and text; embellishments and underlays are the background
layer, as motifs are for the target):

  sum     (A − Σ area(B_i)) / A, as Formula 3.14 writes it
  union   the same with the union of the boxes (detections may overlap)

Each candidate's whitespace ratio is recomputed the way the evaluator does
(over the candidate's content region); its penalty under another R_target is
|ratio − R_target|. The other three penalties don't depend on R_target, so
each run's six candidates are generated once and re-ranked, with the
deployed weights and the deployed choice rule (the fittest candidate of the
layout type the master calls for), and with the plain ranking (all six).

Usage:
  python src/evaluation/r_target_analysis.py
  python src/evaluation/r_target_analysis.py --reuse    # re-analyse the saved runs

Writes results/r_target_analysis.json.
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

import numpy as np

_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_EVAL_DIR)
_ROOT = os.path.dirname(_SRC)
for _p in (_EVAL_DIR, _SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import phase4_packet as p4                 # noqa: E402 — imports rasterize (fonts) first
import pipeline                            # noqa: E402
import weight_calibration as wc            # noqa: E402
from candidate_generator import ARCHETYPES                    # noqa: E402 — on the path via pipeline
from optimization_engine import HeuristicEvaluator            # noqa: E402
from PIL import Image                      # noqa: E402

RESULT_PATH = os.path.join(_ROOT, "results", "r_target_analysis.json")
RUNS_DIR = os.path.join(_ROOT, "data", "rendered", "r_target")
DEPLOYED_R = HeuristicEvaluator().r_target
CONTENT_CLASSES = ("logo", "text")
SWEEP = [round(0.30 + 0.05 * i, 2) for i in range(14)]     # 0.30 .. 0.95


def master_ratio(detected: list, mw: int, mh: int) -> dict:
    """Formula 3.14 on the master: whitespace over its whole canvas, with the
    parsed logos and text as its elements."""
    boxes = [d["bbox"] for d in detected if d.get("semantic_category") in CONTENT_CLASSES]
    area = float(mw * mh)
    summed = sum(float(w) * float(h) for _, _, w, h in boxes)
    mask = np.zeros((mh, mw), dtype=bool)
    for x, y, w, h in boxes:
        x0, y0 = max(0, int(round(x))), max(0, int(round(y)))
        mask[y0:max(y0, int(round(y + h))), x0:max(x0, int(round(x + w)))] = True
    return {"elements": len(boxes), "sum": round((area - summed) / area, 4),
            "union": round(float(1.0 - mask.sum() / area), 4)}


def candidate_ratio(session, cand: dict) -> float:
    """The candidate's whitespace ratio, as HeuristicEvaluator computes it."""
    arch = ARCHETYPES[cand["variation"].get("archetype", "classic")]
    left, right = arch["region"][0] * session.canvas_w, arch["region"][1] * session.canvas_w
    area = (right - left) * session.canvas_h
    used = sum(float(n["bbox"][2]) * float(n["bbox"][3]) for n in cand["nodes"]
               if n.get("structural_class") != "decor")
    return (area - used) / area


def generate_runs() -> list:
    rows = sorted([r for r in p4.read_manifest(p4.POSTERS_DIR) if r.get("poster_file")],
                  key=lambda r: r["poster_file"])
    runs = []
    for i, row in enumerate(rows):
        poster = os.path.join(p4.POSTERS_DIR, row["poster_file"])
        stem = os.path.splitext(row["poster_file"])[0]
        content = p4.content_for(row, i)
        with Image.open(poster) as img:
            mw, mh = img.size
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
                cands = []
                for k, c in enumerate(by_order):
                    rec = wc._candidate_record(session, c, k)
                    rec["whitespace_ratio"] = candidate_ratio(session, c)
                    rec["ratio_reproduces_P_space"] = abs(abs(rec["whitespace_ratio"] - DEPLOYED_R)
                                                          - rec["P_space"]) < 1e-9
                    cands.append(rec)
                runs.append({"poster": row["poster_file"], "format": fmt, "condition": cond,
                             "preferred_archetype": session.preferred_archetype,
                             "deployed_winner": session.candidates[0]["candidate_id"],
                             "master": master_ratio(session.detected_nodes or [], mw, mh),
                             "candidates": cands})
                print(f"  [{len(runs):>2}/{len(rows) * 4}] {stem[:28]:<28} {fmt:<11} {cond:<8} "
                      f"→ {runs[-1]['deployed_winner']}  master R {runs[-1]['master']['sum']:.3f}", flush=True)
    return runs


def with_r(run: dict, r: float) -> dict:
    """The run with every candidate's whitespace penalty against R_target r."""
    return dict(run, candidates=[dict(c, P_space=abs(c["whitespace_ratio"] - r)) for c in run["candidates"]])


def choices(runs: list, r_of, rule: str, w: dict) -> list:
    return [wc.choose(with_r(run, r_of(run)), w, rule) for run in runs]


def analyse(runs: list) -> dict:
    w = wc.deployed_weights()
    key = {}
    if os.path.exists(p4.KEY_PATH):
        with open(p4.KEY_PATH, newline="", encoding="utf-8") as f:
            key = {(r["poster_file"], r["format"], r["condition"]): r["winner_candidate"] for r in csv.DictReader(f)}
    base = {rule: choices(runs, lambda run: DEPLOYED_R, rule, w) for rule in ("deployed", "plain")}
    out = {
        "deployed_r_target": DEPLOYED_R,
        "weights": w,
        "sanity": {
            "runs": len(runs),
            "ratios_reproduce_P_space": sum(all(c["ratio_reproduces_P_space"] for c in r["candidates"]) for r in runs),
            "choice_at_0.65_matches_pipeline": sum(c["candidate_id"] == r["deployed_winner"]
                                                   for r, c in zip(runs, base["deployed"])),
            "choice_at_0.65_matches_phase4_key": sum(c["candidate_id"] == key.get((r["poster"], r["format"], r["condition"]))
                                                     for r, c in zip(runs, base["deployed"])) if key else None,
        },
        "master_r_target": {},
        "candidate_whitespace_ratio": {},
    }
    masters = {r["poster"]: r["master"] for r in runs}
    for v in ("sum", "union"):
        vals = [m[v] for m in masters.values()]
        out["master_r_target"][v] = {"min": min(vals), "median": round(statistics.median(vals), 4),
                                     "max": max(vals), "per_poster": {p: m[v] for p, m in sorted(masters.items())}}
    for fmt in p4.FORMATS:
        vals = [c["whitespace_ratio"] for r in runs if r["format"] == fmt for c in r["candidates"]]
        chosen = [c["whitespace_ratio"] for r, c in zip(runs, base["deployed"]) if r["format"] == fmt]
        out["candidate_whitespace_ratio"][fmt] = {
            "all_candidates": {"min": round(min(vals), 4), "median": round(statistics.median(vals), 4),
                               "max": round(max(vals), 4)},
            "chosen_at_0.65": {"min": round(min(chosen), 4), "median": round(statistics.median(chosen), 4),
                               "max": round(max(chosen), 4)}}

    def changed(rule: str, r_of) -> dict:
        new = choices(runs, r_of, rule, w)
        diff = [(r, b["candidate_id"], c["candidate_id"]) for r, b, c in zip(runs, base[rule], new)
                if b["candidate_id"] != c["candidate_id"]]
        return {"outputs_changed": len(diff),
                "by_format_condition": {f"{f} {cnd}": sum(r["format"] == f and r["condition"] == cnd for r, _, _ in diff)
                                        for f in p4.FORMATS for cnd in p4.CONDITIONS},
                "changes": [f"{r['poster']} {r['format']} {r['condition']}: {a} → {b}" for r, a, b in diff],
                "mean_P_space_of_chosen": round(statistics.mean(abs(c["whitespace_ratio"] - r_of(r))
                                                                for r, c in zip(runs, new)), 5)}

    for rule in ("deployed", "plain"):
        out[rule] = {
            "runs_with_one_option": sum(len(wc.options(r, rule)) == 1 for r in runs),
            "master_sum": changed(rule, lambda run: run["master"]["sum"]),
            "master_union": changed(rule, lambda run: run["master"]["union"]),
            "sweep": [{"r_target": r, **{k: v for k, v in changed(rule, lambda run, r=r: r).items()
                                          if k in ("outputs_changed", "by_format_condition")}} for r in SWEEP],
        }
    return out


def main():
    parser = argparse.ArgumentParser(description="A master-derived R_target (analysis only; M19)")
    parser.add_argument("--reuse", action="store_true", help="re-analyse the runs saved in the last result")
    args = parser.parse_args()
    if args.reuse:
        with open(RESULT_PATH, encoding="utf-8") as f:
            runs = json.load(f)["runs"]
    else:
        runs = generate_runs()
    result = {"generated": datetime.datetime.now().isoformat(timespec="seconds"),
              "analysis": analyse(runs), "runs": runs}
    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    a = result["analysis"]
    print("\nSanity:", json.dumps(a["sanity"]))
    print("Master R_target:", {v: {k: a["master_r_target"][v][k] for k in ("min", "median", "max")}
                               for v in ("sum", "union")})
    print("Candidates' whitespace ratios:", json.dumps(a["candidate_whitespace_ratio"]))
    for rule in ("deployed", "plain"):
        print(f"\n{rule}: one option in {a[rule]['runs_with_one_option']} runs")
        for v in ("master_sum", "master_union"):
            print(f"  {v}: {a[rule][v]['outputs_changed']} of {len(runs)} outputs change "
                  f"{a[rule][v]['by_format_condition']}")
        print("  sweep:", ", ".join(f"{s['r_target']:.2f}→{s['outputs_changed']}" for s in a[rule]["sweep"]))
    print(f"\n-> {os.path.relpath(RESULT_PATH, _ROOT)}")


if __name__ == "__main__":
    main()
