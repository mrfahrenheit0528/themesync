"""
ThemeSync — Phase 4 statistical analysis (the plan adopted 2026-10-10)
=======================================================================
The statistics consultation guide (notes/consultation_guidelines.pdf, for the
9 October 2026 consultation) asked eleven questions, each with a suggested
answer. The consultant reviews only the prototype, so the group adopted the
suggested answer to every question (user, 2026-10-10). This script
implements them as written. It was committed before the experts' scores were
imported or looked at.

Data: results/mos_results.json, written by
`mos_collector.py --import_scores` (4 experts x 64 layouts x 3 parameters =
768 ratings). The import tags each rating with its layout's poster, format
and condition from the key.

The plan
  Q1  Describe: the MOS (arithmetic mean, ITU-T P.800) and SD of the
      ratings for each parameter and overall (a rating's overall = the mean
      of its three parameters), for GNN and baseline, certificates and event
      IDs; how many 1s-5s each condition received.
  Q2  Agreement: Kendall's W (tie-corrected), for each parameter and
      overall, over the 64 layouts, with its chi-square test (df 63).
  Q3  Main test: the Wilcoxon signed-rank test on the 32 pairs (poster x
      format; GNN vs baseline).
  Q4  Each layout's score is the mean of its four experts' ratings.
  Q5  Both formats in one test; each format's MOS described (Q1), not
      tested separately.
  Q6  The overall MOS is the main test; the three parameters are follow-up
      tests; Holm's correction over the four.
  Q7  Two-sided.
  Q8  A significance level of 0.05.
  Q9  An effect size beside every p-value: the matched-pairs rank-biserial
      correlation r = (W+ - W-) / (W+ + W-); positive = GNN rated higher.
  Q10 Sampling: wording only, nothing to compute.
  Q11 Phase 3 numbers: mean and SD of the fitness (C_total), latency, F1
      and IoU; the same Wilcoxon test (two-sided, with r) for GNN vs
      baseline C_total on the same 32 pairs.

Details fixed with the plan: pairs with equal scores are dropped from the
Wilcoxon test (Wilcoxon's own procedure, scipy's zero_method="wilcox");
scipy picks the exact or the normal-approximation p-value (method="auto"),
and the report says which it used. SDs are sample SDs (n - 1).

Sensitivity analyses (secondary; they check the plan's conclusions, they
don't replace them):
  - the median and IQR beside the mean (Q1's alternative, "alongside");
  - ICC(2,1) and ICC(2,k), two-way random, absolute agreement, and
    Krippendorff's alpha (ordinal for each parameter, interval for the
    overall) (Q2's alternatives);
  - the paired t-test on the same pairs, with Cohen's d_z (Q3's alternative);
  - Bonferroni-adjusted p-values beside Holm's (Q6's alternative);
  - the main tests without the one pair whose two layouts rendered
    identically (key column identical_to_pair).
Not run: a one-sided test (Q7 chose two-sided), per-format tests (Q5), and
a mixed-effects model (Q4's alternative; statsmodels isn't installed).

Usage:
  python src/evaluation/phase4_analysis.py              # -> results/phase4_analysis.json
  python src/evaluation/phase4_analysis.py --simulate   # random ratings, to test this code
"""

import argparse
import csv
import datetime
import json
import os
import random
import statistics
import sys

import numpy as np
import scipy
from scipy import stats

_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_EVAL_DIR)
_ROOT = os.path.dirname(_SRC)

MOS_PATH = os.path.join(_ROOT, "results", "mos_results.json")
KEY_PATH = os.path.join(_ROOT, "data", "phase4", "phase4_key.csv")
OUT_PATH = os.path.join(_ROOT, "results", "phase4_analysis.json")
SIM_OUT = os.path.join(_ROOT, "data", "rendered", "phase4_analysis_simulated.json")
INSTRUMENT = "manuscript_ch3_table2_3param"
PARAMS = {"visual_hierarchy_preservation": "Visual Hierarchy Preservation",
          "brand_typographic_consistency": "Brand and Typographic Consistency",
          "constraint_whitespace_harmony": "Constraint and Whitespace Harmony"}
MEASURES = ["overall", *PARAMS]          # the main test first (Q6)
CONDITIONS = ("gnn", "baseline")
FORMATS = ("certificate", "event_id")
ALPHA = 0.05                             # Q8
EXPERTS = 4


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def read_key() -> list:
    with open(KEY_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ratings_from_mos(path: str) -> list:
    """[(expert, (poster, format, condition), {param: score})] from the
    imported paper-packet ratings."""
    with open(path, encoding="utf-8") as f:
        evals = [e for e in json.load(f)["evaluations"]
                 if e.get("instrument") == INSTRUMENT and e.get("source") == "paper_packet"]
    return [(e["evaluator"], (e["poster_file"], e["format"], e["condition"]), dict(e["scores"])) for e in evals]


def simulated_ratings(key: list, seed: int = 0) -> list:
    """Random ratings with the real design, to test the code without the data."""
    rng = random.Random(seed)
    return [(f"Expert {i + 1}", (r["poster_file"], r["format"], r["condition"]),
             {p: rng.randint(1, 5) for p in PARAMS}) for i in range(EXPERTS) for r in key]


def value(scores: dict, measure: str) -> float:
    return statistics.mean(scores[p] for p in PARAMS) if measure == "overall" else float(scores[measure])


def check_design(ratings: list, key: list) -> dict:
    layouts = {(r["poster_file"], r["format"], r["condition"]) for r in key}
    experts = sorted({e for e, _, _ in ratings})
    seen = {(e, l) for e, l, _ in ratings}
    problems = []
    if len(experts) != EXPERTS:
        problems.append(f"{len(experts)} experts, expected {EXPERTS}")
    for e in experts:
        missing = [l for l in layouts if (e, l) not in seen]
        if missing:
            problems.append(f"{e}: {len(missing)} layout(s) unrated")
    if len(seen) != len(ratings):
        problems.append("a layout rated twice by the same expert")
    if problems:
        sys.exit("Design check failed:\n  " + "\n  ".join(problems))
    return {"experts": experts, "layouts": len(layouts), "ratings": len(ratings) * len(PARAMS)}


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def describe(values: list) -> dict:
    v = np.asarray(values, dtype=float)
    q1, med, q3 = np.percentile(v, [25, 50, 75])
    return {"n": int(v.size), "mean": round(float(v.mean()), 4),
            "sd": round(float(v.std(ddof=1)), 4) if v.size > 1 else None,
            "median": round(float(med), 4), "iqr": [round(float(q1), 4), round(float(q3), 4)]}


def kendall_w(matrix: np.ndarray) -> dict:
    """Kendall's W with the tie correction, for m raters (rows) x n objects."""
    m, n = matrix.shape
    ranks = np.vstack([stats.rankdata(row) for row in matrix])
    r = ranks.sum(axis=0)
    s = float(((r - r.mean()) ** 2).sum())
    ties = 0.0
    for row in matrix:
        _, counts = np.unique(row, return_counts=True)
        ties += float((counts ** 3 - counts).sum())
    w = 12.0 * s / (m ** 2 * (n ** 3 - n) - m * ties)
    chi2 = m * (n - 1) * w
    return {"W": round(w, 4), "chi2": round(chi2, 3), "df": n - 1,
            "p": float(stats.chi2.sf(chi2, n - 1)), "raters": m, "objects": n}


def icc(matrix: np.ndarray) -> dict:
    """ICC(2,1) and ICC(2,k): two-way random effects, absolute agreement
    (Shrout & Fleiss 1979; McGraw & Wong 1996). matrix: n objects x k raters."""
    n, k = matrix.shape
    grand = matrix.mean()
    ss_r = k * ((matrix.mean(axis=1) - grand) ** 2).sum()
    ss_c = n * ((matrix.mean(axis=0) - grand) ** 2).sum()
    ss_e = ((matrix - grand) ** 2).sum() - ss_r - ss_c
    ms_r, ms_c, ms_e = ss_r / (n - 1), ss_c / (k - 1), ss_e / ((n - 1) * (k - 1))
    return {"ICC(2,1)": round(float((ms_r - ms_e) / (ms_r + (k - 1) * ms_e + k * (ms_c - ms_e) / n)), 4),
            "ICC(2,k)": round(float((ms_r - ms_e) / (ms_r + (ms_c - ms_e) / n)), 4)}


def krippendorff_alpha(matrix: np.ndarray, metric: str) -> float:
    """Krippendorff's alpha for complete data, matrix: n units x m coders.
    metric "ordinal" (values on an ordered scale) or "interval"."""
    units = [row for row in matrix]
    values = np.unique(matrix)
    idx = {v: i for i, v in enumerate(values)}
    o = np.zeros((len(values), len(values)))
    for row in units:
        m = len(row)
        for a in range(m):
            for b in range(m):
                if a != b:
                    o[idx[row[a]], idx[row[b]]] += 1.0 / (m - 1)
    n_c = o.sum(axis=1)
    n = n_c.sum()
    if metric == "ordinal":
        cum = np.cumsum(n_c)
        d2 = np.zeros_like(o)
        for c in range(len(values)):
            for k in range(len(values)):
                lo, hi = min(c, k), max(c, k)
                d2[c, k] = (cum[hi] - (cum[lo - 1] if lo else 0.0) - (n_c[c] + n_c[k]) / 2.0) ** 2
    else:
        d2 = (values[:, None] - values[None, :]) ** 2
    d_o = (o * d2).sum()
    d_e = (np.outer(n_c, n_c) * d2).sum() / (n - 1)
    return round(float(1.0 - d_o / d_e), 4)


def wilcoxon(diffs: list) -> dict:
    """Two-sided Wilcoxon signed-rank test with the matched-pairs
    rank-biserial r (Q3, Q7, Q9)."""
    d = np.round(np.asarray(diffs, dtype=float), 10)
    nz = d[d != 0]
    out = {"pairs": int(d.size), "nonzero": int(nz.size), "higher": int((d > 0).sum()),
           "lower": int((d < 0).sum()), "equal": int((d == 0).sum()),
           "mean_diff": round(float(d.mean()), 4), "median_diff": round(float(np.median(d)), 4)}
    if nz.size == 0:
        return {**out, "W_plus": 0.0, "W_minus": 0.0, "statistic": None, "p": 1.0, "method": "no nonzero pairs",
                "r": 0.0}
    ranks = stats.rankdata(np.abs(nz))
    w_plus, w_minus = float(ranks[nz > 0].sum()), float(ranks[nz < 0].sum())
    res = stats.wilcoxon(d, zero_method="wilcox", alternative="two-sided", method="auto")
    try:
        exact = stats.wilcoxon(d, zero_method="wilcox", alternative="two-sided", method="exact").pvalue
    except (ValueError, NotImplementedError):
        exact = None
    method = "exact" if exact is not None and np.isclose(exact, res.pvalue) else "normal approximation"
    return {**out, "W_plus": w_plus, "W_minus": w_minus, "statistic": float(res.statistic),
            "p": float(res.pvalue), "method": method,
            "r": round((w_plus - w_minus) / (w_plus + w_minus), 4)}


def paired_t(gnn: list, base: list) -> dict:
    d = np.asarray(gnn) - np.asarray(base)
    res = stats.ttest_rel(gnn, base)
    sd = d.std(ddof=1)
    return {"t": round(float(res.statistic), 4), "df": int(d.size - 1), "p": float(res.pvalue),
            "mean_diff": round(float(d.mean()), 4), "cohen_dz": round(float(d.mean() / sd), 4) if sd else None}


def holm(pvalues: dict) -> dict:
    order = sorted(pvalues, key=pvalues.get)
    m, running, out = len(order), 0.0, {}
    for i, name in enumerate(order):
        running = max(running, min(1.0, (m - i) * pvalues[name]))
        out[name] = running
    return out


def bonferroni(pvalues: dict) -> dict:
    return {k: min(1.0, len(pvalues) * p) for k, p in pvalues.items()}


# ---------------------------------------------------------------------------
# The analysis
# ---------------------------------------------------------------------------

def analyse(ratings: list, key: list) -> dict:
    design = check_design(ratings, key)
    experts = design["experts"]
    layouts = sorted({l for _, l, _ in ratings})
    by = {(e, l): s for e, l, s in ratings}
    identical = {(r["poster_file"], r["format"]) for r in key
                 if str(r.get("identical_to_pair", "")).strip().lower() in ("true", "yes", "1")}

    # Q1: describing the ratings
    def cell(measure, fmt=None, cond=None):
        return describe([value(s, measure) for (e, l), s in by.items()
                         if (fmt is None or l[1] == fmt) and (cond is None or l[2] == cond)])

    q1 = {"all": {m: cell(m) for m in MEASURES}}
    for cond in CONDITIONS:
        q1[cond] = {m: cell(m, cond=cond) for m in MEASURES}
        for fmt in FORMATS:
            q1[f"{fmt} {cond}"] = {m: cell(m, fmt, cond) for m in MEASURES}
    counts = {}
    for cond in CONDITIONS:
        counts[cond] = {p: {str(v): sum(1 for (e, l), s in by.items() if l[2] == cond and s[p] == v)
                            for v in range(1, 6)} for p in PARAMS}
        counts[cond]["all three"] = {str(v): sum(counts[cond][p][str(v)] for p in PARAMS) for v in range(1, 6)}

    # Q2: agreement over the 64 layouts (and the sensitivity measures)
    q2, agreement_sens = {}, {}
    for m in MEASURES:
        matrix = np.array([[value(by[(e, l)], m) for e in experts] for l in layouts])   # layouts x experts
        q2[m] = kendall_w(matrix.T)
        agreement_sens[m] = {**icc(matrix),
                             "krippendorff_alpha": krippendorff_alpha(matrix, "interval" if m == "overall" else "ordinal"),
                             "alpha_metric": "interval" if m == "overall" else "ordinal"}

    # Q3-Q9: each layout's MOS (Q4), the 32 pairs (Q5), Wilcoxon (Q3, Q7, Q9), Holm (Q6)
    mos = {l: {m: statistics.mean(value(by[(e, l)], m) for e in experts) for m in MEASURES} for l in layouts}
    pairs = sorted({(l[0], l[1]) for l in layouts})

    def tests(selected):
        res = {m: wilcoxon([mos[(p, f, "gnn")][m] - mos[(p, f, "baseline")][m] for p, f in selected])
               for m in MEASURES}
        adj = holm({m: r["p"] for m, r in res.items()})
        bon = bonferroni({m: r["p"] for m, r in res.items()})
        for m, r in res.items():
            r["p_holm"] = adj[m]
            r["p_bonferroni"] = bon[m]
            r["significant_holm"] = adj[m] < ALPHA
        return res

    main = tests(pairs)
    pair_rows = [{"poster": p, "format": f, "identical_layouts": (p, f) in identical,
                  **{f"{m}_gnn": round(mos[(p, f, "gnn")][m], 4) for m in MEASURES},
                  **{f"{m}_baseline": round(mos[(p, f, "baseline")][m], 4) for m in MEASURES}}
                 for p, f in pairs]
    t_tests = {m: paired_t([mos[(p, f, "gnn")][m] for p, f in pairs],
                           [mos[(p, f, "baseline")][m] for p, f in pairs]) for m in MEASURES}
    without_identical = tests([pf for pf in pairs if pf not in identical]) if identical else None

    # Q11: the system's own numbers
    q11 = phase3_numbers(key, pairs)

    return {
        "design": {**design, "pairs": len(pairs), "identical_pairs": sorted(f"{p} {f}" for p, f in identical)},
        "plan": {"significance_level": ALPHA, "main_test": "overall MOS", "correction": "Holm, over 4 tests",
                 "sides": "two-sided", "zero_method": "wilcox (pairs with equal MOS dropped)",
                 "effect_size": "matched-pairs rank-biserial r = (W+ - W-)/(W+ + W-); positive = GNN higher",
                 "scipy": scipy.__version__},
        "q1_describe": q1, "q1_rating_counts": counts,
        "q2_kendall_w": q2,
        "q3_q9_wilcoxon": main,
        "pairs": pair_rows,
        "q11_phase3": q11,
        "sensitivity": {
            "agreement_icc_krippendorff": agreement_sens,
            "paired_t": t_tests,
            "wilcoxon_without_identical_pair": without_identical,
        },
    }


def phase3_numbers(key: list, pairs: list) -> dict:
    """Q11: mean and SD of the fitness, latency, F1 and IoU; Wilcoxon for
    GNN vs baseline C_total on the 32 pairs (lower C_total is better)."""
    c = {(r["poster_file"], r["format"], r["condition"]): float(r["c_total"]) for r in key}
    out = {"c_total": {cond: describe([v for (p, f, cd), v in c.items() if cd == cond]) for cond in CONDITIONS}}
    for fmt in FORMATS:
        for cond in CONDITIONS:
            out["c_total"][f"{fmt} {cond}"] = describe([v for (p, f, cd), v in c.items() if f == fmt and cd == cond])
    test = wilcoxon([c[(p, f, "gnn")] - c[(p, f, "baseline")] for p, f in pairs])
    test["reading"] = "positive r / 'higher' = the GNN's C_total is higher, i.e. worse (Formula 3.11 is minimised)"
    out["c_total_wilcoxon"] = test

    def load(name):
        path = os.path.join(_ROOT, "results", name)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    lat = load("latency_benchmark.json")
    if lat:
        events = [e for r in lat["runs"] for e in r["events"]]
        out["latency_ms"] = {"solver": describe([e["solver_ms"] for e in events if e["solver_ms"] is not None]),
                             "full_edit": describe([e["full_ms"] for e in events]),
                             "source": "results/latency_benchmark.json"}
    f1 = load("rated_layouts_check.json")
    if f1:
        out["f1_rated_layouts"] = {cond: describe([r["f1"] for r in f1["rows"] if r["condition"] == cond])
                                   for cond in CONDITIONS}
        out["f1_rated_layouts"]["source"] = "results/rated_layouts_check.json"
    iou = load("yolo_iou.json")
    if iou:
        res = iou["results"][next(iter(iou["results"]))]["all"]
        out["detector_iou"] = {k: res.get(k) for k in ("ground_truth_boxes", "strict_mean_iou", "strict_sd",
                                                       "found", "found_mean_iou", "found_sd")}
        out["detector_iou"]["source"] = "results/yolo_iou.json (all 40 validation images)"
    return out


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _p(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def print_report(a: dict) -> None:
    d = a["design"]
    print(f"\n  {d['experts']} — {d['layouts']} layouts, {d['ratings']} ratings, {d['pairs']} pairs")
    print("\n  Q1  MOS ± SD (median, IQR)")
    for group in ("gnn", "baseline", "certificate gnn", "certificate baseline", "event_id gnn", "event_id baseline"):
        cells = a["q1_describe"][group]
        print(f"    {group:<22} " + "  ".join(
            f"{m[:10]:>10} {c['mean']:.2f}±{c['sd']:.2f}" for m, c in cells.items()))
    print("\n  Q2  Kendall's W")
    for m, w in a["q2_kendall_w"].items():
        print(f"    {m:<32} W = {w['W']:.3f}  chi2({w['df']}) = {w['chi2']:.1f}  p = {_p(w['p'])}")
    print("\n  Q3-Q9  Wilcoxon signed-rank, 32 pairs, two-sided, Holm over 4")
    for m, r in a["q3_q9_wilcoxon"].items():
        print(f"    {m:<32} GNN higher {r['higher']}, lower {r['lower']}, equal {r['equal']}; "
              f"median diff {r['median_diff']:+.3f}; W = {r['statistic']}; p = {_p(r['p'])} "
              f"(Holm {_p(r['p_holm'])}; {r['method']}); r = {r['r']:+.3f}")
    q = a["q11_phase3"]["c_total_wilcoxon"]
    print(f"\n  Q11 C_total, GNN vs baseline: GNN higher {q['higher']}, lower {q['lower']}, equal {q['equal']}; "
          f"p = {_p(q['p'])}; r = {q['r']:+.3f}")


def main():
    parser = argparse.ArgumentParser(description="Phase 4 statistical analysis (the adopted plan)")
    parser.add_argument("--simulate", action="store_true", help="random ratings with the real design")
    args = parser.parse_args()
    key = read_key()
    ratings = simulated_ratings(key) if args.simulate else ratings_from_mos(MOS_PATH)
    result = {"generated": datetime.datetime.now().isoformat(timespec="seconds"),
              "data": "SIMULATED random ratings (code test only)" if args.simulate else os.path.relpath(MOS_PATH, _ROOT),
              **analyse(ratings, key)}
    out = SIM_OUT if args.simulate else OUT_PATH
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    print_report(result)
    print(f"\n  -> {os.path.relpath(out, _ROOT)}")


if __name__ == "__main__":
    main()
