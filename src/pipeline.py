"""
ThemeSync Pipeline Orchestrator
================================
Entry-point for the full end-to-end ThemeSync layout generation pipeline.

Execution order:
  0. Template Ingestion          (image → LAB centroids + SIFT saliency)  [optional]
  0b. Semantic Layout Parsing    (image → detected logo/text/underlay/
                                   embellishment nodes via YOLO+OCR)      [optional]
                                  Independent of Stage 0 and of Stage 1 below —
                                  reports on the master layout's own structure,
                                  does not feed the certificate/ID being built.
                                  See notes/gnn_fixes_and_methodology_notes.md
                                  section 3.7.
  1. Dynamic Node Instantiation  (payload → node tensors)
  2. GNN Inference               (spatial position prediction)
  3. CSP Resolution              (Cassowary hard + soft constraints)
  4. Metaheuristic Ranking       (AAPA candidate exploration)
  5. Aesthetic Rendering         (SVG output of top candidate)
  6. State Serialization         (FSM final state snapshot)

Usage:
  # Full pipeline — real template image + real content data
  python src/pipeline.py \\
      --payload data/raw/academic_payload.json \\
      --template_image data/raw/my_certificate_template.png \\
      --content_data data/raw/sample_content.json

  # Template image only (content uses domain defaults)
  python src/pipeline.py \\
      --payload data/raw/academic_payload.json \\
      --template_image data/raw/my_certificate_template.png

  # Original behaviour — no template image (synthetic fallback values)
  python src/pipeline.py --payload data/raw/academic_payload.json

  # Baseline comparison (no GNN)
  python src/pipeline.py --payload data/raw/academic_payload.json --no_gnn
"""

import argparse
import json
import os
import sys
import time
import torch

# ---------------------------------------------------------------------------
# Path bootstrap — resolve all sibling packages
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
from template_ingestor import TemplateIngestor
from layout_extractor import LayoutExtractor

# ---------------------------------------------------------------------------
# Constants — synthetic fallback values (used when no template image is given)
# These match the values used during GNN training for the CSPC institution.
# ---------------------------------------------------------------------------
DEFAULT_WEIGHTS = os.path.join(os.path.dirname(_SRC), "themesync_gnn_v1.pth")
# v2 (fine-tuned on real master-layout images) preferred over v1 (CGL-only) —
# see notes/gnn_fixes_and_methodology_notes.md section 3.7.
_YOLO_V2 = os.path.join(os.path.dirname(_SRC), "themesync_yolo_v2.pt")
_YOLO_V1 = os.path.join(os.path.dirname(_SRC), "themesync_yolo_v1.pt")
DEFAULT_YOLO_WEIGHTS = _YOLO_V2 if os.path.exists(_YOLO_V2) else _YOLO_V1
SEPARATOR = "=" * 66

_FALLBACK_CENTROIDS = [
    [0.0,   51.0,  102.0],   # Primary — deep navy blue (CSPC)
    [255.0, 204.0,   0.0],   # Accent  — CSPC gold
    [255.0, 255.0, 255.0],   # Background — white
]
_FALLBACK_SALIENCY = 0.75


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_header(title: str):
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def _print_stage(stage: str, elapsed: float):
    print(f"  ✔  {stage:<42} [{elapsed*1000:.1f} ms]")


def _load_json(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def _derive_canvas(payload_meta: dict, canvas_w: int, canvas_h: int):
    """
    Canvas resolution priority:
      1. Explicit CLI args (--canvas_w / --canvas_h)
      2. Domain defaults from the payload (1200×900 cert / 638×1014 ID),
         matching each payload's own target_aspect_ratio.

    The uploaded master-layout image's own pixel dimensions are deliberately
    NOT consulted here. The master layout is a generic branded design used
    only to extract a visual theme (colour, typography, detected structure)
    — its aspect ratio has nothing to do with the certificate/ID format the
    user actually selected. Using it was a leftover from before that
    distinction was clarified (see notes/gnn_fixes_and_methodology_notes.md
    sections 3.5-3.7) and caused a 2:3 ID request to silently render as a
    1:1 square whenever a square poster was uploaded as the theme source.
    """
    if canvas_w and canvas_h:
        return int(canvas_w), int(canvas_h)

    domain = payload_meta.get("domain_context", "academic_certificate")
    return (638, 1014) if domain == "identification_card" else (1200, 900)


# ---------------------------------------------------------------------------
# Stage functions
# ---------------------------------------------------------------------------

def stage_template_ingestion(template_image_path: str) -> dict:
    """
    Stage 0 — Runtime template ingestion.

    Runs VisionExtractor on the provided master design image to extract:
      - LAB colour centroids  (drives GNN graph construction + SVG palette)
      - SIFT saliency weight  (drives GNN saliency node feature)
      - Native image dimensions (can auto-set canvas size)
    """
    t0 = time.perf_counter()
    ingestor = TemplateIngestor(n_colors=3)
    result = ingestor.ingest(template_image_path)
    elapsed = time.perf_counter() - t0
    _print_stage("0. Template Ingestion", elapsed)
    print(f"     → Palette: {' | '.join(result['palette_hex'])}")
    print(f"     → Saliency: {result['saliency_weight']:.4f}  "
          f"| Native size: {result['image_wh'][0]}×{result['image_wh'][1]} px")
    return result, elapsed


def stage_layout_parsing(template_image_path: str, weights_path: str) -> tuple:
    """
    Stage 0b — Semantic Layout Parsing (Chapter 3, p. 50).

    Runs the fine-tuned YOLOv8 detector + Tesseract OCR on the uploaded
    master-layout image, independently of Stage 0's colour/saliency
    extraction and independently of the JSON-schema-driven certificate/ID
    node instantiation (Stage 1) — this stage reports on the *master
    layout's own* structure ("Logo detected: True," per Figure 2's UI
    mockup), it does not feed those nodes into the certificate/ID being
    generated. See notes/gnn_fixes_and_methodology_notes.md sections 3.5-3.7
    for why these stay separate for now.

    Gracefully skipped (not a hard failure) if no fine-tuned weights file is
    present, so the rest of the pipeline still runs on a machine that hasn't
    gone through YOLO fine-tuning.
    """
    t0 = time.perf_counter()
    if not os.path.exists(weights_path):
        print("\n  ⊘  Stage 0b skipped — no YOLO weights found at "
              f"'{weights_path}' (run src/models/train_yolo_extractor.py "
              "and/or finetune_yolo_master_layout.py first)")
        return None, 0.0

    extractor = LayoutExtractor(weights_path=weights_path)
    nodes = extractor.extract(template_image_path)
    elapsed = time.perf_counter() - t0

    _print_stage("0b. Semantic Layout Parsing (YOLO+OCR)", elapsed)
    print(f"     → Weights: {os.path.basename(weights_path)}")
    print(f"     → {len(nodes)} node(s) detected on the master layout")
    for n in nodes:
        detail = f"conf={n['detection_confidence']:.2f}"
        if n["structural_class"] == "text_node" and n.get("ocr_text"):
            preview = n["ocr_text"].replace("\n", " ")[:40]
            detail += f"  ocr=\"{preview}\""
        print(f"       · {n['node_id']:<22} {detail}")

    return nodes, elapsed


def stage_instantiate(payload_path: str, canvas_w: int, canvas_h: int):
    t0 = time.perf_counter()
    instantiator = NodeInstantiator(canvas_width=canvas_w, canvas_height=canvas_h)
    nodes = instantiator.instantiate_payload(payload_path)
    elapsed = time.perf_counter() - t0
    _print_stage("1. Dynamic Node Instantiation", elapsed)
    print(f"     → {len(nodes)} node(s) instantiated for canvas {canvas_w}×{canvas_h}")
    return nodes, elapsed


def stage_gnn_inference(nodes: list, canvas_w: int, canvas_h: int,
                         weights_path: str, device: torch.device,
                         color_centroids: list, saliency_weight: float):
    """
    Stage 2 — GNN spatial inference.

    The colour centroids and saliency weight now come from the template
    ingestor (Stage 0) instead of hardcoded synthetic values.
    """
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

    # Build the GNN graph with real (or fallback) extracted features
    gnn_payload = {
        "extracted_nodes":           nodes,
        "extracted_color_centroids": color_centroids,   # ← real or fallback
        "extracted_saliency_weight": saliency_weight,   # ← real or fallback
        "canvas_w":                  canvas_w,
        "canvas_h":                  canvas_h,
    }

    graph_data = builder.build_graph(gnn_payload)
    predicted = False

    if graph_data is not None:
        graph_data = graph_data.to(device)
        with torch.no_grad():
            predicted_coords = model(graph_data)

        builder.apply_predictions(nodes, predicted_coords, canvas_w, canvas_h)
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
    print(f"     → Hard constraints: {hard} | Soft constraints: {len(resolved) - hard}")
    return resolved, elapsed


def stage_rank_candidates(resolved_nodes: list, population: int, canvas_w: int, canvas_h: int,
                          saliency_map: dict = None):
    t0 = time.perf_counter()
    explorer = MetaheuristicStateExplorer(
        canvas_width=canvas_w, canvas_height=canvas_h, saliency_map=saliency_map
    )
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
                 payload_meta: dict, output_dir: str,
                 color_centroids: list, content_data: dict = None,
                 font_family: str = None):
    """
    Stage 5 — Aesthetic SVG rendering.

    Now receives real colour centroids from Stage 0 and real content strings
    from --content_data — both replacing hardcoded defaults. font_family is
    the "User Injected" administrative typography constraint from Table 1
    (p. 49), e.g. set via the dashboard's Visual DNA panel.
    """
    t0 = time.perf_counter()
    domain = payload_meta.get("domain_context", "layout")
    stem = domain.replace("_", "-")

    renderer = AestheticSVGRenderer(
        canvas_width=canvas_w,
        canvas_height=canvas_h,
        original_filename=f"ThemeSync_{stem}",
        color_centroids=color_centroids,     # ← drives palette from real image
        mock_data=content_data,              # ← real user content, or None → domain defaults
        domain_context=domain,
        font_family=font_family,
    )
    renderer.render_layout(winner_filepath, output_dir=output_dir, with_border=True)
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
    template_image: str = None,
    content_data_path: str = None,
    canvas_w: int = None,
    canvas_h: int = None,
    population: int = 5,
    use_gnn: bool = True,
    weights_path: str = DEFAULT_WEIGHTS,
    yolo_weights_path: str = DEFAULT_YOLO_WEIGHTS,
    output_dir: str = "data/rendered/",
    font_family: str = None,
):
    _print_header("ThemeSync — Design Orchestration Pipeline")

    if not os.path.exists(payload_path):
        print(f"ERROR: Payload not found at '{payload_path}'")
        sys.exit(1)

    payload_meta = _load_json(payload_path)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Load optional real content data
    content_data = _load_json(content_data_path) if content_data_path else None

    timings = {}

    # ------------------------------------------------------------------
    # Stage 0 — Template Ingestion (optional)
    # ------------------------------------------------------------------
    saliency_map = None
    if template_image:
        ingestion_result, timings["template_ingestion"] = stage_template_ingestion(template_image)
        color_centroids = ingestion_result["color_centroids"]
        saliency_weight = ingestion_result["saliency_weight"]
        saliency_map    = ingestion_result["saliency_map"]
        ingestion_mode  = f"real image → {ingestion_result['palette_hex']}"

        # Stage 0b — Semantic Layout Parsing (YOLO+OCR on the same image).
        # Independent of the colour/saliency extraction above and of the
        # schema-driven node instantiation below — see stage_layout_parsing's
        # docstring for why these three stay separate for now.
        detected_layout_nodes, timings["layout_parsing"] = stage_layout_parsing(
            template_image, yolo_weights_path
        )
    else:
        color_centroids = _FALLBACK_CENTROIDS
        saliency_weight = _FALLBACK_SALIENCY
        timings["template_ingestion"] = 0.0
        timings["layout_parsing"] = 0.0
        detected_layout_nodes = None
        ingestion_mode  = "synthetic fallback (no --template_image provided)"
        print(f"\n  ⊘  Stage 0 skipped — {ingestion_mode}")

    # Resolve canvas dimensions (CLI > domain default — see _derive_canvas)
    canvas_w, canvas_h = _derive_canvas(payload_meta, canvas_w, canvas_h)

    print(f"\n  Payload        : {payload_path}")
    print(f"  Domain         : {payload_meta.get('domain_context', 'N/A')}")
    print(f"  Canvas         : {canvas_w} × {canvas_h} px")
    print(f"  Device         : {device}")
    print(f"  Template Image : {template_image or '(none — using synthetic fallback)'}")
    print(f"  Content Data   : {content_data_path or '(none — using domain defaults)'}")
    print(f"  GNN            : {'enabled' if use_gnn else 'disabled (baseline mode)'}")
    print(f"  Population     : {population}")
    print(f"  Palette Source : {ingestion_mode}")

    # ------------------------------------------------------------------
    # Stage 1 — Instantiation
    # ------------------------------------------------------------------
    nodes, timings["instantiation"] = stage_instantiate(payload_path, canvas_w, canvas_h)

    # ------------------------------------------------------------------
    # Stage 2 — GNN Inference
    # ------------------------------------------------------------------
    if use_gnn:
        nodes, timings["gnn_inference"] = stage_gnn_inference(
            nodes, canvas_w, canvas_h, weights_path, device,
            color_centroids, saliency_weight
        )
    else:
        print("\n  ⊘  GNN Inference skipped (baseline mode)")
        timings["gnn_inference"] = 0.0

    # ------------------------------------------------------------------
    # Stage 3 — CSP Resolution
    # ------------------------------------------------------------------
    resolved_nodes, timings["csp_resolution"] = stage_csp_resolve(nodes, canvas_w, canvas_h)

    # ------------------------------------------------------------------
    # Stage 4 — Metaheuristic Ranking
    # ------------------------------------------------------------------
    ranked_candidates, timings["ranking"] = stage_rank_candidates(
        resolved_nodes, population, canvas_w, canvas_h, saliency_map=saliency_map
    )

    # ------------------------------------------------------------------
    # Stage 5 — Render winner
    # ------------------------------------------------------------------
    winner = ranked_candidates[0]
    timings["rendering"] = stage_render(
        winner["filepath"], canvas_w, canvas_h, payload_meta, output_dir,
        color_centroids=color_centroids,
        content_data=content_data,
        font_family=font_family,
    )

    # ------------------------------------------------------------------
    # Stage 6 — Serialize FSM state
    # ------------------------------------------------------------------
    timings["serialization"] = stage_serialize_state(resolved_nodes)

    # Persist Stage 0b's detections too, if any — otherwise they only ever
    # existed as console output.
    detected_layout_path = None
    if detected_layout_nodes is not None:
        os.makedirs(output_dir, exist_ok=True)
        domain_stem = payload_meta.get("domain_context", "layout").replace("_", "-")
        detected_layout_path = os.path.join(
            output_dir, f"ThemeSync_{domain_stem}_detected_master_layout.json"
        )
        with open(detected_layout_path, "w") as f:
            json.dump(detected_layout_nodes, f, indent=2)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    total = sum(timings.values())
    _print_header("Pipeline Complete — Timing Summary")
    print(f"\n  {'Stage':<42} {'Time (ms)':>10}")
    print(f"  {'-'*42} {'-'*10}")
    labels = {
        "template_ingestion": "0. Template Ingestion",
        "layout_parsing":     "0b. Semantic Layout Parsing (YOLO+OCR)",
        "instantiation":      "1. Dynamic Node Instantiation",
        "gnn_inference":      "2. GNN Spatial Inference",
        "csp_resolution":     "3. Cassowary CSP Resolution",
        "ranking":            "4. Metaheuristic Ranking",
        "rendering":          "5. Aesthetic SVG Rendering",
        "serialization":      "6. FSM State Serialization",
    }
    for key, label in labels.items():
        t = timings.get(key, 0.0)
        skipped = "  (skipped)" if t == 0.0 else ""
        print(f"  {label:<42} {t*1000:>10.1f}{skipped}")
    print(f"  {'─'*42} {'─'*10}")
    print(f"  {'TOTAL END-TO-END':<42} {total*1000:>10.1f}")
    print()

    domain = payload_meta.get("domain_context", "layout")
    stem   = domain.replace("_", "-")
    rendered_path = os.path.join(output_dir, f"ThemeSync_{stem}_populated.svg")
    print(f"  Winner   : {winner['candidate_id']} (C_total = {winner['c_total']:.4f})")
    print(f"  Output   : {rendered_path}")
    if detected_layout_path:
        print(f"  Detected master-layout nodes : {detected_layout_path}")
    print()

    return {
        "timings_ms":     {k: round(v * 1000, 2) for k, v in timings.items()},
        "total_ms":       round(total * 1000, 2),
        "winner":         winner,
        "rendered_path":  rendered_path,
        "color_centroids": color_centroids,
        "saliency_weight": saliency_weight,
        "detected_master_layout_nodes": detected_layout_nodes,
        "detected_master_layout_path":  detected_layout_path,
    }


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="ThemeSync — Graph-Based Design Orchestration Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Full pipeline with real template:
    python src/pipeline.py \\
        --payload data/raw/academic_payload.json \\
        --template_image data/raw/my_template.png \\
        --content_data data/raw/sample_content.json

  Payload only (synthetic fallback):
    python src/pipeline.py --payload data/raw/academic_payload.json
        """,
    )
    parser.add_argument(
        "--payload", type=str, default="data/raw/academic_payload.json",
        help="Path to the dynamic content payload JSON (schema definition)",
    )
    parser.add_argument(
        "--template_image", type=str, default=None,
        help="Path to the master design image (PNG/JPG). "
             "If provided, colours and saliency are extracted at runtime "
             "via VisionExtractor (K-Means LAB + SIFT).",
    )
    parser.add_argument(
        "--content_data", type=str, default=None,
        help="Path to a JSON file mapping schema variables to real content strings. "
             "Example: {\"{{Student_Name}}\": \"Maria Santos\", ...}. "
             "If omitted, domain-appropriate placeholder strings are used.",
    )
    parser.add_argument(
        "--canvas_w", type=int, default=None,
        help="Canvas width in pixels (overrides image size and domain defaults)",
    )
    parser.add_argument(
        "--canvas_h", type=int, default=None,
        help="Canvas height in pixels (overrides image size and domain defaults)",
    )
    parser.add_argument(
        "--population", type=int, default=5,
        help="Number of metaheuristic candidates to generate (default: 5)",
    )
    parser.add_argument(
        "--no_gnn", action="store_true",
        help="Skip GNN inference — useful for baseline comparison",
    )
    parser.add_argument(
        "--weights", type=str, default=DEFAULT_WEIGHTS,
        help="Path to trained GNN weights .pth file",
    )
    parser.add_argument(
        "--yolo_weights", type=str, default=DEFAULT_YOLO_WEIGHTS,
        help="Path to fine-tuned YOLOv8 weights for Stage 0b Semantic Layout "
             "Parsing. Defaults to themesync_yolo_v2.pt (fine-tuned on real "
             "master-layout images) if present, else themesync_yolo_v1.pt "
             "(CGL-Dataset only). Stage 0b is skipped gracefully if neither "
             "exists.",
    )
    parser.add_argument(
        "--output_dir", type=str, default="data/rendered/",
        help="Directory to write SVG output (default: data/rendered/)",
    )
    parser.add_argument(
        "--font_family", type=str, default=None,
        help="CSS font-family stack to inject as the administrative "
             "typography constraint (Table 1, p. 49). Defaults to the "
             "renderer's built-in Montserrat stack if omitted.",
    )

    args = parser.parse_args()

    run_pipeline(
        payload_path=args.payload,
        template_image=args.template_image,
        content_data_path=args.content_data,
        canvas_w=args.canvas_w,
        canvas_h=args.canvas_h,
        population=args.population,
        use_gnn=not args.no_gnn,
        weights_path=args.weights,
        yolo_weights_path=args.yolo_weights,
        output_dir=args.output_dir,
        font_family=args.font_family,
    )


if __name__ == "__main__":
    main()
