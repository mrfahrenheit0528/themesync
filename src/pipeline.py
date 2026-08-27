"""
ThemeSync Pipeline Orchestrator
================================
Entry-point for the full end-to-end ThemeSync layout generation pipeline.

Execution order:
  1. Dynamic Node Instantiation  (payload → node tensors)
  2. GNN Inference               (spatial position prediction)
  3. CSP Resolution              (Cassowary hard + soft constraints)
  4. Metaheuristic Ranking       (AAPA candidate exploration)
  5. Aesthetic Rendering         (SVG output of top candidate)
  6. State Serialization         (FSM final state snapshot)

Usage:
  python src/pipeline.py --payload data/raw/academic_payload.json
  python src/pipeline.py --payload data/raw/id_payload.json --canvas_w 638 --canvas_h 1014
  python src/pipeline.py --payload data/raw/academic_payload.json --population 5 --no_gnn
"""

import argparse
import json
import os
import sys
import time
import torch

# ---------------------------------------------------------------------------
# Path bootstrap — resolve all sibling packages without sys.path hacks later
# ---------------------------------------------------------------------------
_SRC = os.path.dirname(os.path.abspath(__file__))
for _sub in ("models", "solvers", "renderers", "data_preprocessing"):
    _p = os.path.join(_SRC, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dynamic_instantiation import NodeInstantiator
from gnn_model import ThemeSyncGNN
from graph_builder import LayoutGraphBuilder
from cassowary_engine import ConstraintSolverEngine
from candidate_generator import MetaheuristicStateExplorer
from aesthetic_renderer import AestheticSVGRenderer
from state_manager import StateManager

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_WEIGHTS = os.path.join(os.path.dirname(_SRC), "themesync_gnn_v1.pth")
SEPARATOR = "=" * 66


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_header(title: str):
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def _print_stage(stage: str, elapsed: float):
    print(f"  ✔  {stage:<42} [{elapsed*1000:.1f} ms]")


def _load_payload_meta(payload_path: str) -> dict:
    """Read domain_context and target_aspect_ratio from the payload file."""
    with open(payload_path, "r") as f:
        return json.load(f)


def _derive_canvas(payload_meta: dict, canvas_w: int, canvas_h: int):
    """
    If canvas dimensions were explicitly passed, use them.
    Otherwise infer sensible defaults from the domain_context in the payload.
    """
    if canvas_w and canvas_h:
        return int(canvas_w), int(canvas_h)

    domain = payload_meta.get("domain_context", "academic_certificate")
    if domain == "identification_card":
        return 638, 1014   # CR80 portrait
    else:
        return 1200, 900   # A4 landscape (4:3 proxy)


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def stage_instantiate(payload_path: str, canvas_w: int, canvas_h: int) -> list:
    t0 = time.perf_counter()
    instantiator = NodeInstantiator(canvas_width=canvas_w, canvas_height=canvas_h)
    nodes = instantiator.instantiate_payload(payload_path)
    _print_stage("1. Dynamic Node Instantiation", time.perf_counter() - t0)
    print(f"     → {len(nodes)} node(s) instantiated for canvas {canvas_w}×{canvas_h}")
    return nodes, time.perf_counter() - t0


def stage_gnn_inference(nodes: list, canvas_w: int, canvas_h: int,
                         weights_path: str, device: torch.device):
    t0 = time.perf_counter()
    model = ThemeSyncGNN(num_layers=3, node_dim=8, edge_dim=4, hidden_dim=64).to(device)

    if os.path.exists(weights_path):
        model.load_state_dict(
            torch.load(weights_path, map_location=device, weights_only=True)
        )
        weights_status = f"loaded from {os.path.basename(weights_path)}"
    else:
        weights_status = "WARNING: weights not found — using random init"

    model.eval()
    builder = LayoutGraphBuilder()

    # Build a synthetic colour/saliency context for GNN graph construction
    gnn_payload = {
        "extracted_nodes": nodes,
        "extracted_color_centroids": [
            [0.0, 51.0, 102.0],
            [255.0, 204.0, 0.0],
            [255.0, 255.0, 255.0],
        ],
        "extracted_saliency_weight": 0.75,
    }

    graph_data = builder.build_graph(gnn_payload)
    predicted = False

    if graph_data is not None:
        graph_data = graph_data.to(device)
        with torch.no_grad():
            predicted_coords = model(graph_data)

        for idx, node in enumerate(nodes):
            pred_x = predicted_coords[idx][0].item()
            pred_y = predicted_coords[idx][1].item()
            # Clamp predictions to canvas boundaries
            pred_x = max(0.0, min(pred_x, canvas_w - node["bbox"][2]))
            pred_y = max(0.0, min(pred_y, canvas_h - node["bbox"][3]))
            node["bbox"][0] = round(pred_x, 2)
            node["bbox"][1] = round(pred_y, 2)
        predicted = True

    elapsed = time.perf_counter() - t0
    _print_stage("2. GNN Spatial Inference", elapsed)
    print(f"     → Weights: {weights_status}")
    print(f"     → Predictions applied: {predicted}")
    return nodes, elapsed


def stage_csp_resolve(nodes: list, canvas_w: int, canvas_h: int):
    t0 = time.perf_counter()
    engine = ConstraintSolverEngine(canvas_width=canvas_w, canvas_height=canvas_h)
    resolved = engine.execute_relational_logic(nodes)
    elapsed = time.perf_counter() - t0
    _print_stage("3. Cassowary CSP Resolution", elapsed)
    hard = sum(1 for n in resolved if n.get("constraint_type") == "Hard")
    soft = len(resolved) - hard
    print(f"     → Hard constraints: {hard} | Soft constraints: {soft}")
    return resolved, elapsed


def stage_rank_candidates(resolved_nodes: list, population: int):
    t0 = time.perf_counter()
    explorer = MetaheuristicStateExplorer()
    ranked = explorer.generate_and_rank_candidates(resolved_nodes, population_size=population)
    elapsed = time.perf_counter() - t0
    _print_stage("4. Metaheuristic Candidate Ranking", elapsed)
    print(f"     → {len(ranked)} candidate(s) evaluated")
    print()
    print(f"  {'Rank':<6} {'Candidate':<35} {'C_total':>8}")
    print(f"  {'-'*6} {'-'*35} {'-'*8}")
    for i, c in enumerate(ranked):
        marker = " ◀ WINNER" if i == 0 else ""
        print(f"  [{i+1}]   {c['candidate_id']:<35} {c['c_total']:>8.4f}{marker}")
    return ranked, elapsed


def stage_render(winner_filepath: str, canvas_w: int, canvas_h: int,
                 payload_meta: dict, output_dir: str):
    t0 = time.perf_counter()
    # Derive a clean filename stem from the payload domain
    domain = payload_meta.get("domain_context", "layout")
    stem = domain.replace("_", "-")

    renderer = AestheticSVGRenderer(
        canvas_width=canvas_w,
        canvas_height=canvas_h,
        original_filename=f"ThemeSync_{stem}",
    )
    renderer.render_layout(winner_filepath, output_dir=output_dir)
    elapsed = time.perf_counter() - t0
    _print_stage("5. Aesthetic SVG Rendering", elapsed)
    return elapsed


def stage_serialize_state(resolved_nodes: list):
    t0 = time.perf_counter()
    manager = StateManager()
    filepath = manager.serialize_state(resolved_nodes, version="v1")
    elapsed = time.perf_counter() - t0
    _print_stage("6. FSM State Serialization", elapsed)
    print(f"     → Saved: {filepath}")
    return elapsed


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_pipeline(
    payload_path: str,
    canvas_w: int = None,
    canvas_h: int = None,
    population: int = 5,
    use_gnn: bool = True,
    weights_path: str = DEFAULT_WEIGHTS,
    output_dir: str = "data/rendered/",
):
    _print_header("ThemeSync — Design Orchestration Pipeline")

    if not os.path.exists(payload_path):
        print(f"ERROR: Payload not found at '{payload_path}'")
        sys.exit(1)

    payload_meta = _load_payload_meta(payload_path)
    canvas_w, canvas_h = _derive_canvas(payload_meta, canvas_w, canvas_h)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print(f"\n  Payload  : {payload_path}")
    print(f"  Domain   : {payload_meta.get('domain_context', 'N/A')}")
    print(f"  Canvas   : {canvas_w} × {canvas_h} px")
    print(f"  Device   : {device}")
    print(f"  GNN      : {'enabled' if use_gnn else 'disabled (baseline mode)'}")
    print(f"  Population: {population}")

    timings = {}

    # Stage 1
    nodes, timings["instantiation"] = stage_instantiate(payload_path, canvas_w, canvas_h)

    # Stage 2
    if use_gnn:
        nodes, timings["gnn_inference"] = stage_gnn_inference(
            nodes, canvas_w, canvas_h, weights_path, device
        )
    else:
        print("\n  ⊘  GNN Inference skipped (baseline mode)")
        timings["gnn_inference"] = 0.0

    # Stage 3
    resolved_nodes, timings["csp_resolution"] = stage_csp_resolve(nodes, canvas_w, canvas_h)

    # Stage 4
    ranked_candidates, timings["ranking"] = stage_rank_candidates(resolved_nodes, population)

    # Stage 5 — render the winner
    winner = ranked_candidates[0]
    timings["rendering"] = stage_render(
        winner["filepath"], canvas_w, canvas_h, payload_meta, output_dir
    )

    # Stage 6 — serialize final state
    timings["serialization"] = stage_serialize_state(resolved_nodes)

    # Summary
    total = sum(timings.values())
    _print_header("Pipeline Complete — Timing Summary")
    print(f"\n  {'Stage':<40} {'Time (ms)':>10}")
    print(f"  {'-'*40} {'-'*10}")
    labels = {
        "instantiation": "1. Dynamic Node Instantiation",
        "gnn_inference": "2. GNN Spatial Inference",
        "csp_resolution": "3. Cassowary CSP Resolution",
        "ranking": "4. Metaheuristic Ranking",
        "rendering": "5. Aesthetic Rendering",
        "serialization": "6. FSM State Serialization",
    }
    for key, label in labels.items():
        print(f"  {label:<40} {timings[key]*1000:>10.1f}")
    print(f"  {'─'*40} {'─'*10}")
    print(f"  {'TOTAL END-TO-END':<40} {total*1000:>10.1f}")
    print()

    # Final output paths
    domain = payload_meta.get("domain_context", "layout")
    stem = domain.replace("_", "-")
    rendered_path = os.path.join(output_dir, f"ThemeSync_{stem}_populated.svg")
    print(f"  Winner   : {winner['candidate_id']} (C_total = {winner['c_total']:.4f})")
    print(f"  Output   : {rendered_path}")
    print()

    return {
        "timings_ms": {k: round(v * 1000, 2) for k, v in timings.items()},
        "total_ms": round(total * 1000, 2),
        "winner": winner,
        "rendered_path": rendered_path,
    }


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="ThemeSync — Graph-Based Design Orchestration Pipeline"
    )
    parser.add_argument(
        "--payload",
        type=str,
        default="data/raw/academic_payload.json",
        help="Path to the dynamic content payload JSON",
    )
    parser.add_argument(
        "--canvas_w",
        type=int,
        default=None,
        help="Canvas width in pixels (auto-inferred from domain if omitted)",
    )
    parser.add_argument(
        "--canvas_h",
        type=int,
        default=None,
        help="Canvas height in pixels (auto-inferred from domain if omitted)",
    )
    parser.add_argument(
        "--population",
        type=int,
        default=5,
        help="Number of metaheuristic candidates to generate (default: 5)",
    )
    parser.add_argument(
        "--no_gnn",
        action="store_true",
        help="Skip GNN inference — useful for baseline comparison",
    )
    parser.add_argument(
        "--weights",
        type=str,
        default=DEFAULT_WEIGHTS,
        help="Path to trained GNN weights .pth file",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="data/rendered/",
        help="Directory to write SVG output (default: data/rendered/)",
    )

    args = parser.parse_args()

    run_pipeline(
        payload_path=args.payload,
        canvas_w=args.canvas_w,
        canvas_h=args.canvas_h,
        population=args.population,
        use_gnn=not args.no_gnn,
        weights_path=args.weights,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
