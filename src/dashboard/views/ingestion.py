"""
ThemeSync — Perceptual Ingestion & Initialization Dashboard (Figure 2)
=======================================================================
Chapter 3, pp. 50-51. The central viewport shows the uploaded master
template; the right-hand panel exposes the "Hybrid Visual DNA" in its two
parts and the target set-up:

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
    Orchestration", which runs Stages 1-6 and opens the Figure 3 workspace.
"""

import glob
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


def _node_label(node: dict) -> str:
    """Figure 2's 'Node_01: Logo (Static)' style line for a detected node."""
    kind = node["node_id"].split("_")[1] if node["node_id"].startswith("auto_") else node["structural_class"]
    nature = "Fluid" if node["structural_class"] == "text_node" else "Static"
    return f"**{node['node_id']}** — {kind.title()} ({nature}) · conf={node.get('detection_confidence', 0.0):.2f}"


@st.cache_data(show_spinner="Stage 0: K-Means palette and SIFT saliency...")
def _ingest(path: str, mtime: float) -> dict:
    return TemplateIngestor(n_colors=3).ingest(path)


@st.cache_data(show_spinner="Stage 0c: text-free background, motifs, title artwork...")
def _style_kit(path: str, mtime: float, nodes_json: str) -> dict:
    nodes = json.loads(nodes_json)
    stem = os.path.splitext(os.path.basename(path))[0]
    return build_style_kit(path, nodes, os.path.join(DNA_DIR, stem), stem,
                           logo_boxes=[n["bbox"] for n in nodes if n.get("semantic_category") == "logo"])


def _swatch(hexcode: str, label: str) -> None:
    st.markdown(f'<div style="background:{hexcode};height:34px;border-radius:6px;'
                f'border:1px solid rgba(0,0,0,.15);"></div>', unsafe_allow_html=True)
    st.caption(f"{label}\n\n`{hexcode}`")


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title("ThemeSync")
st.caption("Phase 1 · Perceptual Ingestion & Feature Extraction — Master Template Dashboard (Figure 2)")

col_left, col_right = st.columns([1.3, 1], gap="large")
dna = None

# ---------------------------------------------------------------------------
# LEFT — Master Template Preview
# ---------------------------------------------------------------------------
with col_left:
    st.subheader("Master Template Preview")
    uploaded = st.file_uploader("Upload a master layout (event poster, banner, letterhead...)",
                                type=["png", "jpg", "jpeg", "bmp", "webp"])
    if uploaded is not None:
        st.session_state["master_path"] = ui.save_upload(uploaded)
    master_path = st.session_state.get("master_path")

    if master_path and os.path.exists(master_path):
        extracted = st.session_state.get("dna_for") == master_path
        if st.button("🔍 Extract Visual DNA", type="primary", disabled=extracted,
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
        st.info("Upload an image to begin — it drives everything in the panel on the right.")

# ---------------------------------------------------------------------------
# RIGHT — Visual DNA + Target Initialization
# ---------------------------------------------------------------------------
with col_right:
    st.subheader("Visual DNA")
    typography = dict(DEFAULT_TYPOGRAPHY)
    logo_images, motif_paths, use_wordmark, wordmark_path = None, None, True, None

    if not dna:
        st.info("Waiting on Visual DNA extraction (left panel).")
    else:
        ing, kit = dna["ingestion"], dna["kit"]

        st.markdown("**[-] K-Means Color Centroids**")
        palette = _palette_from_centroids(ing["color_centroids"])
        cols = st.columns(len(ing["palette_hex"]))
        for i, hexcode in enumerate(ing["palette_hex"]):
            with cols[i]:
                _swatch(hexcode, f"Centroid {i + 1}")
        st.caption(f"Roles the renderer assigns — primary `{palette['primary']}` · accent "
                   f"`{palette['accent']}` · certificate panel `{palette['panel']}`.")

        st.markdown("**[-] SIFT/SURF Keypoints**")
        logos_found = [n for n in dna["nodes"] if n.get("semantic_category") == "logo"]
        st.write(f"- Saliency weight: `{ing['saliency_weight']:.4f}`")
        st.write(f"- Logo detected: `{bool(logos_found)}`")
        st.write(f"- Native size: `{ing['image_wh'][0]}×{ing['image_wh'][1]} px`")

        st.markdown("**[-] Relational Node Graph**")
        if dna["yolo_error"]:
            st.warning(f"Stage 0b unavailable — {dna['yolo_error']}")
        elif not dna["nodes"]:
            st.caption("No nodes detected above the confidence threshold.")
        else:
            with st.expander(f"{len(dna['nodes'])} node(s) parsed from the master layout"):
                for n in dna["nodes"]:
                    st.markdown(f"- {_node_label(n)}")
                    if n["structural_class"] == "text_node" and n.get("ocr_text"):
                        st.caption(f"  ↳ OCR: “{n['ocr_text'][:60]}”")

        # Stylistic markers (Stage 0c)
        st.markdown("**[-] Stylistic Markers (Stage 0c)**")
        with Image.open(kit["background"]) as bg:
            st.image(cover(bg.convert("RGB"), 240, 150), caption="Text-free background layer",
                     width=240)
        if kit["wordmark"]:
            with Image.open(kit["wordmark"]["path"]) as wm:
                st.image(ui.tile(wm, 220), caption="Title artwork", width=220)
            use_wordmark = st.checkbox("Use the event's title artwork on the event ID", value=True)
        else:
            use_wordmark = False
            st.caption("No title artwork separated cleanly — the event title is typed.")
        up = st.file_uploader("…or upload title artwork (transparent PNG)", type=["png", "webp"],
                              key="wordmark_upload")
        if up:
            wordmark_path = ui.save_upload(up, prefix="wordmark_")
            use_wordmark = True
        if kit["motifs"]:
            st.caption("Motifs (the master's own decorations) — untick any that shouldn't travel:")
            motif_paths = []
            for start in range(0, len(kit["motifs"]), 4):
                for m, col in zip(kit["motifs"][start:start + 4], st.columns(4)):
                    with col:
                        with Image.open(m["path"]) as im:
                            st.image(ui.tile(im, 110), width="stretch")
                        if st.checkbox(f"conf {m['confidence']:.2f}", value=True, key=f"motif_{m['path']}"):
                            motif_paths.append(m["path"])
        else:
            motif_paths = []
            st.caption("No motifs separated cleanly from this master.")

        # Organisation logos
        st.markdown("**[-] User Injected — Organisation Logos**")
        cands = ui.logo_detections(master_path, dna["nodes"])
        extra = st.file_uploader("Add logos Stage 0b missed (transparent PNGs look best)",
                                 type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True,
                                 key="logo_upload")
        uploads = [ui.save_upload(f, prefix="logo_") for f in extra or []]
        ticked = []
        for start in range(0, len(cands), 4):
            for c, col in zip(cands[start:start + 4], st.columns(4)):
                with col:
                    st.image(ui.tile(c["image"], 100), width="stretch")
                    if st.checkbox(f"{c['label']} · {c['conf']:.2f}", value=c["auto"], key=f"logo_{c['id']}"):
                        ticked.append(c)
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
        with st.expander("Logo detections on the master"):
            st.image(ui.annotate(master_path, [(c["label"], c["bbox"], ui.GREEN if c in ticked else ui.RED)
                                               for c in cands]), width="stretch")

        # Administrative typography
        st.markdown("**[-] User Injected — Administrative Typography**")
        font_label = st.selectbox("Primary Font", list(FONT_OPTIONS.keys()))
        weight = st.selectbox("Font Weight", FONT_WEIGHTS, index=FONT_WEIGHTS.index(700),
                              format_func=lambda w: f"{w} — {WEIGHT_NAMES[w]}")
        base = st.number_input("Base Size (px)", min_value=1.0, max_value=400.0, value=48.0, step=1.0,
                               help="The certificate title's size; the whole type scale is built on it.")
        typography = {"family": FONT_OPTIONS[font_label], "weight": int(weight), "base_size": float(base)}

    st.markdown("---")
    st.subheader("Target Initialization")
    formats = _discover_target_formats()
    if not formats:
        st.error("No *_payload.json files found under data/raw/.")
        st.stop()
    target_label = st.selectbox("Select Target Format", list(formats.keys()))
    target = formats[target_label]
    schema = target["meta"].get("variable_schema", {})
    canvas_w, canvas_h = pipeline._derive_canvas(target["meta"], None, None)

    st.markdown("**Required structural fields**")
    for var, props in schema.items():
        st.write(f"- [■] [{props.get('instantiation_count', 1)}] {_friendly(var)}  `{props.get('structural_class')}`")

    # Content payload
    domain = target["meta"].get("domain_context")
    sample_path = _CONTENT_DATA_BY_DOMAIN.get(domain)
    sample = json.load(open(sample_path)) if sample_path and os.path.exists(sample_path) else {}
    payload_upload = st.file_uploader("Content payload (JSON) — optional; edit the fields below instead",
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
    content = {}
    with st.expander("Content payload", expanded=True):
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

    # Pre-orchestration schema validation (Chapter 3, p.44)
    checks = {"typography": validate_typography(typography, canvas_w, canvas_h),
              "content": validate_content(content, target["meta"])}
    problems = [f"{name}: {e}" for name, v in checks.items() for e in v["errors"]]
    if problems:
        st.error("Schema validation — initialization would be rejected:\n\n" + "\n".join(f"- {p}" for p in problems))
    else:
        st.success("Schema validation passed — typography and content payload conform.")

    use_gnn = st.toggle("GNN-guided layout (off: no-GNN baseline)", value=True)
    ready = dna is not None and not problems
    if dna is None:
        st.caption("Extract Visual DNA on the left before initializing orchestration.")

    if st.button("▶ Initialize Orchestration", type="primary", disabled=not ready):
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
            st.switch_page("views/orchestration.py")
