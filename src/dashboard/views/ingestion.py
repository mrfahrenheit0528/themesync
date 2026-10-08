"""
ThemeSync — Perceptual Ingestion & Initialization Dashboard (Figure 2)
=======================================================================
Chapter 3, pp. 50-51. The central viewport shows the uploaded master
template; the right-hand panel exposes the "Hybrid Visual DNA" in its two
parts and the target set-up, laid out as a bento grid of cards so the whole
workspace fits beside the master:

  Visual DNA — autonomous extraction
    K-Means colour centroids (Stage 0), SIFT/SURF keypoints (saliency,
    logo detected, affine scaling), the relational node graph YOLO parsed
    (Stage 0b), and the stylistic markers Stage 0c cut from the master
    (text-free background, motifs, title artwork) — each pick reviewable.
  Visual DNA — user injected
    Organisation logos, and the administrative typography (font family,
    weight, baseline size), validated against its JSON Schema before
    orchestration may start (p.44).
  Target initialization
    Target format, its structural fields, the content payload (validated
    against the format's schema), GNN-guided or baseline, and "Initialize
    Orchestration", which runs Stages 1-6 and moves on to Step 2, the
    Figure 3 workspace.

This is Step 1 of the dashboard's workflow; Steps 2 and 3 stay disabled
until a layout is initialized.
"""

import glob
import html
import json
import os
import sys
import time

import streamlit as st
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import components as ui                                              # noqa: E402
import pipeline                                                      # noqa: E402
from aesthetic_renderer import DEFAULT_TYPOGRAPHY, _palette_from_centroids  # noqa: E402
from schema_validation import FONT_WEIGHTS, validate_content, validate_typography  # noqa: E402
from stylistic_markers import build_style_kit, cover                 # noqa: E402
from template_ingestor import TemplateIngestor                       # noqa: E402

_ROOT = ui.ROOT
DNA_DIR = os.path.join(ui.SESSIONS_DIR, "visual_dna")

# Explicit domain -> sample content-data mapping (data/raw/).
_CONTENT_DATA_BY_DOMAIN = {
    "academic_certificate": os.path.join(_ROOT, "data", "raw", "sample_content.json"),
    "identification_card":  os.path.join(_ROOT, "data", "raw", "sample_content_id.json"),
}

FONT_OPTIONS = {
    "Montserrat (default)": DEFAULT_TYPOGRAPHY["family"],
    "Lato":                 "Lato, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "Open Sans":            "'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "Playfair Display":     "'Playfair Display', Georgia, 'Times New Roman', serif",
    "Merriweather":         "Merriweather, Georgia, serif",
    "Times New Roman":      "'Times New Roman', Times, serif",
}
WEIGHT_NAMES = {100: "Thin", 200: "Extra Light", 300: "Light", 400: "Regular", 500: "Medium",
                600: "Semibold", 700: "Bold", 800: "Extra Bold", 900: "Black"}
CATEGORY_COLOURS = {"logo": (0, 200, 90), "text": (40, 120, 255), "underlay": (255, 170, 0),
                    "embellishment": (220, 60, 220), "illustration": (0, 190, 200)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _discover_target_formats() -> dict:
    """data/raw/*_payload.json → Figure 2's "Select Target Format" options,
    read from each payload's own domain_context and target_aspect_ratio."""
    formats = {}
    for path in sorted(glob.glob(os.path.join(_ROOT, "data", "raw", "*_payload.json"))):
        try:
            with open(path) as f:
                meta = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        domain = meta.get("domain_context", os.path.basename(path))
        ratio = meta.get("target_aspect_ratio", "?")
        formats[f"{domain.replace('_', ' ').title()} ({ratio})"] = {"path": path, "meta": meta}
    return formats


def _friendly(var_name: str) -> str:
    return var_name.strip("{}").replace("_", " ").title()


def _node_row(node: dict) -> str:
    """Figure 2's 'Node_01: Logo (Static)' style row for a detected node,
    with its OCR text when it has some."""
    kind = node["node_id"].split("_")[1] if node["node_id"].startswith("auto_") else node["structural_class"]
    nature = "Fluid" if node["structural_class"] == "text_node" else "Static"
    row = (f'<div class="bn-node"><b>{html.escape(node["node_id"])}</b><span>{kind.title()} ({nature})</span>'
           f'<i>{node.get("detection_confidence", 0.0):.2f}</i></div>')
    if node["structural_class"] == "text_node" and node.get("ocr_text"):
        row += f'<div class="bn-ocr">“{html.escape(node["ocr_text"][:60])}”</div>'
    return row


@st.cache_data(show_spinner="Stage 0: K-Means palette and SIFT saliency...")
def _ingest(path: str, mtime: float) -> dict:
    return TemplateIngestor(n_colors=3).ingest(path)


@st.cache_data(show_spinner="Stage 0c: text-free background, motifs, title artwork...")
def _style_kit(path: str, mtime: float, nodes_json: str) -> dict:
    nodes = json.loads(nodes_json)
    stem = os.path.splitext(os.path.basename(path))[0]
    return build_style_kit(path, nodes, os.path.join(DNA_DIR, stem), stem,
                           logo_boxes=[n["bbox"] for n in nodes if n.get("semantic_category") == "logo"])


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

ui.enter_step(1, "New design · upload a master layout, review its Visual DNA, set up the target")

# A bento layout on one workspace (p.51): the master template's viewport on
# the left, kept in view; the right-hand panel's diagnostics and controls as
# a grid of cards beside it. The cards are laid out first and filled in the
# order the values depend on each other.
master_col, grid_col = st.columns([0.95, 1.65], gap="medium")
dna = None
master_path = None
typography = dict(DEFAULT_TYPOGRAPHY)
logo_images, motif_paths, use_wordmark, wordmark_path = None, None, True, None


def _empty(text: str = "Waiting for the master layout.") -> None:
    st.markdown(f'<div class="bn-empty">{html.escape(text)}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# LEFT — the master template (the central viewport)
# ---------------------------------------------------------------------------
with master_col, st.container(border=True, key="card_master"):
    st.markdown(":material/image: **Master Template**")
    uploaded = st.file_uploader("Upload a master layout (event poster, banner, letterhead...)",
                                type=["png", "jpg", "jpeg", "bmp", "webp"])
    if uploaded is not None:
        st.session_state["master_path"] = ui.save_upload(uploaded)
    master_path = st.session_state.get("master_path")

    if master_path and os.path.exists(master_path):
        extracted = st.session_state.get("dna_for") == master_path
        if st.button("Extract Visual DNA", icon=":material/biotech:", type="primary", disabled=extracted,
                     width="stretch",
                     help="Stage 0 (K-Means + SIFT), Stage 0b (YOLOv8 + OCR) and Stage 0c "
                          "(stylistic markers) on the uploaded image."):
            st.session_state["dna_for"] = master_path
            st.rerun()
        if extracted:
            mtime = os.path.getmtime(master_path)
            ingestion = _ingest(master_path, mtime)
            try:
                nodes = ui.detect(master_path, mtime)
                yolo_error = None
            except Exception as e:  # surfaced in the UI, not a hard crash
                nodes, yolo_error = [], str(e)
            kit = _style_kit(master_path, mtime, json.dumps(nodes))
            dna = {"ingestion": ingestion, "nodes": nodes, "kit": kit, "yolo_error": yolo_error,
                   "stem": os.path.splitext(os.path.basename(master_path))[0]}

        show_nodes = st.toggle("Show Stage 0b detections", value=False, disabled=dna is None)
        if dna and show_nodes:
            st.image(ui.annotate(master_path, [(n["semantic_category"][:4], n["bbox"],
                                                CATEGORY_COLOURS.get(n["semantic_category"], (255, 255, 255)))
                                               for n in dna["nodes"]]), width="stretch")
            st.caption("Green logo · blue text · orange underlay · magenta embellishment"
                       + (" · cyan illustration." if any(n["semantic_category"] == "illustration"
                                                         for n in dna["nodes"]) else "."))
        else:
            st.image(master_path, width="stretch")
    else:
        st.caption("Phase 1 · Perceptual Ingestion & Feature Extraction (Figure 2). The master layout "
                   "drives every card on the right: its colours, style, elements and logos.")

# ---------------------------------------------------------------------------
# RIGHT — the Hybrid Visual DNA and the target set-up, as cards
# ---------------------------------------------------------------------------
with grid_col, st.container(key="bento_grid"):
    st.markdown('<div class="bn-group">Visual DNA · autonomous extraction</div>', unsafe_allow_html=True)
    a1, a2 = st.columns([1.1, 1], gap="small")
    card_colours = a1.container(border=True, key="card_colours")
    card_sift = a2.container(border=True, key="card_sift")
    b1, b2 = st.columns([1, 1.1], gap="small")
    card_graph = b1.container(border=True, key="card_graph")
    card_markers = b2.container(border=True, key="card_markers")
    st.markdown('<div class="bn-group">Visual DNA · user injected</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.15, 1], gap="small")
    card_logos = c1.container(border=True, key="card_logos")
    card_type = c2.container(border=True, key="card_type")
    st.markdown('<div class="bn-group">Target initialization</div>', unsafe_allow_html=True)
    d1, d2 = st.columns([1, 1.15], gap="small")
    card_target = d1.container(border=True, key="card_target")
    card_content = d2.container(border=True, key="card_content")

ing = dna["ingestion"] if dna else None
kit = dna["kit"] if dna else None

with card_colours:
    st.markdown(":material/palette: **K-Means Color Centroids**")
    if not dna:
        _empty()
    else:
        palette = _palette_from_centroids(ing["color_centroids"])
        st.markdown('<div class="bn-swatches">' + "".join(
            f'<div class="bn-swatch"><span style="background:{h}"></span><small>Centroid {i + 1}</small>'
            f'<code>{h}</code></div>' for i, h in enumerate(ing["palette_hex"])) + "</div>",
            unsafe_allow_html=True)
        st.caption(f"Roles the renderer assigns: primary `{palette['primary']}` · accent "
                   f"`{palette['accent']}` · certificate panel `{palette['panel']}`.")

with card_sift:
    st.markdown(":material/scatter_plot: **SIFT/SURF Keypoints**")
    if not dna:
        _empty()
    else:
        logos_found = [n for n in dna["nodes"] if n.get("semantic_category") == "logo"]
        stats = [("Saliency weight", f"{ing['saliency_weight']:.4f}"),
                 ("Logo detected", "Yes" if logos_found else "No"),
                 ("Native size", f"{ing['image_wh'][0]}×{ing['image_wh'][1]}")]
        st.markdown('<div class="bn-stats">' + "".join(
            f'<div class="bn-stat"><small>{k}</small><b>{v}</b></div>' for k, v in stats) + "</div>",
            unsafe_allow_html=True)
        st.caption("The saliency weight is the master's SIFT keypoint density. Its map is what the "
                   "legibility penalty (Formula 3.15) checks text against.")

with card_graph:
    st.markdown(":material/account_tree: **Relational Node Graph**")
    if not dna:
        _empty()
    elif dna["yolo_error"]:
        st.warning(f"Stage 0b unavailable — {dna['yolo_error']}")
    elif not dna["nodes"]:
        st.caption("No nodes detected above the confidence threshold.")
    else:
        counts = {}
        for n in dna["nodes"]:
            counts[n["semantic_category"]] = counts.get(n["semantic_category"], 0) + 1
        st.markdown(f'<div class="bn-big">{len(dna["nodes"])}<small> nodes parsed (Stage 0b)</small></div>'
                    '<div class="bn-chips">' + "".join(f'<span class="bn-chip">{c} <i>{k}</i></span>'
                                                       for c, k in sorted(counts.items())) + "</div>",
                    unsafe_allow_html=True)
        with st.container(height=250, border=False, key="node_list"):
            st.markdown('<div class="bn-nodes">' + "".join(_node_row(n) for n in dna["nodes"]) + "</div>",
                        unsafe_allow_html=True)

with card_markers:
    st.markdown(":material/auto_awesome_mosaic: **Stylistic Markers (Stage 0c)**")
    if not dna:
        _empty()
        motif_paths = []
    else:
        images, captions = [], []
        with Image.open(kit["background"]) as bg:
            images.append(cover(bg.convert("RGB"), 240, 150))
            captions.append("Text-free background")
        if kit["wordmark"]:
            with Image.open(kit["wordmark"]["path"]) as wm:
                images.append(ui.tile(wm, 150))
                captions.append("Title artwork")
        st.image(images, caption=captions, width=150)
        if kit["wordmark"]:
            use_wordmark = st.checkbox("Use the event's title artwork on the event ID", value=True)
        else:
            use_wordmark = False
            st.caption("No title artwork separated cleanly — the event title is typed.")
        with st.popover("Upload title artwork", icon=":material/upload:", width="stretch"):
            up = st.file_uploader("Title artwork (transparent PNG)", type=["png", "webp"], key="wordmark_upload")
        if up:
            wordmark_path = ui.save_upload(up, prefix="wordmark_")
            use_wordmark = True
        if kit["motifs"]:
            tiles = []
            for m in kit["motifs"]:
                with Image.open(m["path"]) as im:
                    tiles.append(ui.tile(im, 90))
            st.image(tiles, caption=[f"M{i + 1}" for i in range(len(tiles))], width=62)
            picked = st.pills("Motifs that travel (the master's own decorations)", list(range(len(kit["motifs"]))),
                              selection_mode="multi", default=list(range(len(kit["motifs"]))),
                              format_func=lambda i: f"M{i + 1} · {kit['motifs'][i]['confidence']:.2f}",
                              key=f"motifs_{dna['stem']}")
            motif_paths = [kit["motifs"][i]["path"] for i in picked or []]
        else:
            motif_paths = []
            st.caption("No motifs separated cleanly from this master.")

with card_logos:
    st.markdown(":material/verified: **Organisation Logos**")
    if not dna:
        _empty()
    else:
        cands = ui.logo_detections(master_path, dna["nodes"])
        if cands:
            st.image([ui.tile(c["image"], 100) for c in cands], caption=[c["label"] for c in cands], width=72)
            picked = st.pills("Logos to use", list(range(len(cands))), selection_mode="multi",
                              default=[i for i, c in enumerate(cands) if c["auto"]],
                              format_func=lambda i: f"{cands[i]['label']} · {cands[i]['conf']:.2f}",
                              key=f"logos_{dna['stem']}")
            ticked = [cands[i] for i in picked or []]
        else:
            ticked = []
        with st.popover("Add logos", icon=":material/add_photo_alternate:", width="stretch"):
            extra = st.file_uploader("Logos Stage 0b missed (transparent PNGs look best)",
                                     type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True,
                                     key="logo_upload")
            if cands:
                st.image(ui.annotate(master_path, [(c["label"], c["bbox"], ui.GREEN if c in ticked else ui.RED)
                                                   for c in cands]), caption="Detections: green = picked",
                         width="stretch")
        uploads = [ui.save_upload(f, prefix="logo_") for f in extra or []]
        auto_ids = {c["id"] for c in cands if c["auto"]}
        if not cands and not uploads:
            st.caption("No logos detected — a drawn badge stands in unless you upload one.")
        elif {c["id"] for c in ticked} == auto_ids and not uploads:
            st.caption("✓ ThemeSync's automatic logo pick.")
        else:
            os.makedirs(os.path.join(ui.UPLOAD_DIR, "logos"), exist_ok=True)
            logo_images = []
            for c in sorted(ticked, key=lambda c: (not c["primary"], c["x"])):
                path = os.path.join(ui.UPLOAD_DIR, "logos", f"{dna['stem']}_{c['id']}.png")
                c["image"].save(path)
                logo_images.append(path)
            logo_images += uploads
            logo_images = logo_images or None
            st.caption("Manual logo pick — the first is the certificate seal.")

with card_type:
    st.markdown(":material/text_fields: **Administrative Typography**")
    font_label = st.selectbox("Primary Font", list(FONT_OPTIONS.keys()), disabled=not dna)
    weight = st.selectbox("Font Weight", FONT_WEIGHTS, index=FONT_WEIGHTS.index(700), disabled=not dna,
                          format_func=lambda w: f"{w} — {WEIGHT_NAMES[w]}")
    base = st.number_input("Base Size (px)", min_value=1.0, max_value=400.0, value=48.0, step=1.0,
                           disabled=not dna,
                           help="The certificate title's size; the whole type scale is built on it.")
    if dna:
        typography = {"family": FONT_OPTIONS[font_label], "weight": int(weight), "base_size": float(base)}

with card_target:
    st.markdown(":material/flag: **Target Format**")
    formats = _discover_target_formats()
    if not formats:
        st.error("No *_payload.json files found under data/raw/.")
        st.stop()
    target_label = st.selectbox("Select Target Format", list(formats.keys()))
    target = formats[target_label]
    schema = target["meta"].get("variable_schema", {})
    canvas_w, canvas_h = pipeline._derive_canvas(target["meta"], None, None)
    st.caption(f"{canvas_w}×{canvas_h} px · required structural fields:")
    st.markdown('<div class="bn-chips">' + "".join(
        f'<span class="bn-chip">{props.get("instantiation_count", 1)}× {_friendly(var)} '
        f'<i>{props.get("structural_class")}</i></span>' for var, props in schema.items()) + "</div>",
        unsafe_allow_html=True)

# Content payload
domain = target["meta"].get("domain_context")
sample_path = _CONTENT_DATA_BY_DOMAIN.get(domain)
sample = json.load(open(sample_path)) if sample_path and os.path.exists(sample_path) else {}
content = {}
with card_content:
    st.markdown(":material/edit_note: **Content Payload**")
    with st.popover("Load a JSON payload", icon=":material/upload_file:", width="stretch"):
        payload_upload = st.file_uploader("Content payload (JSON); it fills the fields below",
                                          type=["json"], key=f"payload_{domain}")
    if payload_upload is not None and st.session_state.get("payload_applied") != payload_upload.file_id:
        # applied once per file, so edits made afterwards aren't overwritten on rerun
        try:
            loaded = json.loads(payload_upload.getvalue().decode("utf-8"))
            for key, value in loaded.items():
                st.session_state[f"content_{domain}_{key}"] = str(value)
            st.session_state["payload_applied"] = payload_upload.file_id
        except (ValueError, UnicodeDecodeError, AttributeError) as e:
            st.error(f"Could not read that JSON: {e}")
    with st.container(height=380, border=False, key="content_fields"):
        for var, props in schema.items():
            count = props.get("instantiation_count", 1)
            keys = [f"{var}_{i}" for i in range(count)] if count > 1 else [var]
            for key in keys:
                default = str(sample.get(key, ""))
                wkey = f"content_{domain}_{key}"
                st.session_state.setdefault(wkey, default)
                if props.get("structural_class") == "image_node":
                    content[key] = st.session_state[wkey]      # alt text only; the image is the logo
                    continue
                label = _friendly(key) if count == 1 else f"{_friendly(var)} {int(key.rsplit('_', 1)[1]) + 1}"
                if "\n" in default or props.get("max_characters", 0) > 80 or props.get("structural_class") == "repeating_group":
                    content[key] = st.text_area(label, key=wkey, height=70,
                                                max_chars=props.get("max_characters"))
                else:
                    content[key] = st.text_input(label, key=wkey, max_chars=props.get("max_characters"))

# Pre-orchestration schema validation (Chapter 3, p.44), then initialize
with card_target:
    checks = {"typography": validate_typography(typography, canvas_w, canvas_h),
              "content": validate_content(content, target["meta"])}
    problems = [f"{name}: {e}" for name, v in checks.items() for e in v["errors"]]
    if problems:
        st.error("Schema validation — initialization would be rejected:\n\n" + "\n".join(f"- {p}" for p in problems))
    else:
        st.success("Schema validation passed: typography and content payload conform.",
                   icon=":material/task_alt:")

    use_gnn = st.toggle("GNN-guided layout (off: no-GNN baseline)", value=True)
    ready = dna is not None and not problems
    if dna is None:
        st.caption("Extract the Visual DNA (left) before initializing orchestration.")
    elif st.session_state.get("orch") is not None:
        st.caption("Initializing starts a new layout; the one you were editing stays saved in its "
                   "session folder.")

    if st.button("Initialize Orchestration", icon=":material/play_arrow:", type="primary",
                 disabled=not ready, width="stretch"):
        out_dir = os.path.join(ui.SESSIONS_DIR, f"{time.strftime('%Y%m%d_%H%M%S')}_{dna['stem']}_{domain}")
        session = pipeline.OrchestrationSession(
            target["path"], template_image=master_path, content_data=content, typography=typography,
            use_gnn=use_gnn, output_dir=out_dir, logo_images=logo_images, use_wordmark=use_wordmark,
            wordmark_path=wordmark_path, motif_paths=motif_paths, detected_nodes=dna["nodes"],
        )
        try:
            with st.spinner("Running Stages 1-6 (instantiation → GNN → CSP → ranking → render → state chain)..."):
                session.run()
        except ValueError as e:
            st.error(str(e))
        else:
            st.session_state["orch"] = session
            st.session_state["orch_master"] = master_path
            ui.go_to_step(2)
