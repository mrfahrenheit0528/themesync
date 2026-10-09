"""
ThemeSync — Phase 4, exploratory (post hoc) analysis
=====================================================
NOT part of the pre-specified plan (phase4_analysis.py, committed before the
scores were read). Written after the planned tests found the baseline rated
higher than the GNN condition, mostly on Constraint and Whitespace Harmony,
to look for what in the layouts goes with that. Its p-values are
exploratory: uncorrected, and chosen after seeing the data.

Looking at the pairs that differed most suggested that the GNN condition
(the master's structure mapping + the GNN) spreads the stacked elements
over the canvas at the master's positions, leaving large uneven gaps, while
the baseline stacks them as one evenly spaced group. This measures that on
all 64 rated layouts, read from the files the packets were printed from
(data/phase4/samples/; read only):

  largest gap    the largest vertical gap between consecutive stacked bands
                 (elements side by side merge into one band), as a fraction
                 of the canvas height
  gap CV         how uneven the gaps are: SD / mean of the gaps
  spread         from the top of the first band to the bottom of the last,
                 as a fraction of the canvas height

For each of the 32 pairs it takes GNN − baseline for each measure, and
relates it to GNN − baseline in MOS (overall, and Constraint and Whitespace
Harmony) with Spearman's rho. It also relates the MOS difference to the
difference in C_total (Formula 3.11).

Usage:
  python src/evaluation/phase4_posthoc.py     # -> results/phase4_posthoc.json
"""

import glob
import json
import os
import statistics
import sys

import numpy as np
from scipy import stats

_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_EVAL_DIR)
_ROOT = os.path.dirname(_SRC)
sys.path.insert(0, _EVAL_DIR)

import phase4_analysis as pa               # noqa: E402

SAMPLES = os.path.join(_ROOT, "data", "phase4", "samples")
OUT = os.path.join(_ROOT, "results", "phase4_posthoc.json")
MEASURES = ("largest_gap", "gap_cv", "spread")


def layout_nodes(poster: str, fmt: str, cond: str) -> tuple:
    folder = os.path.join(SAMPLES, os.path.splitext(poster)[0], f"{fmt}_{cond}")
    with open(glob.glob(os.path.join(folder, "ThemeSync_*_state_chain.json"))[0], encoding="utf-8") as f:
        nodes = json.load(f)["state_chain"][-1]["nodes"]
    import xml.etree.ElementTree as ET
    root = ET.parse(glob.glob(os.path.join(folder, "ThemeSync_*_populated.svg"))[0]).getroot()
    return nodes, float(root.get("height"))


def spacing(nodes: list, height: float) -> dict:
    """Vertical bands of the content (elements overlapping in y merge) and
    the gaps between them."""
    boxes = sorted(([n["bbox"][1], n["bbox"][1] + n["bbox"][3]] for n in nodes
                    if n.get("structural_class") != "decor"), key=lambda b: b[0])
    bands = []
    for top, bottom in boxes:
        if bands and top < bands[-1][1]:
            bands[-1][1] = max(bands[-1][1], bottom)
        else:
            bands.append([top, bottom])
    gaps = [b[0] - a[1] for a, b in zip(bands, bands[1:])]
    mean = statistics.mean(gaps) if gaps else 0.0
    return {"bands": len(bands),
            "largest_gap": round(max(gaps) / height, 4) if gaps else 0.0,
            "gap_cv": round(statistics.pstdev(gaps) / mean, 4) if len(gaps) > 1 and mean > 0 else 0.0,
            "spread": round((bands[-1][1] - bands[0][0]) / height, 4)}


def main():
    with open(os.path.join(_ROOT, "results", "phase4_analysis.json"), encoding="utf-8") as f:
        planned = json.load(f)
    key = pa.read_key()
    c_total = {(r["poster_file"], r["format"], r["condition"]): float(r["c_total"]) for r in key}

    rows = []
    for pair in planned["pairs"]:
        p, fmt = pair["poster"], pair["format"]
        m = {cond: spacing(*layout_nodes(p, fmt, cond)) for cond in pa.CONDITIONS}
        rows.append({"poster": p, "format": fmt, "identical_layouts": pair["identical_layouts"],
                     **{f"{k}_{cond}": m[cond][k] for cond in pa.CONDITIONS for k in MEASURES},
                     **{f"d_{k}": round(m["gnn"][k] - m["baseline"][k], 4) for k in MEASURES},
                     "d_c_total": round(c_total[(p, fmt, "gnn")] - c_total[(p, fmt, "baseline")], 4),
                     "d_mos_overall": round(pair["overall_gnn"] - pair["overall_baseline"], 4),
                     "d_mos_whitespace": round(pair["constraint_whitespace_harmony_gnn"]
                                               - pair["constraint_whitespace_harmony_baseline"], 4)})

    def describe(cond, k):
        return pa.describe([r[f"{k}_{cond}"] for r in rows])

    def rho(x, y):
        res = stats.spearmanr([r[x] for r in rows], [r[y] for r in rows])
        return {"rho": round(float(res.statistic), 4), "p": float(res.pvalue), "n": len(rows)}

    # Each expert on their own: mean overall rating per condition, and in
    # how many of the 32 pairs they rated the GNN version higher / lower
    ratings = pa.ratings_from_mos(pa.MOS_PATH)
    by = {(e, l): s for e, l, s in ratings}
    per_expert = {}
    for e in sorted({e for e, _, _ in ratings}):
        mine = {l: pa.value(s, "overall") for (x, l), s in by.items() if x == e}
        d = [mine[(p, f, "gnn")] - mine[(p, f, "baseline")] for p, f in {(l[0], l[1]) for l in mine}]
        per_expert[e] = {"gnn_mean": round(statistics.mean(v for l, v in mine.items() if l[2] == "gnn"), 3),
                         "baseline_mean": round(statistics.mean(v for l, v in mine.items() if l[2] == "baseline"), 3),
                         "all_mean": round(statistics.mean(mine.values()), 3),
                         "pairs_gnn_higher": sum(x > 0 for x in d), "pairs_gnn_lower": sum(x < 0 for x in d),
                         "pairs_equal": sum(x == 0 for x in d)}

    # The main tests without ANTI_HAZING_LAW, whose four rated pages carry
    # the misplaced "CLOSED" stamp (notes §3.35; raised before the data)
    mos = {}
    for (e, l), s in by.items():
        mos.setdefault(l, []).append(s)
    kept = [(p, f) for p, f in sorted({(l[0], l[1]) for l in mos}) if p != "ANTI_HAZING_LAW.jpg"]
    without_ahl = {m: pa.wilcoxon([statistics.mean(pa.value(s, m) for s in mos[(p, f, "gnn")])
                                   - statistics.mean(pa.value(s, m) for s in mos[(p, f, "baseline")])
                                   for p, f in kept]) for m in pa.MEASURES}
    adj = pa.holm({m: r["p"] for m, r in without_ahl.items()})
    for m in without_ahl:
        without_ahl[m]["p_holm"] = adj[m]

    result = {
        "status": "EXPLORATORY (post hoc): not part of the pre-specified plan; uncorrected p-values",
        "per_expert_overall": per_expert,
        "main_tests_without_anti_hazing_law": without_ahl,
        "layout_spacing": {k: {cond: describe(cond, k) for cond in pa.CONDITIONS} for k in MEASURES},
        "gnn_minus_baseline": {k: {**pa.describe([r[f"d_{k}"] for r in rows]),
                                   "gnn_larger": sum(r[f"d_{k}"] > 0 for r in rows),
                                   "gnn_smaller": sum(r[f"d_{k}"] < 0 for r in rows)} for k in MEASURES},
        "spearman_with_mos_difference": {
            f"d_{k} vs d_mos_{t}": rho(f"d_{k}", f"d_mos_{t}")
            for k in (*MEASURES, "c_total") for t in ("overall", "whitespace")},
        "pairs": rows,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)

    print(f"  {result['status']}\n")
    for e, r in per_expert.items():
        print(f"  {e:<26} GNN {r['gnn_mean']:.2f}  baseline {r['baseline_mean']:.2f}  all {r['all_mean']:.2f}  "
              f"(pairs: GNN higher {r['pairs_gnn_higher']}, lower {r['pairs_gnn_lower']}, equal {r['pairs_equal']})")
    print("\n  Without ANTI_HAZING_LAW (30 pairs):")
    for m, r in without_ahl.items():
        print(f"    {m:<32} higher {r['higher']}, lower {r['lower']}, equal {r['equal']}; "
              f"p = {r['p']:.2e} (Holm {r['p_holm']:.2e}); r = {r['r']:+.3f}")
    print()
    for k in MEASURES:
        g, b = result["layout_spacing"][k]["gnn"], result["layout_spacing"][k]["baseline"]
        d = result["gnn_minus_baseline"][k]
        print(f"  {k:<12} GNN {g['mean']:.3f}±{g['sd']:.3f}  baseline {b['mean']:.3f}±{b['sd']:.3f}  "
              f"(GNN larger in {d['gnn_larger']} pairs, smaller in {d['gnn_smaller']})")
    print()
    for name, r in result["spearman_with_mos_difference"].items():
        print(f"  {name:<36} rho = {r['rho']:+.3f}  p = {r['p']:.4f}")
    print(f"\n  -> {os.path.relpath(OUT, _ROOT)}")


if __name__ == "__main__":
    main()
