"""
ThemeSync — Post-evaluation refinement check (analysis only)
=============================================================
After the Phase 4 evaluation (notes §3.57), the system's output changed:
cut-outs segmented with SAM 2.1, and the gaps redistributed after anchoring
(Chapter 5, Recommendation 3). The experts rated the code tagged
`phase4-rated` (commit 8422282); nothing here changes those layouts, their
key, or the MOS.

This regenerates the 16 Phase 4 posters' layouts with the current code, the
way the packet made them (phase4_packet.generate_sample, the manifest's
content and per-poster choices), and measures them as the rated set was
measured:

  spacing   phase4_posthoc.spacing: largest gap, gap CV, spread — the
            measures that went with the lower MOS
  checks    rated_layouts_check.check: F1 (p.56), reading order, text fit,
            ink clashes

and sets them beside the rated layouts' spacing (results/phase4_posthoc.json).

Usage:
  python src/evaluation/refinement_check.py --label after
  python src/evaluation/refinement_check.py --label after --conditions gnn baseline --posters CTC.jpg

Writes data/rendered/refinement/<label>/ (git-ignored) and
results/refinement_check_<label>.json.
"""

import argparse
import datetime
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

import phase4_packet as p4                                     # noqa: E402
import phase4_posthoc as ph                                    # noqa: E402
import rated_layouts_check as rlc                              # noqa: E402
import stress_test as st                                       # noqa: E402

OUT_ROOT = os.path.join(_ROOT, "data", "rendered", "refinement")
RATED = os.path.join(_ROOT, "results", "phase4_posthoc.json")


def summarise(rows: list) -> dict:
    out = {}
    for k in ph.MEASURES:
        values = [r["spacing"][k] for r in rows]
        out[k] = {"mean": round(statistics.mean(values), 4), "median": round(statistics.median(values), 4),
                  "max": round(max(values), 4)}
    out["f1_below_1"] = sum(r["f1"] < 1 for r in rows)
    out["text_overflowing"] = sum(bool(r["text_overflowing"]) for r in rows)
    out["ink_clashes"] = sum(bool(r["text_over_text"] or r["text_over_picture"]) for r in rows)
    out["order_violations"] = sum(bool(r["reading_order_violations"]) for r in rows)
    out["n"] = len(rows)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", required=True, help="names the output folder and JSON (e.g. before, after)")
    ap.add_argument("--conditions", nargs="+", default=["gnn"], choices=list(p4.CONDITIONS))
    ap.add_argument("--posters", nargs="+", help="poster files (default: all 16 in the manifest)")
    args = ap.parse_args()

    rows_in = sorted([r for r in p4.read_manifest(p4.POSTERS_DIR) if r.get("poster_file")],
                     key=lambda r: r["poster_file"])
    root = os.path.join(OUT_ROOT, args.label)
    rlc.SAMPLES = ph.SAMPLES = os.path.join(root, "samples")
    metrics = st.FontMetrics()
    rows = []
    for i, row in enumerate(rows_in):     # i: content_for's index, as in the packet
        if args.posters and row["poster_file"] not in args.posters:
            continue
        stem = os.path.splitext(row["poster_file"])[0]
        content = p4.content_for(row, i)
        for fmt in p4.FORMATS:
            for cond in args.conditions:
                out_dir = os.path.join(rlc.SAMPLES, stem, f"{fmt}_{cond}")
                p4.generate_sample(os.path.join(p4.POSTERS_DIR, row["poster_file"]), content, fmt, cond, out_dir,
                                   p4.logo_paths(row, p4.POSTERS_DIR), use_wordmark=p4.use_title_artwork(row),
                                   use_motifs=p4.use_motifs(row))
                r = rlc.check(row["poster_file"], fmt, cond, metrics, key=None)
                r["spacing"] = ph.spacing(*ph.layout_nodes(row["poster_file"], fmt, cond))
                rows.append(r)
                s = r["spacing"]
                print(f"  {stem[:26]:<26} {fmt:<11} {cond:<8} gap {s['largest_gap']:.3f}  cv {s['gap_cv']:.2f}  "
                      f"spread {s['spread']:.2f}  F1 {r['f1']:.2f}"
                      + (f"  overflow {', '.join(r['text_overflowing'])}" if r["text_overflowing"] else ""), flush=True)

    result = {"generated": datetime.datetime.now().isoformat(timespec="seconds"), "label": args.label,
              "status": "ANALYSIS ONLY: the current code, not the rated layouts (tag phase4-rated)",
              "summary": {c: summarise([r for r in rows if r["condition"] == c]) for c in args.conditions},
              "rows": rows}
    if os.path.exists(RATED):
        with open(RATED, encoding="utf-8") as f:
            result["rated_spacing"] = json.load(f)["layout_spacing"]
    path = os.path.join(_ROOT, "results", f"refinement_check_{args.label}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)
    print(json.dumps(result["summary"], indent=1))
    print(f"\n  -> {os.path.relpath(path, _ROOT)}")


if __name__ == "__main__":
    main()
