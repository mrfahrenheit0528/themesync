"""
ThemeSync — Experiment Runner
==============================
Runs a configurable N-trial battery across one or both payload domains,
collecting all evaluation metrics per trial and writing a consolidated
results log to results/experiment_log.json.

Produces a summary table suitable for inclusion in the thesis results chapter.

Usage:
  python src/evaluation/experiment_runner.py
  python src/evaluation/experiment_runner.py --trials 10
  python src/evaluation/experiment_runner.py --trials 10 --domains both
  python src/evaluation/experiment_runner.py --trials 5 --domains id
"""

import argparse
import json
import os
import sys
import time
import datetime
import statistics

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC  = os.path.dirname(_EVAL_DIR)
_ROOT = os.path.dirname(_SRC)

for _sub in ("models", "solvers", "renderers"):
    _p = os.path.join(_SRC, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import torch
from dynamic_instantiation import NodeInstantiator
from gnn_model import ThemeSyncGNN
from graph_builder import LayoutGraphBuilder
from cassowary_engine import ConstraintSolverEngine
from candidate_generator import MetaheuristicStateExplorer
from optimization_engine import HeuristicEvaluator

DEFAULT_WEIGHTS = os.path.join(_ROOT, "themesync_gnn_v1.pth")

# ---------------------------------------------------------------------------
# Metric helpers (shared with evaluate.py)
# ---------------------------------------------------------------------------

def _calculate_iou(box1: list, box2: list) -> float:
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    ix1 = max(x1, x2);  iy1 = max(y1, y2)
    ix2 = min(x1+w1, x2+w2); iy2 = min(y1+h1, y2+h2)
    inter = max(0.0, ix2-ix1) * max(0.0, iy2-iy1)
    union = w1*h1 + w2*h2 - inter
    return inter / union if union > 0 else 0.0


def _run_single_trial(
    payload_path: str,
    canvas_w: int,
    canvas_h: int,
    use_gnn: bool,
    device: torch.device,
    population: int = 5,
) -> dict:
    """Execute one full pipeline pass and return collected metrics."""
    t_start = time.perf_counter()

    # Stage 1: Instantiation
    t0 = time.perf_counter()
    inst = NodeInstantiator(canvas_width=canvas_w, canvas_height=canvas_h)
    nodes = inst.instantiate_payload(payload_path)
    t_instantiation = time.perf_counter() - t0

    # Stage 2: GNN Inference
    t0 = time.perf_counter()
    pre_csp_nodes = [dict(n, bbox=list(n["bbox"])) for n in nodes]
    if use_gnn:
        model = ThemeSyncGNN(num_layers=3, node_dim=8, edge_dim=4, hidden_dim=64).to(device)
        if os.path.exists(DEFAULT_WEIGHTS):
            model.load_state_dict(
                torch.load(DEFAULT_WEIGHTS, map_location=device, weights_only=True)
            )
        model.eval()
        builder = LayoutGraphBuilder()
        gnn_payload = {
            "extracted_nodes": nodes,
            "extracted_color_centroids": [
                [0.0, 51.0, 102.0], [255.0, 204.0, 0.0], [255.0, 255.0, 255.0]
            ],
            "extracted_saliency_weight": 0.75,
            "canvas_w": canvas_w,
            "canvas_h": canvas_h,
        }
        graph_data = builder.build_graph(gnn_payload)
        if graph_data is not None:
            graph_data = graph_data.to(device)
            with torch.no_grad():
                predicted = model(graph_data)
            builder.apply_predictions(nodes, predicted, canvas_w, canvas_h)
            pre_csp_nodes = [dict(n, bbox=list(n["bbox"])) for n in nodes]
    t_gnn = time.perf_counter() - t0

    # Stage 3: CSP Resolution
    t0 = time.perf_counter()
    engine = ConstraintSolverEngine(canvas_width=canvas_w, canvas_height=canvas_h)
    resolved = engine.execute_relational_logic(nodes)
    t_csp = time.perf_counter() - t0

    # Stage 4: Ranking
    t0 = time.perf_counter()
    explorer = MetaheuristicStateExplorer()
    ranked = explorer.generate_and_rank_candidates(resolved, population_size=population)
    t_rank = time.perf_counter() - t0

    t_total = time.perf_counter() - t_start

    # IoU: GNN predictions vs CSP resolved positions
    post_csp_map = {n["node_id"]: n for n in resolved}
    iou_scores = []
    for pre in pre_csp_nodes:
        post = post_csp_map.get(pre["node_id"])
        if post:
            iou_scores.append(_calculate_iou(pre["bbox"], post["bbox"]))
    mean_iou = round(sum(iou_scores) / len(iou_scores), 4) if iou_scores else 0.0

    winner = ranked[0]
    metrics = winner["metrics"]

    return {
        "use_gnn":    use_gnn,
        "timings_ms": {
            "instantiation": round(t_instantiation * 1000, 2),
            "gnn_inference":  round(t_gnn * 1000, 2),
            "csp_resolution": round(t_csp * 1000, 2),
            "ranking":        round(t_rank * 1000, 2),
            "total":          round(t_total * 1000, 2),
        },
        "mean_iou":   mean_iou,
        "C_total":    winner["c_total"],
        "P_align":    metrics.get("P_align", 0.0),
        "P_space":    metrics.get("P_space", 0.0),
        "P_legibility": metrics.get("P_legibility", 0.0),
        "num_nodes":  len(resolved),
    }


# ---------------------------------------------------------------------------
# Domain configurations
# ---------------------------------------------------------------------------

DOMAIN_CONFIGS = {
    "certificate": {
        "label":      "Academic Certificate (4:3)",
        "payload":    os.path.join(_ROOT, "data", "raw", "academic_payload.json"),
        "canvas_w":   1200,
        "canvas_h":   900,
    },
    "id": {
        "label":      "Event ID (A6, 1:1.414)",
        "payload":    os.path.join(_ROOT, "data", "raw", "id_payload.json"),
        "canvas_w":   744,
        "canvas_h":   1052,
    },
}

SEPARATOR = "=" * 72


# ---------------------------------------------------------------------------
# Aggregate helpers
# ---------------------------------------------------------------------------

def _mean(values):
    return round(statistics.mean(values), 4) if values else 0.0

def _stdev(values):
    return round(statistics.stdev(values), 4) if len(values) > 1 else 0.0


def _print_summary_table(domain_label: str, gnn_trials: list, base_trials: list):
    print(f"\n  Domain: {domain_label}")
    print(f"  Trials: {len(gnn_trials)} GNN-guided  |  {len(base_trials)} Baseline")
    print()
    metrics_def = [
        ("Mean IoU",            "mean_iou",     True),
        ("C_total  (↓ better)", "C_total",      False),
        ("P_align",             "P_align",       False),
        ("P_space",             "P_space",       False),
        ("P_legibility",        "P_legibility",  False),
        ("Latency total (ms)",  "latency_total", False),
    ]

    # Pre-compute latency as a flat field
    for t in gnn_trials:
        t["latency_total"] = t["timings_ms"]["total"]
    for t in base_trials:
        t["latency_total"] = t["timings_ms"]["total"]

    print(f"  {'Metric':<28} {'GNN Mean':>10} {'GNN σ':>8} {'Base Mean':>10} {'Base σ':>8} {'Δ Mean':>9} {'Better?':>8}")
    print(f"  {'-'*28} {'-'*10} {'-'*8} {'-'*10} {'-'*8} {'-'*9} {'-'*8}")

    for label, key, higher_better in metrics_def:
        gv = [t[key] for t in gnn_trials]
        bv = [t[key] for t in base_trials]
        gm, gs = _mean(gv), _stdev(gv)
        bm, bs = _mean(bv), _stdev(bv)
        delta = gm - bm
        if higher_better:
            better = "GNN ✓" if delta > 0 else ("=" if delta == 0 else "Base ✓")
        else:
            better = "GNN ✓" if delta < 0 else ("=" if delta == 0 else "Base ✓")
        print(f"  {label:<28} {gm:>10.4f} {gs:>8.4f} {bm:>10.4f} {bs:>8.4f} {delta:>+9.4f} {better:>8}")

    # GNN latency breakdown
    print()
    print("  GNN Latency Breakdown (mean ms):")
    stages = ["instantiation", "gnn_inference", "csp_resolution", "ranking"]
    for s in stages:
        vals = [t["timings_ms"][s] for t in gnn_trials]
        print(f"    {s:<20} {_mean(vals):>8.2f} ms")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_experiment(trials: int = 5, domains: list = None, population: int = 5):
    if domains is None:
        domains = ["certificate", "id"]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n{SEPARATOR}")
    print("  ThemeSync — Experiment Runner")
    print(f"{SEPARATOR}")
    print(f"  Run ID   : {run_id}")
    print(f"  Trials   : {trials}")
    print(f"  Domains  : {domains}")
    print(f"  Device   : {device}")
    print(f"  Population: {population}")

    all_results = {
        "run_id":    run_id,
        "timestamp": datetime.datetime.now().isoformat(),
        "config":    {"trials": trials, "domains": domains, "population": population},
        "results":   {},
    }

    for domain_key in domains:
        cfg = DOMAIN_CONFIGS[domain_key]
        print(f"\n{SEPARATOR}")
        print(f"  Running: {cfg['label']}")
        print(SEPARATOR)

        gnn_trials  = []
        base_trials = []

        for trial_num in range(1, trials + 1):
            print(f"  Trial {trial_num:>2}/{trials} ", end="", flush=True)

            r_gnn  = _run_single_trial(cfg["payload"], cfg["canvas_w"], cfg["canvas_h"],
                                        use_gnn=True,  device=device, population=population)
            r_base = _run_single_trial(cfg["payload"], cfg["canvas_w"], cfg["canvas_h"],
                                        use_gnn=False, device=device, population=population)
            gnn_trials.append(r_gnn)
            base_trials.append(r_base)

            print(f"| GNN C={r_gnn['C_total']:.4f} t={r_gnn['timings_ms']['total']:.0f}ms  "
                  f"| Base C={r_base['C_total']:.4f} t={r_base['timings_ms']['total']:.0f}ms")

        _print_summary_table(cfg["label"], gnn_trials, base_trials)

        all_results["results"][domain_key] = {
            "domain_label": cfg["label"],
            "gnn_trials":   gnn_trials,
            "base_trials":  base_trials,
        }

    # Save consolidated log
    results_dir = os.path.join(_ROOT, "results")
    os.makedirs(results_dir, exist_ok=True)
    log_path = os.path.join(results_dir, "experiment_log.json")
    with open(log_path, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\n{SEPARATOR}")
    print(f"  Experiment complete. {trials} trial(s) × {len(domains)} domain(s) = "
          f"{trials * len(domains) * 2} total pipeline runs.")
    print(f"  Log saved → {log_path}")
    print(f"{SEPARATOR}\n")

    return all_results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ThemeSync Experiment Runner")
    parser.add_argument("--trials",     type=int, default=5,
                        help="Number of independent trials per domain (default: 5)")
    parser.add_argument("--domains",    type=str, default="both",
                        choices=["both", "certificate", "id"],
                        help="Which domain(s) to run (default: both)")
    parser.add_argument("--population", type=int, default=5,
                        help="Metaheuristic candidate population size (default: 5)")
    args = parser.parse_args()

    domains = list(DOMAIN_CONFIGS.keys()) if args.domains == "both" else [args.domains]

    run_experiment(trials=args.trials, domains=domains, population=args.population)


if __name__ == "__main__":
    main()
