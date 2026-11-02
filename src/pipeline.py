"""
ThemeSync Pipeline Orchestrator
================================
Entry-point for the full end-to-end ThemeSync layout generation pipeline.

Execution order:
  0.  Template Ingestion         (image → LAB centroids + SIFT saliency)  [optional]
  0b. Semantic Layout Parsing    (image → detected logo/text/underlay/
                                   embellishment nodes via YOLO+OCR)      [optional]
  0c. Stylistic Marker Extraction (image + 0b → text-free background,
                                   motifs, title artwork; notes §3.23)   [optional]
  —   Pre-orchestration schema validation (typography + content payload,
      Chapter 3 p.44); a violation rejects the run
  1.  Dynamic Node Instantiation (payload → node tensors)
  2.  GNN Inference              (naive stack → learned vertical rhythm, v2)
  3.  CSP Resolution             (Cassowary hard + soft constraints)
  4.  Metaheuristic Ranking      (AAPA: margin × rhythm × motif arrangement,
                                  each scored on its own composed background)
  5.  Aesthetic Rendering        (SVG output of the active candidate)
  6.  State Serialization        (JSON state chain, Formulas 3.9-3.10)

OrchestrationSession keeps a run open for Figure 3's Active Orchestration
workspace: after run(), each designer action (move, resize, lock) is a
discrete event that re-solves the layout with the adjusted nodes as Hard
constraints and appends a state to the chain. run_pipeline() is the one-shot
wrapper the CLI, the tests and the evaluation scripts use.

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
import copy
import functools
import json
import os
import re
import sys
import time
import torch
from PIL import Image

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
from graph_builder import LayoutGraphBuilder, naive_stack, register_to_anchors, structure_start
from cassowary_engine import ConstraintSolverEngine
from candidate_generator import ARCHETYPES, MetaheuristicStateExplorer, prefer_archetype, solver_for, variations_for
import structure_mapping
from optimization_engine import HeuristicEvaluator
from aesthetic_renderer import AestheticSVGRenderer, DEFAULT_TYPOGRAPHY, _palette_from_centroids, default_content
from state_manager import StateChain, StateManager
from schema_validation import FONT_WEIGHTS, content_schema, validate_content, validate_typography
from stylistic_markers import build_style_kit, cut_out
from template_ingestor import TemplateIngestor
from layout_extractor import LayoutExtractor

# ---------------------------------------------------------------------------
# Constants — synthetic fallback values (used when no template image is given)
# These match the values used during GNN training for the CSPC institution.
# ---------------------------------------------------------------------------
# v3: trained to turn the master's mapped structure (or, without a master,
# the naive stack) into a clean layout (notes §3.26); v2 (naive stack only,
# §3.22) and v1 (degenerate y-predictions) are kept for the record.
_GNN_V3 = os.path.join(os.path.dirname(_SRC), "themesync_gnn_v3.pth")
_GNN_V2 = os.path.join(os.path.dirname(_SRC), "themesync_gnn_v2.pth")
DEFAULT_WEIGHTS = _GNN_V3 if os.path.exists(_GNN_V3) else _GNN_V2
# v5 (the batch re-annotated to guidelines v2, with an "illustration" class,
# once trained) over v4 (YOLOv8s at 1024 px on the cleaned 124-image batch,
# notes §3.25) over v3 (YOLOv8n, 124 images) over v2 (65 images) over v1
# (CGL-only) — see notes/gnn_fixes_and_methodology_notes.md sections 3.7,
# 3.12, 3.25 and notes/annotation_guidelines.md.
_YOLO_V5 = os.path.join(os.path.dirname(_SRC), "themesync_yolo_v5.pt")   # re-annotated, 5 classes
_YOLO_V4 = os.path.join(os.path.dirname(_SRC), "themesync_yolo_v4.pt")
_YOLO_V3 = os.path.join(os.path.dirname(_SRC), "themesync_yolo_v3.pt")
_YOLO_V2 = os.path.join(os.path.dirname(_SRC), "themesync_yolo_v2.pt")
_YOLO_V1 = os.path.join(os.path.dirname(_SRC), "themesync_yolo_v1.pt")
DEFAULT_YOLO_WEIGHTS = (
    _YOLO_V5 if os.path.exists(_YOLO_V5)
    else _YOLO_V4 if os.path.exists(_YOLO_V4)
    else _YOLO_V3 if os.path.exists(_YOLO_V3)
    else _YOLO_V2 if os.path.exists(_YOLO_V2)
    else _YOLO_V1
)
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
      2. Domain defaults from the payload (1200×900 cert / 744×1052 ID),
         matching each payload's own target_aspect_ratio. The ID default is
         an A6-proportioned (1:√2) event lanyard pass, measured from the
         group's 18 real CSPC event IDs (mean width/height 0.70), not a CR80
         student card — see notes/gnn_fixes_and_methodology_notes.md §3.15.

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
    return (744, 1052) if domain == "identification_card" else (1200, 900)


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
    mockup). The *positions* of detected nodes still never feed the
    generated document (notes §3.5-3.7); what does:
      - the detected logo's aspect ratio, into Stage 1's sizing for the
        schema node marked `lock_aspect_ratio: true` (section 3.11, Figure
        2's "Affine scaling");
      - the logo artwork, cropped from the master layout, rendered in the
        logo node / logo row (sections 3.14-3.15);
      - the embellishment and title detections, from which Stage 0c cuts
        the master's motifs and title artwork (section 3.23).
    User-supplied logo files override the logo crops. See `_resolve_logos()`.

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


def stage_stylistic_markers(template_image: str, detected_nodes: list, output_dir: str,
                            stem: str, use_wordmark: bool = True, wordmark_path: str = None,
                            motif_paths: list = None) -> tuple:
    """
    Stage 0c — Stylistic Marker Extraction (Chapter 3, p.38; p.51's
    "scale-invariant stylistic markers"; Figure 1(b)'s inpainted
    background). Builds the style kit the renderer projects onto the target
    format: the master's text-free background, its motifs, and its title
    artwork (stylistic_markers.py). Detected logos are excluded from the
    motifs so the brand marks aren't doubled as decoration.
    """
    t0 = time.perf_counter()
    logo_boxes = [n["bbox"] for n in detected_nodes or [] if n.get("semantic_category") == "logo"]
    kit = build_style_kit(template_image, detected_nodes or [], os.path.join(output_dir, "style_kit"),
                          stem, logo_boxes=logo_boxes, use_wordmark=use_wordmark,
                          wordmark_path=wordmark_path, motif_paths=motif_paths)
    elapsed = time.perf_counter() - t0
    _print_stage("0c. Stylistic Marker Extraction", elapsed)
    print(f"     → Background: text-free layer rebuilt from the master's border")
    print(f"     → Motifs: {len(kit['motifs'])}  |  Title artwork: "
          f"{kit['wordmark']['source'] if kit['wordmark'] else 'none (typed title)'}")
    return kit, elapsed


def stage_instantiate(payload_path: str, canvas_w: int, canvas_h: int,
                       detected_logo_ratio: float = None, logo_source: str = None):
    t0 = time.perf_counter()
    instantiator = NodeInstantiator(canvas_width=canvas_w, canvas_height=canvas_h)
    nodes = instantiator.instantiate_payload(payload_path, detected_logo_ratio=detected_logo_ratio)
    elapsed = time.perf_counter() - t0
    _print_stage("1. Dynamic Node Instantiation", elapsed)
    print(f"     → {len(nodes)} node(s) instantiated for canvas {canvas_w}×{canvas_h}")
    if detected_logo_ratio:
        print(f"     → Logo aspect ratio locked to {detected_logo_ratio:.2f}:1 "
              f"({logo_source or 'Stage 0b'}, Affine scaling)")
    return nodes, elapsed


def _overlap_ratio(a: list, b: list) -> float:
    """Intersection area over the *smaller* box's area, for [x, y, w, h] boxes —
    catches a small duplicate detection nested inside a larger one, which
    plain IoU would score as low overlap."""
    ix = max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    smaller = min(a[2] * a[3], b[2] * b[3])
    return (ix * iy / smaller) if smaller > 0 else 0.0


def _select_logo_row(detected_layout_nodes: list, image_h: float, min_conf: float = 0.4,
                     max_logos: int = 6) -> list:
    """
    The master layout's institutional logo row, left to right.

    Organisational logos (CSPC, SSC, CCS, JPCS...) sit side by side in a row
    — usually along the top, sometimes in the footer (ORSEM, SEARCH SSC) or
    a third of the way down (HALUBILO) — while other "logo" detections are
    stray marks: an emblem behind a title, windows on an illustrated house,
    social-media icons along the bottom edge. So (notes §3.25):
      1. logos with conf >= `min_conf`, minus tiny marks in the bottom 5%
         of the poster (social-media icons), overlapping duplicates dropped;
      2. grouped into rows (centres within half a logo height, similar
         heights);
      3. the most confident row of at least two logos, looking first in
         the top quarter of the poster, then the bottom quarter, then the
         middle (the organisers' row outranks, e.g., SIKLAB's row of
         participating colleges in its footer);
      4. no such row: the single most confident logo, top band first.
    At most `max_logos`, left to right.
    """
    logos = [n for n in (detected_layout_nodes or []) if n.get("semantic_category") == "logo"]
    if not logos:
        return []

    def cy(n):
        return n["bbox"][1] + n["bbox"][3] / 2.0

    strong = [n for n in logos if n.get("detection_confidence", 0.0) >= min_conf
              and not (cy(n) >= 0.95 * image_h and n["bbox"][3] < 0.045 * image_h)]
    strong.sort(key=lambda n: -n.get("detection_confidence", 0.0))
    kept = []
    for n in strong:
        if all(_overlap_ratio(n["bbox"], k["bbox"]) < 0.5 for k in kept):
            kept.append(n)
    if not kept:
        return [max(logos, key=lambda n: n.get("detection_confidence", 0.0))]

    rows = []
    for n in sorted(kept, key=cy):
        for row in rows:
            ref = max(row, key=lambda r: r["bbox"][3])
            h_ratio = max(n["bbox"][3], ref["bbox"][3]) / max(1e-6, min(n["bbox"][3], ref["bbox"][3]))
            if abs(cy(n) - cy(ref)) <= 0.5 * max(n["bbox"][3], ref["bbox"][3]) and h_ratio <= 1.8:
                row.append(n)
                break
        else:
            rows.append([n])

    def band(row):
        centre = sum(cy(n) for n in row) / len(row) / image_h
        return "top" if centre <= 0.25 else "bottom" if centre >= 0.75 else "middle"

    def confidence(row):
        return sum(n.get("detection_confidence", 0.0) for n in row)

    for tier in ("top", "bottom", "middle"):
        rows_here = [r for r in rows if band(r) == tier and len(r) >= 2]
        if rows_here:
            best = max(rows_here, key=confidence)
            best = sorted(best, key=lambda n: -n.get("detection_confidence", 0.0))[:max_logos]
            return sorted(best, key=lambda n: n["bbox"][0])
    for tier in ("top", "bottom", "middle"):
        singles = [r[0] for r in rows if band(r) == tier]
        if singles:
            return [max(singles, key=lambda n: n.get("detection_confidence", 0.0))]
    return [kept[0]]


def _resolve_logos(logo_images: list, template_image: str, detected_layout_nodes: list,
                   output_dir: str, stem: str) -> dict:
    """
    Decides which logo artwork the generated document carries:
      1. user-uploaded `logo_images`, if any (override detection — the fix
         when YOLO picks the wrong mark or misses one), in the order given;
      2. otherwise the master layout's Stage 0b logo row (_select_logo_row),
         each cropped (4% padding), background cleared, and saved next to
         the output as ThemeSync_<format>_logo_<i>.png;
      3. otherwise nothing — the renderer falls back to a drawn badge.
    `primary` is the one logo a single-logo slot uses (the certificate's
    seal): the first upload, or the most confident logo in the row. Its
    aspect ratio drives Stage 1's `lock_aspect_ratio` sizing.
    """
    none = {"row": [], "primary": None, "ratio": None, "source": None}
    if logo_images:
        with Image.open(logo_images[0]) as img:
            w, h = img.size
        return {"row": list(logo_images), "primary": logo_images[0],
                "ratio": (w / h if h else None),
                "source": f"uploaded logo{'s' if len(logo_images) > 1 else ''}"}

    if not template_image:
        return none
    with Image.open(template_image) as img:
        row = _select_logo_row(detected_layout_nodes, img.height)
        if not row:
            return none
        os.makedirs(output_dir, exist_ok=True)
        paths = []
        for i, node in enumerate(row):
            path = os.path.join(output_dir, f"ThemeSync_{stem}_logo_{i}.png")
            cut_out(img, node["bbox"]).save(path)
            paths.append(path)

    best = max(range(len(row)), key=lambda i: row[i].get("detection_confidence", 0.0))
    _, _, bw, bh = row[best]["bbox"]
    confs = ", ".join(f"{n.get('detection_confidence', 0.0):.2f}" for n in row)
    return {"row": paths, "primary": paths[best], "ratio": (bw / bh if bh > 0 else None),
            "source": f"Stage 0b crop of {len(row)} logo(s), conf={confs}"}


def _arrange_rows(nodes: list, header_side: str, logos: dict) -> None:
    """
    Puts pairs of nodes on one line (cassowary_engine's `row`; notes §3.57):
      - the organisation text beside the logo row, on the side the master
        has it (`header_side`); the logos' box is cut to their natural width
        so the text sits right against them;
      - the certificate number beside the date, one at each margin, as on
        printed certificates.
    In place; a node keeps its Spatial Hierarchy Index.
    """
    def find(*keys):
        return next((n for n in nodes if any(k in n["node_id"] for k in keys)), None)

    logo = next((n for n in nodes if n.get("structural_class") == "image_node" and "Logo" in n["node_id"]), None)
    header = find("Organization_Header", "Issuing_Organization")
    if header_side and logo and header:
        paths = (logos.get("row") if "Logos" in logo["node_id"] else None) or \
                ([logos["primary"]] if logos.get("primary") else [])
        aspects = []
        for path in paths:
            try:
                with Image.open(path) as im:
                    aspects.append(im.width / max(1, im.height))
            except OSError:
                pass
        if aspects:
            h = float(logo["bbox"][3])
            logo["bbox"][2] = round(h * sum(aspects) + 0.25 * h * (len(aspects) - 1), 2)
        header["row"] = {"with": logo["node_id"], "side": header_side}
        header["text_align"] = "left" if header_side == "right" else "right"
    date, number = find("Date_Issued"), find("Certificate_ID")
    if date and number:
        number["row"] = {"with": date["node_id"], "side": "right", "split": True}
        date["text_align"], number["text_align"] = "left", "right"


def _stack(nodes: list) -> list:
    return sorted((n for n in nodes if n.get("structural_class") not in ("repeating_group", "decor")),
                  key=lambda n: n["spatial_hierarchy"])


def _starts(stack: list, canvas_w: float, canvas_h: float, structure: dict = None,
            domain: str = None) -> tuple:
    """Starting positions for the stacked nodes: from the master's mapped
    structure when there is one (notes §3.26), else the naive stack."""
    sizes = [(n["bbox"][2] / canvas_w, n["bbox"][3] / canvas_h) for n in stack]
    anchors = structure_mapping.anchors_for(stack, structure, domain) if structure else {}
    return (structure_start(sizes, anchors) if anchors else naive_stack(sizes)), anchors


def stage_gnn_inference(nodes: list, canvas_w: int, canvas_h: int,
                         weights_path: str, device: torch.device,
                         color_centroids: list, saliency_weight: float, structure: dict = None,
                         domain: str = None):
    """
    Stage 2 — GNN spatial inference.

    The stacked (singular) nodes start from the master's mapped structure —
    each node with a counterpart on the master (logo row, organisation
    header, title, details) where that counterpart sits, the rest in order
    between them (structure_mapping, graph_builder.structure_start) — or,
    without a master, from the naive stack; the GNN (v3, notes §3.26) was
    trained on both and turns either into a clean layout. With a master,
    its output is registered to the anchors (register_to_anchors): the
    mapped nodes keep the master's positions and the GNN places the rest.
    Repeating groups (signature rows) and decor aren't part of the stack;
    the CSP places them. Colour centroids and saliency weight come from
    Stage 0.
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

    stack = _stack(nodes)
    starts, anchors = _starts(stack, canvas_w, canvas_h, structure, domain)
    for i, (node, (sx, sy)) in enumerate(zip(stack, starts)):
        node["bbox"][0] = round(sx * canvas_w, 2)
        node["bbox"][1] = round(sy * canvas_h, 2)
        node["structure_anchor"] = i in anchors

    graph_data = builder.build_graph({
        "extracted_nodes":           stack,
        "extracted_color_centroids": color_centroids,   # ← real or fallback
        "extracted_saliency_weight": saliency_weight,   # ← real or fallback
        "canvas_w":                  canvas_w,
        "canvas_h":                  canvas_h,
    })
    predicted = False

    # One stacked node has no neighbours to relate to (and no edges, which
    # the model can't take): its start position stands (notes §3.54).
    if graph_data is not None and len(stack) > 1:
        graph_data = graph_data.to(device)
        with torch.no_grad():
            predicted_coords = model(graph_data)

        builder.apply_predictions(stack, predicted_coords, canvas_w, canvas_h)
        predicted = True
        if anchors:
            cys = register_to_anchors([(n["bbox"][1] + n["bbox"][3] / 2.0) / canvas_h for n in stack], anchors)
            for node, cy in zip(stack, cys):
                node["bbox"][1] = round(max(0.0, min(cy * canvas_h - node["bbox"][3] / 2.0,
                                                     canvas_h - node["bbox"][3])), 2)

    elapsed = time.perf_counter() - t0
    _print_stage("2. GNN Spatial Inference", elapsed)
    print(f"     → Weights: {weights_status}")
    start = (f"master structure ({len(anchors)} of {len(stack)} node(s) anchored, output registered to them)"
             if anchors else "naive stack")
    print(f"     → Predictions applied: {predicted} ({len(stack)} stacked node(s), from the {start})")
    return nodes, elapsed


def stage_structure_hints(nodes: list, canvas_w: int, canvas_h: int, structure: dict,
                          domain: str = None):
    """
    Ablation for Stage 2 (Phase 3, notes §3.26): the master's mapped
    structure as the solver's position preferences *without* the GNN's
    refinement — separates what the mapping contributes from what the GNN
    adds.
    """
    t0 = time.perf_counter()
    stack = _stack(nodes)
    starts, anchors = _starts(stack, canvas_w, canvas_h, structure, domain)
    for i, (node, (sx, sy)) in enumerate(zip(stack, starts)):
        node["bbox"][0] = round(sx * canvas_w, 2)
        node["bbox"][1] = round(sy * canvas_h, 2)
        node["structure_anchor"] = i in anchors
        node["structure_hint"] = True
    elapsed = time.perf_counter() - t0
    _print_stage("2. Structure mapping (no GNN, ablation)", elapsed)
    print(f"     → {len(anchors)} of {len(stack)} stacked node(s) anchored to the master")
    return nodes, elapsed


def stage_csp_resolve(nodes: list, canvas_w: int, canvas_h: int, margin: float = 50.0,
                      vgap: float = 16.0):
    t0 = time.perf_counter()
    engine = ConstraintSolverEngine(canvas_width=canvas_w, canvas_height=canvas_h,
                                    margin=margin, default_vgap=vgap)
    resolved = engine.execute_relational_logic(nodes)
    elapsed = time.perf_counter() - t0
    _print_stage("3. Cassowary CSP Resolution", elapsed)
    hard = sum(1 for n in resolved if n.get("constraint_type") == "Hard")
    print(f"     → Hard constraints: {hard} | Soft constraints: {len(resolved) - hard}")
    return resolved, elapsed


def stage_rank_candidates(guided_nodes: list, population: int, canvas_w: int, canvas_h: int,
                          saliency_map: dict = None, style_kit: dict = None,
                          domain: str = "academic_certificate", panel_rgb: tuple = (255, 255, 255),
                          palette: dict = None, structure_guided: bool = False):
    t0 = time.perf_counter()
    explorer = MetaheuristicStateExplorer(
        canvas_width=canvas_w, canvas_height=canvas_h, saliency_map=saliency_map,
        style_kit=style_kit, domain=domain, panel_rgb=panel_rgb, palette=palette,
        structure_guided=structure_guided,
    )
    ranked = explorer.generate_and_rank_candidates(guided_nodes, population_size=population)
    elapsed = time.perf_counter() - t0
    _print_stage("4. Metaheuristic Candidate Ranking", elapsed)
    print(f"     → {len(ranked)} candidate(s) evaluated")
    print()
    print(f"  {'Rank':<6} {'Candidate':<14} {'C_total':>8}  Variation")
    print(f"  {'-'*6} {'-'*14} {'-'*8}  {'-'*40}")
    for i, c in enumerate(ranked):
        marker = " ◀ WINNER" if i == 0 else ""
        print(f"  [{i+1}]   {c['candidate_id']:<14} {c['c_total']:>8.4f}  {c['label']}{marker}")
    return ranked, elapsed


def stage_serialize_state(resolved_nodes: list):
    t0 = time.perf_counter()
    manager = StateManager()
    filepath = manager.serialize_state(resolved_nodes, version="v1")
    elapsed = time.perf_counter() - t0
    _print_stage("6. FSM State Serialization", elapsed)
    print(f"     → Saved: {filepath}")
    return elapsed


# ---------------------------------------------------------------------------
# Orchestration session
# ---------------------------------------------------------------------------

def _hex_to_rgb(hexcode: str) -> tuple:
    return tuple(int(hexcode[i:i + 2], 16) for i in (1, 3, 5))


STAGE_LABELS = {
    "template_ingestion": "0. Template Ingestion",
    "layout_parsing":     "0b. Semantic Layout Parsing (YOLO+OCR)",
    "stylistic_markers":  "0c. Stylistic Marker Extraction",
    "instantiation":      "1. Dynamic Node Instantiation",
    "gnn_inference":      "2. GNN Spatial Inference",
    "csp_resolution":     "3. Cassowary CSP Resolution",
    "ranking":            "4. Metaheuristic Ranking",
    "rendering":          "5. Aesthetic SVG Rendering",
    "serialization":      "6. FSM State Serialization",
}


def _timed_event(method):
    """Records a designer event's wall-clock time (re-solve, re-score,
    re-render, state save) in session.event_ms under the new state's id,
    for the latency metric (Chapter 3, p.55)."""
    @functools.wraps(method)
    def timed(self, *args, **kwargs):
        t0 = time.perf_counter()
        state = method(self, *args, **kwargs)
        self.event_ms[state["state_id"]] = round((time.perf_counter() - t0) * 1000, 1)
        return state
    return timed


class OrchestrationSession:
    """
    One master layout projected onto one target format, held open for
    Figure 3's Active Orchestration workspace.

    run() executes Stages 0-6 once. Afterwards every designer action is a
    discrete, terminal event (Formula 3.9, S_{t+1} = δ(S_t, e_t)): the
    layout is re-solved from the same GNN-guided nodes with every manually
    adjusted node as a Hard constraint (Formula 3.10), re-scored, re-rendered,
    and appended to the JSON state chain. Nothing already in the chain is
    ever changed.

    use_gnn / use_structure select the Stage 2 condition (notes §3.26):
      GNN-guided      use_gnn=True  (structure defaults to on) — the master's
                      mapped structure refined by the GNN
      baseline        use_gnn=False, use_structure=False — naive stack, no GNN
      mapping only    use_gnn=False, use_structure=True — the ablation
    """

    def __init__(self, payload_path: str, template_image: str = None, content_data=None,
                 typography: dict = None, use_gnn: bool = True,
                 weights_path: str = DEFAULT_WEIGHTS, yolo_weights_path: str = DEFAULT_YOLO_WEIGHTS,
                 output_dir: str = "data/rendered/", logo_images: list = None, population: int = 6,
                 canvas_w: int = None, canvas_h: int = None, font_family: str = None,
                 use_wordmark: bool = True, wordmark_path: str = None, motif_paths: list = None,
                 detected_nodes: list = None, use_structure: bool = None, background_path: str = None):
        if not os.path.exists(payload_path):
            raise FileNotFoundError(f"Payload not found at '{payload_path}'")
        self.payload_path = payload_path
        self.payload_meta = _load_json(payload_path)
        self.domain = self.payload_meta.get("domain_context", "layout")
        self.stem = self.domain.replace("_", "-")
        self.template_image = template_image
        self.content_data = _load_json(content_data) if isinstance(content_data, str) else content_data
        self.content_data_path = content_data if isinstance(content_data, str) else None
        self.typography = dict(DEFAULT_TYPOGRAPHY)
        self.typography.update({k: v for k, v in (typography or {}).items() if v is not None})
        if font_family:
            self.typography["family"] = font_family
        self.use_gnn = use_gnn
        self.use_structure = use_gnn if use_structure is None else use_structure
        self.weights_path = weights_path
        self.yolo_weights_path = yolo_weights_path
        self.output_dir = output_dir
        self.logo_images = logo_images
        self.population = population
        self.use_wordmark = use_wordmark
        self.wordmark_path = wordmark_path
        self.motif_paths = motif_paths
        self.background_path = background_path   # a picture the designer put in place of the text-free background
        self.canvas_w, self.canvas_h = _derive_canvas(self.payload_meta, canvas_w, canvas_h)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.timings = {}
        self.chain = StateChain()
        self.detected_nodes = detected_nodes   # reuse Stage 0b from the dashboard if given
        self.ingestion = None
        self.style_kit = {}
        self.structure = {}
        self.composition = {}          # the master's composition cues (notes §3.31)
        self.preferred_archetype = None
        self.structure_guided = False
        self.logos = {"row": [], "primary": None, "ratio": None, "source": None}
        self.candidates = []
        self.validation = {}
        # Restoring a state brings back the words and typography it was
        # rendered with, too; these are the values before any edit.
        self._initial_content = copy.deepcopy(self.content_data)
        self._initial_typography = dict(self.typography)
        self._undo, self._redo = [], []   # state indices (undo / redo)
        self.event_ms = {}                # state id → that event's latency (ms)
        # A mail merge (the dashboard's mail_merge.py): {"fields": [...],
        # "rows": [{field: value}], ...}. Its fields show placeholders on the
        # canvas, aren't text-editable, and take each row's words in
        # render_merged. None: no merge (notes §3.53).
        self.merge = None
        # The designer's per-element styles (Step 2's Style tools): node id →
        # {fill, bold, italic, align, opacity, flip, image}. Each change is a
        # state; restore, undo and redo bring the styles back with it.
        self.styles = {}
        self.style_contrast = {}          # styled text's contrast in the last render
        # Elements the designer added (id → node) and deleted (ids), in
        # effect at the current state; restore, undo and redo bring them
        # back with it (notes §3.56)
        self.added = {}
        self.removed = []
        self.rendered_path = os.path.join(output_dir, f"ThemeSync_{self.stem}_populated.svg")
        self.chain_path = os.path.join(output_dir, f"ThemeSync_{self.stem}_state_chain.json")

    @property
    def condition(self) -> str:
        if self.use_gnn:
            return "gnn"
        return "mapping" if self.use_structure else "baseline"

    # -- stages ---------------------------------------------------------

    def run(self) -> dict:
        _print_header("ThemeSync — Design Orchestration Pipeline")

        # Stage 0 / 0b / 0c
        self.saliency_map = None
        if self.template_image:
            self.ingestion, self.timings["template_ingestion"] = stage_template_ingestion(self.template_image)
            self.color_centroids = self.ingestion["color_centroids"]
            self.saliency_weight = self.ingestion["saliency_weight"]
            self.saliency_map = self.ingestion["saliency_map"]
            ingestion_mode = f"real image → {self.ingestion['palette_hex']}"
            if self.detected_nodes is None:
                self.detected_nodes, self.timings["layout_parsing"] = stage_layout_parsing(
                    self.template_image, self.yolo_weights_path)
            else:
                self.timings["layout_parsing"] = 0.0
        else:
            self.color_centroids = _FALLBACK_CENTROIDS
            self.saliency_weight = _FALLBACK_SALIENCY
            self.timings["template_ingestion"] = 0.0
            self.timings["layout_parsing"] = 0.0
            ingestion_mode = "synthetic fallback (no --template_image provided)"
            print(f"\n  ⊘  Stage 0 skipped — {ingestion_mode}")

        self.palette = _palette_from_centroids(self.color_centroids)
        self.logos = _resolve_logos(self.logo_images, self.template_image, self.detected_nodes,
                                    self.output_dir, self.stem)
        if self.template_image:
            self.style_kit, self.timings["stylistic_markers"] = stage_stylistic_markers(
                self.template_image, self.detected_nodes, self.output_dir, self.stem,
                use_wordmark=self.use_wordmark, wordmark_path=self.wordmark_path,
                motif_paths=self.motif_paths)
            if self.background_path:
                # Step 1's replacement for the text-free background; the
                # candidates' legibility is scored against it (notes §3.53)
                self.style_kit = dict(self.style_kit, background=self.background_path)
            if self.detected_nodes:
                with Image.open(self.template_image) as img:
                    mw, mh = img.size
                # Every condition follows the master's composition (the
                # archetype); only GNN and mapping use its structure.
                self.composition = structure_mapping.master_composition(self.detected_nodes, mw, mh)
                self.preferred_archetype = structure_mapping.archetype_for(self.composition, self.domain)
                logo_row = _select_logo_row(self.detected_nodes, mh)
                # Logos and organisation text on one line, like the master
                # (every condition, as with the archetype; notes §3.57)
                side = structure_mapping.header_beside_logos(self.detected_nodes, mw, mh, logo_row)
                if side:
                    self.composition = dict(self.composition, header_beside_logos=side,
                                            evidence=self.composition.get("evidence", [])
                                            + [f"organisation text {side} of the logo row"])
                if self.use_structure:
                    self.structure = structure_mapping.master_structure(self.detected_nodes, mw, mh, logo_row)
        else:
            self.timings["stylistic_markers"] = 0.0
        self.structure_guided = bool(self.structure) and self.use_structure

        print(f"\n  Payload        : {self.payload_path}")
        print(f"  Domain         : {self.domain}")
        print(f"  Canvas         : {self.canvas_w} × {self.canvas_h} px")
        print(f"  Device         : {self.device}")
        print(f"  Template Image : {self.template_image or '(none — using synthetic fallback)'}")
        print(f"  Content Data   : {self.content_data_path or ('(given)' if self.content_data else '(none — using domain defaults)')}")
        print(f"  Condition      : {self.condition}")
        print(f"  Master structure: {', '.join(f'{k} at {v[1]:.2f}' for k, v in self.structure.items()) or '(none)'}")
        print(f"  Layout type    : {self.preferred_archetype or '(fitness alone)'}"
              + (f" — {'; '.join(self.composition.get('evidence', []))}" if self.composition.get('evidence') else ""))
        print(f"  Population     : {self.population}")
        print(f"  Palette Source : {ingestion_mode}")

        # Pre-orchestration schema validation (Chapter 3, p.44)
        self.validation = {"typography": validate_typography(self.typography, self.canvas_w, self.canvas_h)}
        if self.content_data:
            self.validation["content"] = validate_content(self.content_data, self.payload_meta)
        problems = [e for v in self.validation.values() for e in v["errors"]]
        if problems:
            raise ValueError("Schema validation rejected the initialization:\n  - " + "\n  - ".join(problems))
        print(f"  Schema Check   : passed ({', '.join(self.validation)})")

        # Stage 1
        self.base_nodes, self.timings["instantiation"] = stage_instantiate(
            self.payload_path, self.canvas_w, self.canvas_h,
            detected_logo_ratio=self.logos["ratio"], logo_source=self.logos["source"])
        _arrange_rows(self.base_nodes, self.composition.get("header_beside_logos"), self.logos)

        # Stage 2
        structure = self.structure if self.use_structure else None
        if self.use_gnn:
            self.guided_nodes, self.timings["gnn_inference"] = stage_gnn_inference(
                copy.deepcopy(self.base_nodes), self.canvas_w, self.canvas_h, self.weights_path,
                self.device, self.color_centroids, self.saliency_weight, structure=structure,
                domain=self.domain)
        elif structure:
            self.guided_nodes, self.timings["gnn_inference"] = stage_structure_hints(
                copy.deepcopy(self.base_nodes), self.canvas_w, self.canvas_h, structure, self.domain)
        else:
            print("\n  ⊘  GNN Inference skipped (baseline mode)")
            self.guided_nodes = copy.deepcopy(self.base_nodes)
            self.timings["gnn_inference"] = 0.0

        # Stage 3 (the first variation on the unguided nodes — timing and State_00)
        first = variations_for(self.domain)[0]
        t0 = time.perf_counter()
        baseline_nodes = solver_for(first, self.canvas_w, self.canvas_h).execute_relational_logic(
            copy.deepcopy(self.base_nodes))
        self.timings["csp_resolution"] = time.perf_counter() - t0
        _print_stage("3. Cassowary CSP Resolution", self.timings["csp_resolution"])

        # Stage 4
        self.candidates, self.timings["ranking"] = stage_rank_candidates(
            self.guided_nodes, self.population, self.canvas_w, self.canvas_h,
            saliency_map=self.saliency_map, style_kit=self.style_kit, domain=self.domain,
            panel_rgb=_hex_to_rgb(self.palette["panel"]), palette=self.palette,
            structure_guided=self.structure_guided)
        self.candidates = prefer_archetype(self.candidates, self.preferred_archetype, self.composition)
        winner = self.candidates[0]

        # States: baseline arrangement, then the ranked winner
        schema_log = {k: ("passed" if v["valid"] else "rejected") for k, v in self.validation.items()}
        self.chain.append("Baseline Init", {"type": "init", "schema_validation": schema_log},
                          baseline_nodes, fitness=self._fitness(baseline_nodes, first),
                          candidate_id=None, variation=dict(first))
        label = {"gnn": "GNN Relational", "mapping": "Structure mapping",
                 "baseline": "CSP Baseline"}[self.condition] + f" · {winner['candidate_id']}"
        self.chain.append(label, {"type": "candidate", "candidate_id": winner["candidate_id"],
                                  "rank": 1},
                          winner["nodes"], fitness=winner["metrics"],
                          candidate_id=winner["candidate_id"], variation=dict(winner["variation"]))

        # Stage 5
        t0 = time.perf_counter()
        self.render(winner["nodes"], self.rendered_path, winner["variation"])
        self.timings["rendering"] = time.perf_counter() - t0
        _print_stage("5. Aesthetic SVG Rendering", self.timings["rendering"])

        # Stage 6
        self.timings["serialization"] = stage_serialize_state(winner["nodes"])
        self.chain.save(self.chain_path)
        print(f"     → State chain: {self.chain_path}")

        self._print_summary(winner)
        return self.summary()

    # -- scoring and rendering -------------------------------------------

    def _explorer(self) -> MetaheuristicStateExplorer:
        return MetaheuristicStateExplorer(
            canvas_width=self.canvas_w, canvas_height=self.canvas_h, saliency_map=self.saliency_map,
            style_kit=self.style_kit, domain=self.domain, panel_rgb=_hex_to_rgb(self.palette["panel"]),
            palette=self.palette, structure_guided=self.structure_guided)

    def _saliency_for(self, nodes: list, variation: dict):
        """The legibility map for a layout: its own composed background when
        a style kit exists (as the explorer scores candidates), else the
        master's map."""
        if not self.style_kit.get("background"):
            return self.saliency_map
        return self._explorer().saliency(nodes, variation)

    def _fitness(self, nodes: list, variation: dict) -> dict:
        solver = solver_for(variation, self.canvas_w, self.canvas_h, self.structure_guided)
        evaluator = HeuristicEvaluator(canvas_width=self.canvas_w, canvas_height=self.canvas_h,
                                       saliency_map=self._saliency_for(nodes, variation),
                                       grid_bounds=(solver.left_bound, solver.right_bound),
                                       content_region=tuple(r * self.canvas_w for r in solver.region))
        return evaluator.evaluate_layout(nodes)

    def renderer(self, content: dict = None) -> AestheticSVGRenderer:
        """The session's renderer; `content` replaces the canvas's words
        (a mail-merge row)."""
        return AestheticSVGRenderer(
            canvas_width=self.canvas_w, canvas_height=self.canvas_h,
            original_filename=f"ThemeSync_{self.stem}",
            color_centroids=self.color_centroids,
            mock_data=self.content_data if content is None else content,
            domain_context=self.domain,
            logo_image_path=self.logos.get("primary"),
            logo_row_paths=self.logos.get("row"),
            style_kit=self.style_kit,
            typography=self.typography,
            styles=self.styles,
        )

    @staticmethod
    def archetype_of(variation: dict) -> dict:
        return ARCHETYPES[(variation or {}).get("archetype", "classic")]

    def render(self, nodes: list, path: str, variation: dict = None) -> str:
        variation = variation or (self.chain.current or {}).get("variation")
        renderer = self.renderer()
        out = renderer.render_nodes(nodes, path, archetype=self.archetype_of(variation))
        self.style_contrast = renderer.style_contrast
        return out

    def render_merged(self, values: dict, path: str) -> str:
        """The current layout with one mail-merge row's words in its merged
        fields (the layout itself isn't re-solved). Returns the SVG path."""
        state = self.chain.current
        content = dict(self.content(), **values)
        return self.renderer(content).render_nodes(state["nodes"], path,
                                                   archetype=self.archetype_of(state.get("variation")))

    def render_candidates(self, directory: str = None) -> list:
        """Renders every ranked candidate (Figure 3's Recommendation Engine
        thumbnails). Returns [(candidate, svg_path), ...] in rank order."""
        directory = directory or os.path.join(self.output_dir, "candidates")
        renderer = self.renderer()
        return [(c, renderer.render_nodes(c["nodes"], os.path.join(directory, f"{c['candidate_id']}.svg"),
                                          archetype=self.archetype_of(c["variation"])))
                for c in self.candidates]

    # -- human-in-the-loop events -----------------------------------------

    def _resolve(self, nodes: list, variation: dict) -> list:
        """
        Re-solves a canvas after an event: every stacked node starts again
        from its GNN-guided state, except Hard nodes, which keep the box the
        designer gave them (Formula 3.10); decor is re-placed around the new
        layout unless the designer has pinned a motif.
        """
        from decor import place_motifs

        hard = {n["node_id"]: n for n in nodes if n.get("constraint_type") == "Hard"}
        removed = set(self.removed)
        content = [n for n in copy.deepcopy(self.guided_nodes) if n["node_id"] not in removed]
        current = {n["node_id"]: n for n in nodes}
        content += [copy.deepcopy(current.get(nid, spec)) for nid, spec in self.added.items()
                    if nid not in removed and spec.get("structural_class") != "decor"]   # added text (§3.56)
        for n in content:
            if n["node_id"] in hard:
                n["bbox"] = [float(v) for v in hard[n["node_id"]]["bbox"]]
                n["constraint_type"] = "Hard"
        engine = solver_for(variation, self.canvas_w, self.canvas_h, self.structure_guided)
        content = engine.execute_relational_logic(content)

        decor = [copy.deepcopy(n) for n in nodes if n.get("structural_class") == "decor"
                 and n["node_id"] not in removed and n["node_id"] not in self.added]
        pictures = [copy.deepcopy(n) for n in nodes if n["node_id"] in self.added   # added pictures float
                    and n.get("structural_class") == "decor" and n["node_id"] not in removed]
        # A deleted motif keeps the others where they are (motif ids follow
        # their placement, so re-placing them would bring it back)
        if (self.style_kit.get("motifs") and not any(n.get("constraint_type") == "Hard" for n in decor)
                and not any(r.startswith("decor_") for r in removed)):
            decor = place_motifs(self.canvas_w, self.canvas_h, [n["bbox"] for n in content],
                                 self.style_kit["motifs"], variation.get("arrangement", 0))
        return content + decor + pictures

    @_timed_event
    def apply_event(self, event_type: str, node_id: str, bbox: list = None, hard: bool = None) -> dict:
        """
        One terminal designer event (Chapter 3, p.42):
          on-drop            node moved to bbox[0:2]      → Hard
          on-resize-complete node resized to bbox          → Hard
          lock-toggle        node pinned (hard=True) where it is, or released
                             back to the algorithm (hard=False)
        Returns the new state.
        """
        if event_type not in ("on-drop", "on-resize-complete", "lock-toggle"):
            raise ValueError(f"Unknown event type '{event_type}'")
        current = self.chain.current
        nodes = copy.deepcopy(current["nodes"])
        target = next((n for n in nodes if n["node_id"] == node_id), None)
        if target is None:
            raise KeyError(f"No node '{node_id}' on the canvas")
        before = list(target["bbox"])
        if bbox is not None:
            target["bbox"] = [round(float(v), 2) for v in bbox]
        if event_type == "lock-toggle":
            target["constraint_type"] = "Hard" if hard else "Soft"
        else:
            target["constraint_type"] = "Hard"

        variation = current.get("variation") or dict(variations_for(self.domain)[0])
        t0 = time.perf_counter()
        if target.get("structural_class") == "decor":
            resolved = nodes          # motifs sit outside the solver
        else:
            resolved = self._resolve(nodes, variation)
        t1 = time.perf_counter()
        verb = {"on-drop": "Moved", "on-resize-complete": "Resized",
                "lock-toggle": "Locked" if hard else "Released"}[event_type]
        hard_note = "Hard Const." if target["constraint_type"] == "Hard" else "Soft"
        fitness = self._fitness(resolved, variation)
        latency = {"solve": round((t1 - t0) * 1000, 1), "score": round((time.perf_counter() - t1) * 1000, 1)}
        self._mark()
        state = self.chain.append(
            f"{hard_note} [{node_id}]",
            {"type": event_type, "node_id": node_id, "before": before, "after": list(target["bbox"]),
             "constraint_type": target["constraint_type"], "summary": f"{verb} {node_id}",
             "latency_ms": latency},
            resolved, fitness=fitness,
            candidate_id=current.get("candidate_id"), variation=variation)
        self.render(resolved, self.rendered_path, variation)
        self.chain.save(self.chain_path)
        return state

    @_timed_event
    def edit_text(self, node_id: str, text: str) -> dict:
        """
        A text edit on the canvas (double-click → type → Enter): the content
        payload changes for one variable, is re-validated against the
        format's content schema (max_characters, p.44), and the canvas
        re-renders — the layout itself is unchanged; the renderer fits the
        new words to the node's box. A rejected edit raises ValueError.
        """
        content = self.content()
        if node_id not in self.canvas_text():
            raise KeyError(f"'{node_id}' has no editable text")
        before = content[node_id]
        if text == before:
            raise ValueError("The text is unchanged.")
        content[node_id] = text
        check = validate_content(content, self.payload_meta)
        if not check["valid"]:
            raise ValueError("Schema validation rejected the edit:\n  - " + "\n  - ".join(check["errors"]))
        self._mark()
        self.content_data = content
        current = self.chain.current
        state = self.chain.append(f"Text [{node_id}]",
                                  {"type": "text-edit", "node_id": node_id, "before": before, "after": text,
                                   "schema_validation": "passed", "summary": f"Edited text of {node_id}"},
                                  current["nodes"], fitness=current.get("fitness"),
                                  candidate_id=current.get("candidate_id"), variation=current.get("variation"),
                                  content=dict(content))
        self.render(current["nodes"], self.rendered_path, current.get("variation"))
        self.chain.save(self.chain_path)
        return state

    @_timed_event
    def select_candidate(self, candidate_id: str) -> dict:
        """Makes a ranked candidate the active canvas (Recommendation Engine)."""
        cand = next(c for c in self.candidates if c["candidate_id"] == candidate_id)
        rank = self.candidates.index(cand) + 1
        nodes, fitness = cand["nodes"], cand["metrics"]
        if self.added or self.removed:       # the designer's added and deleted elements carry over (§3.56)
            current = {n["node_id"]: n for n in self.chain.current["nodes"]}
            keep = [n for n in cand["nodes"] if n["node_id"] not in set(self.removed)]
            keep += [copy.deepcopy(current[nid]) for nid in self.added if nid in current]
            nodes = self._resolve(keep, cand["variation"])
            fitness = self._fitness(nodes, cand["variation"])
        self._mark()
        state = self.chain.append(f"Candidate {candidate_id} (rank {rank})",
                                  {"type": "candidate", "candidate_id": candidate_id, "rank": rank},
                                  nodes, fitness=fitness, candidate_id=candidate_id,
                                  variation=dict(cand["variation"]))
        self.render(nodes, self.rendered_path, cand["variation"])
        self.chain.save(self.chain_path)
        return state

    @_timed_event
    def restore_state(self, index: int, _label: str = None, _event: dict = None) -> dict:
        """Brings back an earlier canvas — its layout, words and typography —
        as a new state; the chain keeps everything in between."""
        old = self.chain.states[index]
        if _label is None:
            self._mark()
        self.content_data, self.typography, self.styles, elements = self._snapshot_at(index)
        self.added, self.removed = elements["added"], elements["removed"]
        extra = {"typography": dict(self.typography), "styles": copy.deepcopy(self.styles),
                 "elements": copy.deepcopy(elements)}
        if self.content_data is not None:
            extra["content"] = dict(self.content_data)
        state = self.chain.append(_label or f"Restored {old['state_id']}",
                                  _event or {"type": "restore", "restored": old["state_id"]},
                                  old["nodes"], fitness=old.get("fitness"),
                                  candidate_id=old.get("candidate_id"), variation=old.get("variation"),
                                  **extra)
        self.render(old["nodes"], self.rendered_path, old.get("variation"))
        self.chain.save(self.chain_path)
        return state

    def _snapshot_at(self, index: int) -> tuple:
        """(content, typography, styles, elements) in effect at state
        `index`: the latest text edit, typography change, style change,
        added or deleted element, or restore at or before it, else the
        session's initial values."""
        content = typography = styles = elements = None
        for s in reversed(self.chain.states[:index + 1]):
            if elements is None and s.get("elements") is not None:
                elements = s["elements"]
            if content is None and s.get("content") is not None:
                content = s["content"]
            if typography is None:
                typography = s.get("typography") or (s["event"].get("typography")
                                                     if s["event"].get("type") == "typography" else None)
            if styles is None and s.get("styles") is not None:
                styles = s["styles"]
            if content is not None and typography is not None and styles is not None:
                break
        return (copy.deepcopy(content if content is not None else self._initial_content),
                dict(typography or self._initial_typography), copy.deepcopy(styles or {}),
                copy.deepcopy(elements or {"added": {}, "removed": []}))

    # -- undo / redo (Figure 3's canvas: Ctrl+Z, Ctrl+Shift+Z) -------------

    def _mark(self) -> None:
        """Before an ordinary edit: the current state becomes the undo
        point, and the redo trail ends (the edit starts a new branch)."""
        self._undo.append(len(self.chain.states) - 1)
        self._redo.clear()

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @_timed_event
    def undo(self) -> dict:
        """The canvas as it was before the last edit, appended as a new
        state (like Restore — the chain is never rewritten)."""
        if not self._undo:
            raise ValueError("Nothing to undo.")
        index = self._undo.pop()
        self._redo.append(len(self.chain.states) - 1)
        sid = self.chain.states[index]["state_id"]
        return self.restore_state(index, _label=f"Undo → {sid}", _event={"type": "undo", "restored": sid})

    @_timed_event
    def redo(self) -> dict:
        """Re-applies the last undone edit (as a new state)."""
        if not self._redo:
            raise ValueError("Nothing to redo.")
        index = self._redo.pop()
        self._undo.append(len(self.chain.states) - 1)
        sid = self.chain.states[index]["state_id"]
        return self.restore_state(index, _label=f"Redo → {sid}", _event={"type": "redo", "restored": sid})

    # -- the canvas's words ------------------------------------------------

    def content(self) -> dict:
        """The content payload the canvas renders (a copy): the given
        content, or the format's sample content."""
        return dict(self.content_data or default_content(self.domain))

    def canvas_text(self) -> dict:
        """Words the designer can edit on the canvas: node id → text, for
        every text node and signature block — not logos, and not the event
        title while it is drawn with the master's title artwork."""
        kinds = {n["node_id"]: n.get("structural_class") for n in (self.chain.current or {}).get("nodes", [])}
        artwork = bool(self.style_kit.get("wordmark"))
        merged = set((self.merge or {}).get("fields", ()))      # filled from the CSV, per row
        return {k: v for k, v in self.content().items()
                if kinds.get(k) in ("text_node", "repeating_group") and not (artwork and "Event_Title" in k)
                and k not in merged}

    def text_limits(self) -> dict:
        """node id → max characters, from the format's content schema (p.44)."""
        return {k: p["maxLength"] for k, p in content_schema(self.payload_meta)["properties"].items()
                if "maxLength" in p}

    @_timed_event
    def set_typography(self, typography: dict) -> dict:
        """Re-validates and applies new administrative typography (the
        layout is unchanged; the canvas re-renders)."""
        proposed = dict(self.typography)
        proposed.update({k: v for k, v in typography.items() if v is not None})
        check = validate_typography(proposed, self.canvas_w, self.canvas_h)
        if not check["valid"]:
            raise ValueError("Schema validation rejected the typography:\n  - " + "\n  - ".join(check["errors"]))
        self._mark()
        self.typography = proposed
        current = self.chain.current
        state = self.chain.append("Typography", {"type": "typography", "typography": dict(proposed),
                                                 "schema_validation": "passed"},
                                  current["nodes"], fitness=current.get("fitness"),
                                  candidate_id=current.get("candidate_id"),
                                  variation=current.get("variation"))
        self.render(current["nodes"], self.rendered_path, current.get("variation"))
        self.chain.save(self.chain_path)
        return state

    STYLE_KEYS = ("fill", "bold", "italic", "align", "opacity", "flip", "image", "font", "weight")

    @_timed_event
    def set_style(self, node_id: str, changes: dict) -> dict:
        """Applies the designer's style to one element (Step 2's Style tools):
        a text colour (#RRGGBB), bold, italic, alignment (left, center,
        right); for a picture, a replacement image file, a horizontal flip,
        an opacity (0.1-1). A value of None removes that setting. The layout
        isn't re-solved; the canvas re-renders, and the change is one state
        in the chain (notes §3.53)."""
        if node_id not in {n["node_id"] for n in self.chain.current["nodes"]}:
            raise KeyError(f"No node '{node_id}' on the canvas")
        before = dict(self.styles.get(node_id, {}))
        after = dict(before)
        for key, value in changes.items():
            if key not in self.STYLE_KEYS:
                raise ValueError(f"Unknown style '{key}'")
            if value is None:
                after.pop(key, None)
            elif key == "fill" and not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(value)):
                raise ValueError(f"'{value}' is not a #RRGGBB colour")
            elif key == "align" and value not in ("left", "center", "right"):
                raise ValueError("Alignment is left, center or right")
            elif key == "opacity" and not 0.1 <= float(value) <= 1.0:
                raise ValueError("Opacity is between 0.1 and 1")
            elif key == "image" and not os.path.exists(str(value)):
                raise ValueError(f"No image at '{value}'")
            elif key == "font" and not (isinstance(value, str) and 0 < len(value) <= 200):
                raise ValueError("A font is a family name of 1 to 200 characters")
            elif key == "weight" and int(value) not in FONT_WEIGHTS:
                raise ValueError(f"Font weight {value} isn't one of {FONT_WEIGHTS}")
            else:
                after[key] = float(value) if key == "opacity" else int(value) if key == "weight" else bool(
                    value) if key in ("bold", "italic", "flip") else value
        if after == before:
            raise ValueError("The style is unchanged.")
        self._mark()
        styles = copy.deepcopy(self.styles)
        if after:
            styles[node_id] = after
        else:
            styles.pop(node_id, None)
        self.styles = styles
        current = self.chain.current
        state = self.chain.append(f"Style [{node_id}]",
                                  {"type": "style", "node_id": node_id, "before": before, "after": after,
                                   "summary": f"Styled {node_id}" if after else f"Reset the style of {node_id}"},
                                  current["nodes"], fitness=current.get("fitness"),
                                  candidate_id=current.get("candidate_id"), variation=current.get("variation"),
                                  styles=copy.deepcopy(styles))
        self.render(current["nodes"], self.rendered_path, current.get("variation"))
        self.chain.save(self.chain_path)
        return state

    # -- the designer's own elements (notes §3.56) ---------------------------

    def _elements(self) -> dict:
        return {"added": copy.deepcopy(self.added), "removed": list(self.removed)}

    @_timed_event
    def add_element(self, kind: str, value: str) -> dict:
        """Adds an element to the layout: kind "text" (value: its words)
        joins the stack after the format's own elements, Soft, so the solver
        places it and the others re-flow; kind "picture" (value: an image
        file) floats like a motif, in the largest empty gap. Either can then
        be moved, resized, styled or deleted."""
        if kind not in ("text", "picture"):
            raise ValueError("An added element is text or a picture")
        if kind == "text" and not 0 < len(value.strip()) <= 120:
            raise ValueError("Added text is 1 to 120 characters")
        if kind == "picture" and not os.path.exists(value):
            raise ValueError(f"No image at '{value}'")
        n = 1 + sum(1 for k in self.added if k.startswith(f"Added_{kind.title()}_"))
        nid = f"Added_{kind.title()}_{n}"
        W, H = self.canvas_w, self.canvas_h
        current = self.chain.current
        if kind == "text":
            node = {"node_id": nid, "semantic_category": "added", "structural_class": "text_node",
                    "spatial_hierarchy": 50 + len(self.added), "bbox": [W * 0.2, H * 0.5, W * 0.6, H * 0.05],
                    "constraint_type": "Soft"}
        else:
            # A picture floats like a motif, outside the solver, in the
            # layout's largest empty gap (else small, top right)
            with Image.open(value) as im:
                aspect = im.width / max(1, im.height)
            boxes = sorted((n["bbox"] for n in current["nodes"] if n.get("structural_class") != "decor"),
                           key=lambda b: b[1])
            gaps = [(a[1] + a[3], b[1]) for a, b in zip(boxes, boxes[1:]) if b[1] - (a[1] + a[3]) >= 0.06 * H]
            if gaps:
                top, bottom = max(gaps, key=lambda g: g[1] - g[0])
                h = min((bottom - top) * 0.8, W * 0.5 / aspect)
                box = [(W - h * aspect) / 2.0, top + ((bottom - top) - h) / 2.0, h * aspect, h]
            else:
                w = min(W, H) * 0.14 * max(1.0, aspect)
                box = [W - w - 0.06 * W, 0.06 * H, w, w / aspect]
            node = {"node_id": nid, "semantic_category": "added", "structural_class": "decor", "motif_path": value,
                    "spatial_hierarchy": 200 + len(self.added), "bbox": [round(v, 2) for v in box],
                    "constraint_type": "Soft"}
        variation = current.get("variation") or dict(variations_for(self.domain)[0])
        self._mark()
        self.added = dict(self.added, **{nid: node})
        extra = {"elements": self._elements()}
        if kind == "text":
            self.content_data = dict(self.content(), **{nid: value.strip()})
            extra["content"] = dict(self.content_data)
            resolved = self._resolve(current["nodes"] + [node], variation)
        else:
            resolved = copy.deepcopy(current["nodes"]) + [node]
        state = self.chain.append(f"Added [{nid}]", {"type": "add", "node_id": nid, "kind": kind,
                                                     "summary": f"Added {nid}"},
                                  resolved, fitness=self._fitness(resolved, variation),
                                  candidate_id=current.get("candidate_id"), variation=variation, **extra)
        self.render(resolved, self.rendered_path, variation)
        self.chain.save(self.chain_path)
        return state

    @_timed_event
    def remove_element(self, node_id: str) -> dict:
        """Deletes an element from the layout; the others re-flow. A
        format's own element is no longer asked for (F1 leaves it out);
        undo or the State Timeline brings it back."""
        current = self.chain.current
        if node_id not in {n["node_id"] for n in current["nodes"]}:
            raise KeyError(f"No node '{node_id}' on the canvas")
        if sum(1 for n in current["nodes"] if n.get("structural_class") != "decor") <= 1 \
                and not node_id.startswith("decor_"):
            raise ValueError("A layout keeps at least one element")
        variation = current.get("variation") or dict(variations_for(self.domain)[0])
        self._mark()
        self.removed = list(self.removed) + [node_id]
        target = next(n for n in current["nodes"] if n["node_id"] == node_id)
        rest = [n for n in current["nodes"] if n["node_id"] != node_id]
        resolved = rest if target.get("structural_class") == "decor" else self._resolve(rest, variation)
        state = self.chain.append(f"Removed [{node_id}]", {"type": "remove", "node_id": node_id,
                                                           "summary": f"Removed {node_id}"},
                                  resolved, fitness=self._fitness(resolved, variation),
                                  candidate_id=current.get("candidate_id"), variation=variation,
                                  elements=self._elements())
        self.render(resolved, self.rendered_path, variation)
        self.chain.save(self.chain_path)
        return state

    # -- reporting --------------------------------------------------------

    def _print_summary(self, winner: dict) -> None:
        total = sum(self.timings.values())
        _print_header("Pipeline Complete — Timing Summary")
        print(f"\n  {'Stage':<42} {'Time (ms)':>10}")
        print(f"  {'-'*42} {'-'*10}")
        for key, label in STAGE_LABELS.items():
            t = self.timings.get(key, 0.0)
            skipped = "  (skipped)" if t == 0.0 else ""
            print(f"  {label:<42} {t*1000:>10.1f}{skipped}")
        print(f"  {'─'*42} {'─'*10}")
        print(f"  {'TOTAL END-TO-END':<42} {total*1000:>10.1f}")
        print()
        print(f"  Winner   : {winner['candidate_id']} — {winner['label']} (C_total = {winner['c_total']:.4f})")
        print(f"  Output   : {self.rendered_path}")
        print()

    def summary(self) -> dict:
        detected_path = None
        if self.detected_nodes is not None:
            os.makedirs(self.output_dir, exist_ok=True)
            detected_path = os.path.join(self.output_dir, f"ThemeSync_{self.stem}_detected_master_layout.json")
            with open(detected_path, "w") as f:
                json.dump(self.detected_nodes, f, indent=2)
        total = sum(self.timings.values())
        winner = self.candidates[0]
        return {
            "timings_ms":     {k: round(v * 1000, 2) for k, v in self.timings.items()},
            "total_ms":       round(total * 1000, 2),
            "winner":         {k: v for k, v in winner.items() if k != "saliency_map"},
            "candidates":     [{k: v for k, v in c.items() if k != "saliency_map"} for c in self.candidates],
            "rendered_path":  self.rendered_path,
            "condition":      self.condition,
            "master_structure": self.structure,
            "master_composition": self.composition,
            "preferred_archetype": self.preferred_archetype,
            "color_centroids": self.color_centroids,
            "saliency_weight": self.saliency_weight,
            "palette":         self.palette,
            "style_kit":       self.style_kit,
            "typography":      dict(self.typography),
            "schema_validation": self.validation,
            "state_chain_path": self.chain_path,
            "detected_master_layout_nodes": self.detected_nodes,
            "detected_master_layout_path":  detected_path,
            "logo_paths":      self.logos["row"],
            "logo_source":     self.logos["source"],
        }


# ---------------------------------------------------------------------------
# One-shot entry point
# ---------------------------------------------------------------------------

def run_pipeline(
    payload_path: str,
    template_image: str = None,
    content_data_path: str = None,
    canvas_w: int = None,
    canvas_h: int = None,
    population: int = 6,
    use_gnn: bool = True,
    weights_path: str = DEFAULT_WEIGHTS,
    yolo_weights_path: str = DEFAULT_YOLO_WEIGHTS,
    output_dir: str = "data/rendered/",
    font_family: str = None,
    logo_images: list = None,
    typography: dict = None,
    use_wordmark: bool = True,
    use_structure: bool = None,
    use_motifs: bool = True,
):
    """Runs Stages 0-6 once and returns the session summary (see
    OrchestrationSession.summary). use_motifs=False leaves the master's
    motifs out (a per-poster human-in-the-loop choice, e.g. a stamp with
    words that Stage 0c can't tell from decoration)."""
    if not os.path.exists(payload_path):
        print(f"ERROR: Payload not found at '{payload_path}'")
        sys.exit(1)
    session = OrchestrationSession(
        payload_path, template_image=template_image, content_data=content_data_path,
        typography=typography, use_gnn=use_gnn, weights_path=weights_path,
        yolo_weights_path=yolo_weights_path, output_dir=output_dir, logo_images=logo_images,
        population=population, canvas_w=canvas_w, canvas_h=canvas_h, font_family=font_family,
        use_wordmark=use_wordmark, use_structure=use_structure,
        motif_paths=None if use_motifs else [],
    )
    return session.run()


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
             "If provided, colours, saliency and stylistic markers are "
             "extracted at runtime (K-Means LAB + SIFT + Stage 0c).",
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
        "--population", type=int, default=6,
        help="Number of metaheuristic candidates to generate (default: 6, the full set)",
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
             "Parsing. Defaults to the newest checkpoint in the repo root: "
             "themesync_yolo_v5.pt (200-image re-annotation), else v4, v3, v2, "
             "v1. Stage 0b is skipped gracefully if none exists.",
    )
    parser.add_argument(
        "--logo_image", type=str, nargs="+", default=None,
        help="Path(s) to organisation logo file(s), PNG with transparency "
             "preferred. The first is used where a format has one logo slot "
             "(certificate); all form the logo row where it has several (event "
             "ID). Overrides the logos cropped from the master layout by "
             "Stage 0b; if neither is available a drawn badge is used.",
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
    parser.add_argument("--font_weight", type=int, default=None,
                        help="Heading font weight, 100-900 (default 700)")
    parser.add_argument("--base_size", type=float, default=None,
                        help="Baseline type size in px the type scale is built on (default 48)")
    parser.add_argument("--no_wordmark", action="store_true",
                        help="Always type the event title instead of using the master's title artwork")

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
        logo_images=args.logo_image,
        typography={"weight": args.font_weight, "base_size": args.base_size},
        use_wordmark=not args.no_wordmark,
    )


if __name__ == "__main__":
    main()
