"""
ThemeSync — Experiment Runner (Phase 3 battery)
================================================
Runs the full pipeline (OrchestrationSession: Stages 0-6, the same code the
dashboard and the Phase 4 packet use) on a set of real master layouts, for
each target format, under three Stage 2 conditions (notes §3.26):

  gnn       the master's mapped structure refined by the GNN (the default)
  mapping   the mapped structure alone, no GNN (the ablation)
  baseline  no structure, no GNN: the naive stack

and writes results/experiment_log.json for notebooks/results_analysis.ipynb.

Each run records p.56's F1 (layout_report.structural_accuracy: FP = an
element overlapping another or leaving the canvas, FN = one missing).

Besides the fitness terms (Formula 3.11), each run records its structure
error: how far the winning layout's anchored elements (logo row, header,
title, details — whichever the format maps) sit vertically from their
counterparts on the master, as a fraction of the height. It measures what
the fitness function can't: whether the output keeps the master's
composition.

Each "trial" is one master layout. The pipeline is deterministic for a given
input, so repeating one input only repeats its numbers; what varies — and
what the fitness comparison needs — is the master: its palette, motifs and
background, against which the Legibility Penalty (Formula 3.15) now scores
every candidate (notes §3.23).

Content: a poster listed in data/raw/phase4_posters/manifest.csv gets its
own event text (phase4_packet.content_for); any other gets the format's
sample content.

Usage:
  python src/evaluation/experiment_runner.py                     # the 15 Phase 4 posters
  python src/evaluation/experiment_runner.py --limit 5 --domains id
  python src/evaluation/experiment_runner.py --posters_dir data/raw/some_posters
"""

import argparse
import contextlib
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
import structure_mapping                   # noqa: E402 — on the path via pipeline
from layout_report import structural_accuracy  # noqa: E402
from PIL import Image                      # noqa: E402

CONDITIONS = ("gnn", "mapping", "baseline")

DOMAIN_CONFIGS = {
    "certificate": {
        "label":   "Academic Certificate (4:3)",
        "payload": os.path.join(_ROOT, "data", "raw", "academic_payload.json"),
        "sample":  os.path.join(_ROOT, "data", "raw", "sample_content.json"),
        "format":  "certificate",
    },
    "id": {
        "label":   "Event ID (A6, 1:1.414)",
        "payload": os.path.join(_ROOT, "data", "raw", "id_payload.json"),
        "sample":  os.path.join(_ROOT, "data", "raw", "sample_content_id.json"),
        "format":  "event_id",
    },
}
RUNS_DIR = os.path.join(_ROOT, "data", "rendered", "phase3")
SEPARATOR = "=" * 72


def _iou(a: list, b: list) -> float:
    ix = max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


def _content(poster_file: str, cfg: dict, manifest: dict, names: list) -> dict:
    row = manifest.get(poster_file)
    if row and row.get("event_title", "").strip():
        return p4.content_for(row, names.index(poster_file))[cfg["format"]]
    with open(cfg["sample"]) as f:
        return json.load(f)


def master_structure_of(session) -> dict:
    """The master's structure, measured the same way for every condition
    (including those that don't use it)."""
    if not session.detected_nodes or not session.template_image:
        return {}
    if session.structure:
        return session.structure
    with Image.open(session.template_image) as img:
        mw, mh = img.size
    return structure_mapping.master_structure(session.detected_nodes, mw, mh,
                                              pipeline._select_logo_row(session.detected_nodes, mh))


def structure_error(session, nodes: list, structure: dict = None):
    """Mean |output − master| vertical centre (fraction of the height) over
    the stacked nodes the master's structure maps to; None without a
    master or without mapped roles."""
    structure = master_structure_of(session) if structure is None else structure
    if not structure:
        return None
    stack = pipeline._stack(nodes)
    anchors = structure_mapping.anchors_for(stack, structure, session.domain)
    if not anchors:
        return None
    return round(statistics.mean(abs((stack[i]["bbox"][1] + stack[i]["bbox"][3] / 2.0) / session.canvas_h - cy)
                                 for i, (_, cy) in anchors.items()), 4)


def run_single(poster_path: str, domain_key: str, condition: str, content: dict,
               population: int = 6) -> dict:
    """One full pipeline pass on one master layout; returns its metrics."""
    cfg = DOMAIN_CONFIGS[domain_key]
    stem = os.path.splitext(os.path.basename(poster_path))[0]
    out_dir = os.path.join(RUNS_DIR, stem, f"{domain_key}_{condition}")
    use_gnn = condition == "gnn"
    session = pipeline.OrchestrationSession(cfg["payload"], template_image=poster_path,
                                            content_data=content, use_gnn=use_gnn,
                                            use_structure=condition in ("gnn", "mapping"),
                                            output_dir=out_dir, population=population)
    with contextlib.redirect_stdout(io.StringIO()):
        summary = session.run()
    winner = session.candidates[0]
    metrics = winner["metrics"]
    structure = master_structure_of(session)

    # GNN–solver overlap: the IoU between the GNN's predicted boxes (before
    # the solver) and where the solver finally put them — how much of the
    # prediction survived Stage 3. Not p.62's IoU (the detector's,
    # yolo_iou.py); called "mean_iou" before 2026-10-09.
    overlap = None
    if use_gnn:
        resolved = {n["node_id"]: n["bbox"] for n in winner["nodes"]}
        pairs = [(n["bbox"], resolved[n["node_id"]]) for n in session.guided_nodes
                 if n.get("gnn_predicted") and n["node_id"] in resolved]
        overlap = round(sum(_iou(a, b) for a, b in pairs) / len(pairs), 4) if pairs else 0.0

    accuracy = structural_accuracy(winner["nodes"], session.canvas_w, session.canvas_h,
                                   [n["node_id"] for n in session.base_nodes])

    timings = summary["timings_ms"]
    return {
        "poster":        os.path.basename(poster_path),
        "condition":     condition,
        "use_gnn":       use_gnn,
        "structure_error": structure_error(session, winner["nodes"], structure),
        # the same over all six candidates: the Stage 2 effect without the
        # ranking's pick (certificate candidates often tie on C_total)
        "structure_error_all": _mean([structure_error(session, c["nodes"], structure)
                                      for c in session.candidates]),
        "mapped_roles":  sorted(session.structure) if session.structure else [],
        "timings_ms":    dict(timings, total=summary["total_ms"]),
        "latency_total": summary["total_ms"],
        "winner":        winner["candidate_id"],
        "winner_label":  winner["label"],
        "C_total":       winner["c_total"],
        "P_collision":   metrics.get("P_collision", 0.0),
        "P_align":       metrics.get("P_align", 0.0),
        "P_space":       metrics.get("P_space", 0.0),
        "P_legibility":  metrics.get("P_legibility", 0.0),
        "f1":            accuracy["f1"],
        "fp":            accuracy["fp"],
        "fn":            accuracy["fn"],
        "gnn_solver_overlap": overlap,
        "num_nodes":     sum(1 for n in winner["nodes"] if n.get("structural_class") != "decor"),
        "motifs_placed": sum(1 for n in winner["nodes"] if n.get("structural_class") == "decor"),
        "title_artwork": bool(session.style_kit.get("wordmark")),
        "candidates":    [[c["candidate_id"], c["c_total"]] for c in session.candidates],
        "rendered_svg":  os.path.relpath(summary["rendered_path"], _ROOT),
    }


def _mean(values):
    values = [v for v in values if v is not None]
    return round(statistics.mean(values), 4) if values else None


def _stdev(values):
    values = [v for v in values if v is not None]
    return round(statistics.stdev(values), 4) if len(values) > 1 else 0.0


def _print_summary_table(domain_label: str, trials: dict):
    gnn, mapping, base = trials["gnn"], trials["mapping"], trials["baseline"]
    print(f"\n  Domain: {domain_label}")
    print(f"  Master layouts: {len(gnn)}  (each run GNN-guided, mapping only, and baseline)")
    print()
    print(f"  {'Metric':<26} {'GNN':>9} {'σ':>7} {'Mapping':>9} {'σ':>7} {'Base':>9} {'σ':>7}")
    print(f"  {'-'*26} {'-'*9} {'-'*7} {'-'*9} {'-'*7} {'-'*9} {'-'*7}")
    for label, key in [("C_total (↓ better)", "C_total"), ("F1, p.56 (↑ better)", "f1"),
                       ("P_collision", "P_collision"),
                       ("P_align", "P_align"), ("P_space", "P_space"), ("P_legibility", "P_legibility"),
                       ("Structure error, winner (↓)", "structure_error"),
                       ("Structure error, all 6 (↓)", "structure_error_all"),
                       ("Latency total (ms)", "latency_total")]:
        cells = []
        for ts in (gnn, mapping, base):
            vs = [t[key] for t in ts]
            m = _mean(vs)
            cells.append(f"{m:>9.4f} {_stdev(vs):>7.4f}" if m is not None else f"{'—':>9} {'':>7}")
        print(f"  {label:<26} " + " ".join(cells))

    def tally(a, b):
        wins = sum(1 for x, y in zip(a, b) if x["C_total"] < y["C_total"])
        ties = sum(1 for x, y in zip(a, b) if x["C_total"] == y["C_total"])
        return wins, ties, len(a) - wins - ties

    for name, other in (("baseline", base), ("mapping only", mapping)):
        w, t, l = tally(gnn, other)
        print(f"  Per master, GNN vs {name}: lower C_total on {w}, equal on {t}, higher on {l}")


def run_experiment(posters_dir: str = p4.POSTERS_DIR, domains: list = None,
                   population: int = 6, limit: int = None) -> dict:
    domains = domains or list(DOMAIN_CONFIGS)
    manifest = {r["poster_file"]: r for r in p4.read_manifest(posters_dir)}
    names = sorted(manifest)
    posters = p4.poster_files(posters_dir)[:limit] if limit else p4.poster_files(posters_dir)
    run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n{SEPARATOR}\n  ThemeSync — Experiment Runner (Phase 3)\n{SEPARATOR}")
    print(f"  Run ID    : {run_id}")
    print(f"  Masters   : {len(posters)} from {os.path.relpath(posters_dir, _ROOT)}")
    print(f"  Domains   : {domains}")
    print(f"  GNN       : {os.path.basename(pipeline.DEFAULT_WEIGHTS)}")
    print(f"  YOLO      : {os.path.basename(pipeline.DEFAULT_YOLO_WEIGHTS)}")
    print(f"  Conditions: {', '.join(CONDITIONS)}")
    print(f"  Population: {population}")

    all_results = {
        "run_id": run_id,
        "timestamp": datetime.datetime.now().isoformat(),
        "config": {"masters": len(posters), "posters_dir": os.path.relpath(posters_dir, _ROOT),
                   "domains": domains, "population": population,
                   "gnn_weights": os.path.basename(pipeline.DEFAULT_WEIGHTS),
                   "yolo_weights": os.path.basename(pipeline.DEFAULT_YOLO_WEIGHTS),
                   "conditions": list(CONDITIONS),
                   "trial_unit": "one master layout (the pipeline is deterministic per input)"},
        "results": {},
    }
    for domain_key in domains:
        cfg = DOMAIN_CONFIGS[domain_key]
        print(f"\n{SEPARATOR}\n  Running: {cfg['label']}\n{SEPARATOR}")
        trials = {c: [] for c in CONDITIONS}
        for k, poster in enumerate(posters, start=1):
            path = os.path.join(posters_dir, poster)
            content = _content(poster, cfg, manifest, names)
            runs = {c: run_single(path, domain_key, c, content, population) for c in CONDITIONS}
            for c, r in runs.items():
                trials[c].append(r)

            def cell(r):
                err = r["structure_error"]
                return f"C={r['C_total']:.4f} ({r['winner'][-1]}) s={err if err is not None else '—'}"
            print(f"  {k:>2}/{len(posters)} {poster[:20]:<20} | GNN {cell(runs['gnn'])} | "
                  f"Map {cell(runs['mapping'])} | Base {cell(runs['baseline'])} "
                  f"| {runs['gnn']['latency_total']:.0f} ms", flush=True)
        _print_summary_table(cfg["label"], trials)
        all_results["results"][domain_key] = {"domain_label": cfg["label"],
                                              "gnn_trials": trials["gnn"],
                                              "mapping_trials": trials["mapping"],
                                              "base_trials": trials["baseline"]}

    log_path = os.path.join(_ROOT, "results", "experiment_log.json")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w") as f:
        json.dump(all_results, f, indent=2)
    runs = len(posters) * len(domains) * len(CONDITIONS)
    print(f"\n{SEPARATOR}\n  Experiment complete: {len(posters)} master(s) × {len(domains)} format(s) × "
          f"{len(CONDITIONS)} conditions = {runs} pipeline runs.\n  Log saved → {log_path}\n{SEPARATOR}\n")
    return all_results


def main():
    parser = argparse.ArgumentParser(description="ThemeSync Experiment Runner (Phase 3)")
    parser.add_argument("--posters_dir", default=p4.POSTERS_DIR)
    parser.add_argument("--limit", type=int, default=None, help="use only the first N master layouts")
    parser.add_argument("--domains", default="both", choices=["both", "certificate", "id"])
    parser.add_argument("--population", type=int, default=6)
    args = parser.parse_args()
    domains = list(DOMAIN_CONFIGS) if args.domains == "both" else [args.domains]
    run_experiment(args.posters_dir, domains, args.population, args.limit)


if __name__ == "__main__":
    main()
