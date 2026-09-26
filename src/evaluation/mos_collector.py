"""
ThemeSync — Mean Opinion Score (MOS) Collector
================================================
A simple CLI tool for the Phase 4 domain expert to rate rendered ThemeSync
layouts on the manuscript's 5-point Likert scale (Chapter 3, "Mean Opinion
Score (MOS) for Aesthetic Alignment", pp. 57-58).

Core design parameters (scored separately, 1-5 each):
  1. Visual Hierarchy Preservation      — correct structural dominance
  2. Brand and Typographic Consistency  — Hybrid Visual DNA rendered faithfully
  3. Constraint and Whitespace Harmony  — no occlusion, professional negative space

Each score is anchored to Table 2 (Mean Opinion Score Rating Scale for
Aesthetic Alignment), which is shown to the evaluator at the start of the
session and can be re-displayed at any prompt by typing "?".

Layouts are presented in a randomized order (the manuscript specifies "a
randomized sample of the generated layouts"); the seed is recorded with every
rating so the exact order can be reproduced.

Usage:
  python src/evaluation/mos_collector.py --rendered_dir data/rendered/
  python src/evaluation/mos_collector.py --rendered_dir data/rendered/ --evaluator "Evaluator A"
  python src/evaluation/mos_collector.py --rendered_dir data/rendered/ --sample_size 10 --seed 42
  python src/evaluation/mos_collector.py --report              # View existing results
"""

import argparse
import glob
import json
import os
import random
import statistics
import sys
import datetime

_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC      = os.path.dirname(_EVAL_DIR)
_ROOT     = os.path.dirname(_SRC)

RESULTS_PATH = os.path.join(_ROOT, "results", "mos_results.json")
INSTRUMENT   = "manuscript_ch3_table2_3param"

# (key, name as written in the manuscript, what the evaluator is judging — p.57)
DIMENSIONS = [
    ("visual_hierarchy_preservation",
     "Visual Hierarchy Preservation",
     "Does the placement keep the correct structural dominance? (e.g., the "
     "recipient's name or the certificate title remains the primary focal "
     "point relative to the surrounding elements)"),
    ("brand_typographic_consistency",
     "Brand and Typographic Consistency",
     "Are the user-defined fonts, baseline geometric sizes, and extracted "
     "color palette rendered accurately, without hallucinated colors or "
     "typefaces?"),
    ("constraint_whitespace_harmony",
     "Constraint and Whitespace Harmony",
     "Is the layout free of element occlusion (overlapping text/graphics), "
     "with negative space that meets professional composition standards?"),
]

# Table 2: Mean Opinion Score Rating Scale for Aesthetic Alignment (p.58)
RATING_SCALE = [
    (5, "Excellent",  "No noticeable flaws"),
    (4, "Good",       "Minor aesthetic deviations"),
    (3, "Acceptable", "Noticeable but non-destructive deviations"),
    (2, "Poor",       "Significant layout fragility"),
    (1, "Fail",       "Severe structural overlap or typographic failure"),
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


def _print_rating_scale() -> None:
    print("    Table 2 — MOS Rating Scale for Aesthetic Alignment")
    print(f"    {'Score':<7}{'Rating':<12}Description")
    for score, rating, description in RATING_SCALE:
        print(f"    {score:<7}{rating:<12}{description}")
    print()


def _prompt_rating(dimension_name: str, criterion: str) -> int:
    print(f"    {dimension_name}")
    print(f"      {criterion}")
    while True:
        try:
            raw = input("      Score 1-5 (? = show Table 2): ").strip()
            if raw == "?":
                print()
                _print_rating_scale()
                continue
            score = int(raw)
            if 1 <= score <= 5:
                rating = next(r for s, r, _ in RATING_SCALE if s == score)
                print(f"      → {score} ({rating})\n")
                return score
            print("      ✘  Please enter a number between 1 and 5.")
        except ValueError:
            print("      ✘  Invalid input — enter a digit (1–5), or ? for the scale.")
        except (EOFError, KeyboardInterrupt):
            print("\n  Evaluation cancelled.")
            sys.exit(0)


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

def collect_ratings(rendered_dir: str, evaluator_name: str,
                    sample_size: int | None = None, seed: int | None = None) -> None:
    svg_files = sorted(glob.glob(os.path.join(rendered_dir, "*.svg")))
    if not svg_files:
        print(f"  No SVG files found in '{rendered_dir}'.")
        sys.exit(1)

    if seed is None:
        seed = random.SystemRandom().randrange(2**31)
    rng = random.Random(seed)
    if sample_size is not None and 0 < sample_size < len(svg_files):
        svg_files = rng.sample(svg_files, sample_size)
    else:
        rng.shuffle(svg_files)

    data = _load_results()
    session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n{'='*66}")
    print("  ThemeSync — MOS Collection Session (Phase 4 Aesthetic Alignment)")
    print(f"{'='*66}")
    print(f"  Evaluator : {evaluator_name}")
    print(f"  Session   : {session_id}")
    print(f"  Files     : {len(svg_files)} layout(s) to evaluate, randomized order (seed {seed})")
    print(f"  Criteria  : {len(DIMENSIONS)} design parameters, each scored 1–5")
    print(f"{'='*66}\n")
    _print_rating_scale()

    for i, svg_path in enumerate(svg_files):
        filename = os.path.basename(svg_path)
        print(f"  [{i+1}/{len(svg_files)}] Layout: {filename}")
        print(f"  Open the file to view: {svg_path}\n")

        scores = {}
        for dim_key, dim_name, criterion in DIMENSIONS:
            scores[dim_key] = _prompt_rating(dim_name, criterion)

        mean_score = round(sum(scores.values()) / len(scores), 2)
        print(f"    → MOS for this layout: {mean_score:.2f} / 5.00\n")

        optional = input("    Optional comment (press Enter to skip): ").strip()

        evaluation_entry = {
            "session_id":         session_id,
            "instrument":         INSTRUMENT,
            "evaluator":          evaluator_name,
            "layout_file":        filename,
            "presentation_order": i + 1,
            "order_seed":         seed,
            "timestamp":          datetime.datetime.now().isoformat(timespec="seconds"),
            "scores":             scores,
            "mean_mos":           mean_score,
            "comment":            optional or None,
        }
        data["evaluations"].append(evaluation_entry)
        _save_results(data)
        print(f"  ✔  Saved. ({RESULTS_PATH})\n")
        print(f"  {'─'*62}\n")

    print(f"  Session complete. {len(svg_files)} layout(s) rated.")
    print_report()


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _fmt_sd(values: list) -> str:
    return f"{statistics.stdev(values):.2f}" if len(values) > 1 else "n/a"


def print_report() -> None:
    data = _load_results()
    evals = [e for e in data.get("evaluations", []) if e.get("instrument") == INSTRUMENT]
    skipped = len(data.get("evaluations", [])) - len(evals)

    if not evals:
        print("  No MOS data collected yet.")
        return

    # Group by layout file
    by_layout: dict[str, list] = {}
    for e in evals:
        by_layout.setdefault(e["layout_file"], []).append(e)

    print(f"\n{'='*72}")
    print("  ThemeSync — MOS Report (Phase 4 Aesthetic Alignment)")
    print(f"{'='*72}")
    print(f"  Total evaluations : {len(evals)}")
    print(f"  Unique layouts    : {len(by_layout)}")
    print(f"  Unique evaluators : {len(set(e['evaluator'] for e in evals))}")
    if skipped:
        print(f"  Skipped           : {skipped} entr(y/ies) from an older rating instrument")
    print()

    # Per-layout aggregate
    print(f"  {'Layout File':<36} {'N':>3} {'Hierarchy':>10} {'Brand/Typo':>11} "
          f"{'Whitespace':>11} {'MOS':>6}")
    print(f"  {'-'*36} {'-'*3} {'-'*10} {'-'*11} {'-'*11} {'-'*6}")

    for layout_file, layout_evals in sorted(by_layout.items()):
        n = len(layout_evals)
        means = [statistics.mean(e["scores"][k] for e in layout_evals) for k, _, _ in DIMENSIONS]
        mos  = statistics.mean(e["mean_mos"] for e in layout_evals)
        name = layout_file[:34] + ".." if len(layout_file) > 36 else layout_file
        print(f"  {name:<36} {n:>3} {means[0]:>10.2f} {means[1]:>11.2f} "
              f"{means[2]:>11.2f} {mos:>6.2f}")

    # Per-parameter aggregate across the tested dataset
    print(f"\n  {'Design Parameter':<36} {'Mean':>6} {'SD':>6}")
    print(f"  {'-'*36} {'-'*6} {'-'*6}")
    for dim_key, dim_name, _ in DIMENSIONS:
        values = [e["scores"][dim_key] for e in evals]
        print(f"  {dim_name:<36} {statistics.mean(values):>6.2f} {_fmt_sd(values):>6}")

    # Overall MOS — the manuscript's final validation metric
    all_mos = [e["mean_mos"] for e in evals]
    overall = statistics.mean(all_mos)
    rating  = next(r for s, r, _ in RATING_SCALE if s == max(1, min(5, round(overall))))
    print(f"\n  Overall Mean Opinion Score (MOS): {overall:.2f} / 5.00 "
          f"(SD {_fmt_sd(all_mos)}, nearest Table 2 rating: {rating})")
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
        "--sample_size", type=int, default=None,
        help="Rate a random sample of N layouts instead of all of them",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Seed for the randomized presentation order (default: random, recorded in results)",
    )
    parser.add_argument(
        "--report", action="store_true",
        help="Print a summary report of all collected MOS scores and exit",
    )
    args = parser.parse_args()

    if args.report:
        print_report()
    else:
        collect_ratings(args.rendered_dir, args.evaluator, args.sample_size, args.seed)


if __name__ == "__main__":
    main()
