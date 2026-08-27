"""
ThemeSync — Mean Opinion Score (MOS) Collector
================================================
A simple CLI tool for expert evaluators to rate rendered ThemeSync layouts
on a 1–5 Likert scale across the four perceptual dimensions specified in
the manuscript evaluation protocol.

Dimensions:
  1. Aesthetic Quality   — Overall visual appeal
  2. Spatial Coherence   — Logical placement and hierarchy
  3. Legibility          — Text readability and contrast
  4. Layout Balance      — Symmetry and whitespace distribution

Usage:
  python src/evaluation/mos_collector.py --rendered_dir data/rendered/
  python src/evaluation/mos_collector.py --rendered_dir data/rendered/ --evaluator "Evaluator A"
  python src/evaluation/mos_collector.py --report              # View existing results
"""

import argparse
import glob
import json
import os
import sys
import datetime

_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC      = os.path.dirname(_EVAL_DIR)
_ROOT     = os.path.dirname(_SRC)

RESULTS_PATH = os.path.join(_ROOT, "results", "mos_results.json")
DIMENSIONS = [
    ("aesthetic_quality",  "Aesthetic Quality   (1=Poor, 5=Excellent)"),
    ("spatial_coherence",  "Spatial Coherence   (1=Poor, 5=Excellent)"),
    ("legibility",         "Legibility          (1=Poor, 5=Excellent)"),
    ("layout_balance",     "Layout Balance      (1=Poor, 5=Excellent)"),
]


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _load_results() -> dict:
    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH, "r") as f:
            return json.load(f)
    return {"evaluations": []}


def _save_results(data: dict) -> None:
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _prompt_rating(dimension_label: str) -> int:
    while True:
        try:
            raw = input(f"    {dimension_label}: ").strip()
            score = int(raw)
            if 1 <= score <= 5:
                return score
            print("    ✘  Please enter a number between 1 and 5.")
        except ValueError:
            print("    ✘  Invalid input — enter a digit (1–5).")
        except (EOFError, KeyboardInterrupt):
            print("\n  Evaluation cancelled.")
            sys.exit(0)


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

def collect_ratings(rendered_dir: str, evaluator_name: str) -> None:
    svg_files = sorted(glob.glob(os.path.join(rendered_dir, "*.svg")))
    if not svg_files:
        print(f"  No SVG files found in '{rendered_dir}'.")
        sys.exit(1)

    data = _load_results()
    session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n{'='*60}")
    print("  ThemeSync — MOS Collection Session")
    print(f"{'='*60}")
    print(f"  Evaluator : {evaluator_name}")
    print(f"  Session   : {session_id}")
    print(f"  Files     : {len(svg_files)} layout(s) to evaluate")
    print(f"  Scale     : 1 (Poor) → 5 (Excellent)")
    print(f"{'='*60}\n")

    for i, svg_path in enumerate(svg_files):
        filename = os.path.basename(svg_path)
        print(f"  [{i+1}/{len(svg_files)}] Layout: {filename}")
        print(f"  Open the file to view: {svg_path}\n")

        scores = {}
        for dim_key, dim_label in DIMENSIONS:
            scores[dim_key] = _prompt_rating(dim_label)

        mean_score = round(sum(scores.values()) / len(scores), 2)
        print(f"\n    → MOS for this layout: {mean_score:.2f} / 5.00\n")

        optional = input("    Optional comment (press Enter to skip): ").strip()

        evaluation_entry = {
            "session_id":    session_id,
            "evaluator":     evaluator_name,
            "layout_file":   filename,
            "timestamp":     datetime.datetime.now().isoformat(timespec="seconds"),
            "scores":        scores,
            "mean_mos":      mean_score,
            "comment":       optional or None,
        }
        data["evaluations"].append(evaluation_entry)
        _save_results(data)
        print(f"  ✔  Saved. ({RESULTS_PATH})\n")
        print(f"  {'─'*56}\n")

    print(f"  Session complete. {len(svg_files)} layout(s) rated.")
    print_report()


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report() -> None:
    data = _load_results()
    evals = data.get("evaluations", [])

    if not evals:
        print("  No MOS data collected yet.")
        return

    # Group by layout file
    by_layout: dict[str, list] = {}
    for e in evals:
        by_layout.setdefault(e["layout_file"], []).append(e)

    print(f"\n{'='*66}")
    print("  ThemeSync — MOS Report")
    print(f"{'='*66}")
    print(f"  Total evaluations : {len(evals)}")
    print(f"  Unique layouts    : {len(by_layout)}")
    print(f"  Unique evaluators : {len(set(e['evaluator'] for e in evals))}\n")

    # Per-layout aggregate
    print(f"  {'Layout File':<40} {'N':>4} {'Aesthetic':>10} {'Coherence':>10} "
          f"{'Legibility':>11} {'Balance':>8} {'MOS':>6}")
    print(f"  {'-'*40} {'-'*4} {'-'*10} {'-'*10} {'-'*11} {'-'*8} {'-'*6}")

    for layout_file, layout_evals in sorted(by_layout.items()):
        n = len(layout_evals)
        def _mean(dim):
            return round(sum(e["scores"].get(dim, 0) for e in layout_evals) / n, 2)
        aes  = _mean("aesthetic_quality")
        coh  = _mean("spatial_coherence")
        leg  = _mean("legibility")
        bal  = _mean("layout_balance")
        mos  = round((aes + coh + leg + bal) / 4, 2)
        name = layout_file[:38] + ".." if len(layout_file) > 40 else layout_file
        print(f"  {name:<40} {n:>4} {aes:>10.2f} {coh:>10.2f} {leg:>11.2f} {bal:>8.2f} {mos:>6.2f}")

    # Overall MOS
    all_mos = [e["mean_mos"] for e in evals]
    overall = round(sum(all_mos) / len(all_mos), 2)
    print(f"\n  Overall Mean Opinion Score (MOS): {overall:.2f} / 5.00")
    print(f"\n  Results file: {RESULTS_PATH}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ThemeSync MOS Collector")
    parser.add_argument(
        "--rendered_dir", type=str, default="data/rendered/",
        help="Directory containing rendered SVG layouts to evaluate",
    )
    parser.add_argument(
        "--evaluator", type=str, default="Evaluator",
        help="Name/label for this evaluator (default: 'Evaluator')",
    )
    parser.add_argument(
        "--report", action="store_true",
        help="Print a summary report of all collected MOS scores and exit",
    )
    args = parser.parse_args()

    if args.report:
        print_report()
    else:
        collect_ratings(args.rendered_dir, args.evaluator)


if __name__ == "__main__":
    main()
