"""
ThemeSync — Perceptual Ingestion & Initialization Dashboard
==============================================================
Streamlit implementation of the Phase 1 dashboard described in the
manuscript (Chapter 3, p. 50-51, Figure 2: "Perceptual Ingestion and
Initialization Dashboard").

This is a thin UI layer over the existing, already-working backend:
  - Stage 0  (TemplateIngestor)  → K-Means LAB palette + SIFT saliency
  - Stage 0b (LayoutExtractor)   → YOLOv8 + Tesseract detected nodes
  - run_pipeline()               → full orchestration (Stages 1-6)

No new algorithms are introduced here — this only makes the already-built
pipeline reviewable and triggerable interactively, closing the gap flagged
in notes/system_development_progress.md ("no interactive UI exists").

Run:
    streamlit run src/dashboard/app.py
"""

import glob
import json
import os
import sys

import streamlit as st

# ---------------------------------------------------------------------------
# Path bootstrap — same pattern as pipeline.py
# ---------------------------------------------------------------------------
_THIS = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_THIS)
_ROOT = os.path.dirname(_SRC)

for _sub in ("models", "solvers", "renderers", "data_preprocessing"):
    _p = os.path.join(_SRC, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from template_ingestor import TemplateIngestor          # noqa: E402
from layout_extractor import LayoutExtractor             # noqa: E402
import pipeline as themesync_pipeline                    # noqa: E402

UPLOAD_DIR = os.path.join(_ROOT, "data", "raw", "dashboard_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Explicit domain -> sample content-data mapping, matching the files already
# in data/raw/ (see notes/system_development_progress.md Phase 1 table).
_CONTENT_DATA_BY_DOMAIN = {
    "academic_certificate": os.path.join(_ROOT, "data", "raw", "sample_content.json"),
    "identification_card":  os.path.join(_ROOT, "data", "raw", "sample_content_id.json"),
}

FONT_OPTIONS = {
    "Montserrat (default)": "Montserrat, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "Lato":                 "Lato, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "Open Sans":            "'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "Playfair Display":     "'Playfair Display', Georgia, 'Times New Roman', serif",
    "Merriweather":         "Merriweather, Georgia, serif",
    "Times New Roman":      "'Times New Roman', Times, serif",
}

FONT_WEIGHTS = ["300 — Light", "400 — Regular", "600 — Semibold", "700 — Bold", "900 — Black"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _discover_target_formats() -> dict:
    """
    Scans data/raw/*_payload.json for available target formats, matching
    Figure 2's "TARGET INITIALIZATION" dropdown. Reads domain_context and
    target_aspect_ratio directly from each payload rather than hardcoding,
    so a newly added payload is picked up automatically.
    """
    formats = {}
    for path in sorted(glob.glob(os.path.join(_ROOT, "data", "raw", "*_payload.json"))):
        try:
            with open(path) as f:
                meta = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        domain = meta.get("domain_context", os.path.basename(path))
        ratio = meta.get("target_aspect_ratio", "?")
        label = f"{domain.replace('_', ' ').title()} ({ratio})"
        formats[label] = {"path": path, "meta": meta}
    return formats


def _friendly_field_name(var_name: str) -> str:
    return var_name.strip("{}").replace("_", " ").title()


def _node_display_label(node: dict) -> str:
    """Maps a detected node to Figure 2's 'Node_01: Logo (Static)' style line."""
    kind = node["node_id"].split("_")[1] if node["node_id"].startswith("auto_") else node["structural_class"]
    nature = "Fluid" if node["structural_class"] == "text_node" else "Static"
    conf = node.get("detection_confidence", 0.0)
    return f"**{node['node_id']}** — {kind.title()} ({nature}) · conf={conf:.2f}"


def _save_upload(uploaded_file) -> str:
    dest = os.path.join(UPLOAD_DIR, uploaded_file.name)
    with open(dest, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return dest


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="ThemeSync // Phase 1: Perceptual Ingestion & Feature Extraction",
    layout="wide",
)

st.title("ThemeSync")
st.caption("Phase 1 · Perceptual Ingestion & Feature Extraction — Master Template Dashboard")

col_left, col_right = st.columns([1.3, 1], gap="large")

# ---------------------------------------------------------------------------
# LEFT — Master Template Preview
# ---------------------------------------------------------------------------
with col_left:
    st.subheader("Master Template Preview")
    uploaded = st.file_uploader(
        "Upload a master layout (poster, banner, letterhead...)",
        type=["png", "jpg", "jpeg", "bmp", "webp"],
    )

    if uploaded is not None:
        st.image(uploaded, use_container_width=True)

        upload_key = f"{uploaded.name}_{uploaded.size}"
        already_extracted = st.session_state.get("upload_key") == upload_key

        extract_clicked = st.button(
            "🔍 Extract Visual DNA",
            type="primary",
            disabled=already_extracted,
            help="Runs Stage 0 (K-Means + SIFT) and Stage 0b (YOLOv8 + OCR) on the uploaded image.",
        )

        if extract_clicked:
            image_path = _save_upload(uploaded)
            with st.spinner("Extracting palette, saliency, and detected nodes..."):
                ingestor = TemplateIngestor(n_colors=3)
                ingestion_result = ingestor.ingest(image_path)

                detected_nodes = []
                yolo_weights = themesync_pipeline.DEFAULT_YOLO_WEIGHTS
                yolo_error = None
                if os.path.exists(yolo_weights):
                    try:
                        extractor = LayoutExtractor(weights_path=yolo_weights)
                        detected_nodes = extractor.extract(image_path)
                    except Exception as e:  # surfaced in the UI, not a hard crash
                        yolo_error = str(e)
                else:
                    yolo_error = f"No YOLO weights found at '{yolo_weights}'."

            st.session_state["upload_key"] = upload_key
            st.session_state["image_path"] = image_path
            st.session_state["ingestion_result"] = ingestion_result
            st.session_state["detected_nodes"] = detected_nodes
            st.session_state["yolo_error"] = yolo_error
            st.session_state.pop("orchestration_result", None)
            st.rerun()

        if already_extracted:
            st.success(f"Visual DNA extracted for **{uploaded.name}**.")
    else:
        st.info("Upload an image to begin — this drives everything in the panel on the right.")

    # Orchestration output, once available
    if st.session_state.get("orchestration_result"):
        st.markdown("---")
        st.subheader("Orchestration Output")
        result = st.session_state["orchestration_result"]
        rendered_path = result["rendered_path"]
        if os.path.exists(rendered_path):
            with open(rendered_path, "r") as f:
                svg_markup = f.read()
            st.components.v1.html(svg_markup, height=520, scrolling=True)
            with open(rendered_path, "rb") as f:
                st.download_button("⬇ Download rendered SVG", f, file_name=os.path.basename(rendered_path))
        winner = result["winner"]
        st.write(
            f"**Winner candidate:** {winner['candidate_id']} "
            f"(C_total = {winner['c_total']:.4f}) · "
            f"**Total latency:** {result['total_ms']:.1f} ms"
        )
        st.caption(f"Logo source: {result.get('logo_source') or 'none found — drawn badge'}")
        with st.expander("Full timing breakdown"):
            st.json(result["timings_ms"])

# ---------------------------------------------------------------------------
# RIGHT — Visual DNA + Target Initialization
# ---------------------------------------------------------------------------
with col_right:
    st.subheader("Visual DNA")

    ingestion_result = st.session_state.get("ingestion_result")
    detected_nodes = st.session_state.get("detected_nodes")

    if not ingestion_result:
        st.info("Waiting on Visual DNA extraction (left panel).")
    else:
        st.markdown("**K-Means Color Centroids**")
        role_labels = ["Primary", "Accent", "Background"]
        swatch_cols = st.columns(len(ingestion_result["palette_hex"]))
        for i, hexcode in enumerate(ingestion_result["palette_hex"]):
            role = role_labels[i] if i < len(role_labels) else f"Color {i + 1}"
            with swatch_cols[i]:
                st.markdown(
                    f'<div style="background:{hexcode};height:40px;border-radius:6px;'
                    f'border:1px solid rgba(0,0,0,.15);"></div>',
                    unsafe_allow_html=True,
                )
                st.caption(f"{role}\n\n`{hexcode}`")

        st.markdown("**SIFT Keypoints**")
        logo_detected = any("logo" in n["node_id"] for n in (detected_nodes or []))
        st.write(f"- Saliency weight: `{ingestion_result['saliency_weight']:.4f}`")
        st.write(f"- Logo detected: `{logo_detected}`")
        st.write(f"- Native size: `{ingestion_result['image_wh'][0]}×{ingestion_result['image_wh'][1]} px`")

        st.markdown("**Relational Node Graph**")
        if st.session_state.get("yolo_error"):
            st.warning(f"Stage 0b unavailable — {st.session_state['yolo_error']}")
        elif not detected_nodes:
            st.caption("No nodes detected above the confidence threshold.")
        else:
            for n in detected_nodes:
                st.markdown(f"- {_node_display_label(n)}")
                if n["structural_class"] == "text_node" and n.get("ocr_text"):
                    st.caption(f"  ↳ OCR: “{n['ocr_text'][:60]}”")

        st.markdown("**User Injected — Administrative Typography**")
        st.caption(
            "Font family is applied to the rendered output below. Weight and "
            "base size are captured for the record but not yet wired into the "
            "renderer (Table 1's per-element sizing formulas are still the "
            "source of truth for text size)."
        )
        font_label = st.selectbox("Primary Font", list(FONT_OPTIONS.keys()))
        st.session_state["font_weight"] = st.selectbox("Font Weight", FONT_WEIGHTS, index=1)
        st.session_state["base_size"] = st.number_input("Base Size (px)", min_value=8, max_value=120, value=48)
        st.session_state["font_family_stack"] = FONT_OPTIONS[font_label]

        st.markdown("**User Injected — Organisation Logos (optional)**")
        st.caption(
            "Leave empty to use the logo row Stage 0b detected along the top of "
            "the master layout (backgrounds removed). Upload files to override "
            "it, in left-to-right order, e.g. when the detector missed a logo or "
            "picked a footer icon. The first file is the certificate's seal. "
            "Transparent PNGs give the cleanest result."
        )
        logo_uploads = st.file_uploader(
            "Organisation logos", type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True, key="logo_upload",
        )
        st.session_state["logo_image_paths"] = [_save_upload(f) for f in logo_uploads] or None

    st.markdown("---")
    st.subheader("Target Initialization")

    target_formats = _discover_target_formats()
    if not target_formats:
        st.error("No *_payload.json files found under data/raw/.")
    else:
        target_label = st.selectbox("Select Target Format", list(target_formats.keys()))
        target = target_formats[target_label]
        schema = target["meta"].get("variable_schema", {})

        st.markdown("**Required structural fields**")
        for var_name, props in schema.items():
            count = props.get("instantiation_count", 1)
            st.write(f"- [{count}] {_friendly_field_name(var_name)}  `{props.get('structural_class')}`")

        domain = target["meta"].get("domain_context")
        content_path = _CONTENT_DATA_BY_DOMAIN.get(domain)
        use_real_content = st.checkbox(
            f"Populate with sample content ({os.path.basename(content_path)})"
            if content_path else "No sample content available for this domain",
            value=bool(content_path),
            disabled=not content_path,
        )

        ready = ingestion_result is not None
        if not ready:
            st.caption("Extract Visual DNA on the left before initializing orchestration.")

        init_clicked = st.button(
            "▶ Initialize Orchestration", type="primary", disabled=not ready,
        )

        if init_clicked:
            with st.spinner("Running Stages 1-6 (instantiation → GNN → CSP → ranking → render → FSM)..."):
                result = themesync_pipeline.run_pipeline(
                    payload_path=target["path"],
                    template_image=st.session_state.get("image_path"),
                    content_data_path=content_path if use_real_content else None,
                    font_family=st.session_state.get("font_family_stack"),
                    logo_images=st.session_state.get("logo_image_paths"),
                )
            st.session_state["orchestration_result"] = result
            st.rerun()
