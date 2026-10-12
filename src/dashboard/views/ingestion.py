"""
ThemeSync — Perceptual Ingestion & Initialization Dashboard (Figure 2)
=======================================================================
Chapter 3, pp. 50-51: the uploaded master layout, the "Hybrid Visual DNA"
in its two parts, and the target set-up, on one screen without scrolling.
Laid out from the user's mockups A1-A3 (2026-10-09, notes §3.37):

  Left: the Master Layout
    A1, before extraction: a large upload area, Extract Visual DNA, and the
    Stage 0b toggle. A2, after: the master's preview (the expand icon opens
    it full size), its K-Means colour centroids (Stage 0) and SIFT
    keypoints (saliency, logo detected) beneath it. The (i) icon opens the
    relational node graph YOLO parsed (Stage 0b), with its detections drawn
    on the master.
  Right: what the new layout carries
    Organisation logos and the stylistic markers Stage 0c cut from the
    master (text-free background, title artwork, motifs) in one card, each
    tile ticked to use it; the administrative typography (font family,
    weight, baseline size) in one row; the content payload. Typography and
    content are validated against their JSON Schemas before orchestration
    may start (p.43).
  The Target Initialization panel (A3)
    Opened from the top bar, it slides over the page without moving it:
    target format and its structural fields, structure mapping + GNN or baseline, the
    schema validation, and "Initialize", which runs Stages 1-6 and moves on
    to Step 2, the Figure 3 workspace.

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
import mail_merge                                                    # noqa: E402
import poster_text                                                   # noqa: E402
import pipeline                                                      # noqa: E402
from aesthetic_renderer import DEFAULT_TYPOGRAPHY, _palette_from_centroids  # noqa: E402
from schema_validation import FONT_WEIGHTS, validate_content, validate_typography  # noqa: E402
from stylistic_markers import build_style_kit                        # noqa: E402
from template_ingestor import TemplateIngestor                       # noqa: E402

_ROOT = ui.ROOT
DNA_DIR = os.path.join(ui.SESSIONS_DIR, "visual_dna")
IMAGE_TYPES = ["png", "jpg", "jpeg", "bmp", "webp"]

# Explicit domain -> sample content-data mapping (data/raw/).
_CONTENT_DATA_BY_DOMAIN = {
    "academic_certificate": os.path.join(_ROOT, "data", "raw", "sample_content.json"),
    "identification_card":  os.path.join(_ROOT, "data", "raw", "sample_content_id.json"),
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


def _placeholder(text: str) -> None:
    st.markdown(f'<div class="ts-placeholder">{html.escape(text)}</div>', unsafe_allow_html=True)


def _legend(nodes: list) -> str:
    seen = {n["semantic_category"] for n in nodes}
    return '<div class="ts-legend">' + "".join(
        f'<span><i style="background:rgb{CATEGORY_COLOURS[c]}"></i>{c}</span>'
        for c in CATEGORY_COLOURS if c in seen) + "</div>"


def _annotated(path: str, nodes: list) -> Image.Image:
    return ui.annotate(path, [(n["semantic_category"][:4], n["bbox"],
                               CATEGORY_COLOURS.get(n["semantic_category"], (255, 255, 255))) for n in nodes])


IMAGE_DROP_TYPES = ["png", "jpg", "jpeg", "webp"]


@st.cache_data(show_spinner="Reading the poster's text (OCR)...")
def _poster_lines(path: str, mtime: float) -> list:
    """Readable lines of the master's text (poster_text.ocr_lines), from
    Stage 0b's OCR of its text boxes."""
    return poster_text.ocr_lines(path, ui.detect(path, mtime))


MAX_REPEATS = 5    # the stress test: signature blocks overlap from six (notes §3.42; Chapter 5)


def _content_keys(var: str, props: dict) -> list:
    """A variable's content keys: {{Name}}, or {{Name}}_0, _1... for a
    repeating group."""
    count = props.get("instantiation_count", 1)
    return [f"{var}_{i}" for i in range(count)] if count > 1 else [var]


def _replaced(key: str):
    """The picture the designer dropped on tile `key` (its path), or None."""
    path = st.session_state.get(f"replaced_{key}")
    return path if path and os.path.exists(path) else None


def _drop_zone(key: str) -> None:
    """An invisible upload area over tile `key`'s picture (notes §3.53):
    drop an image on it, or click it, to replace the extracted one; the ↺
    button goes back to the extracted image."""
    n = st.session_state.get(f"replace_n_{key}", 0)
    up = st.file_uploader("Drop an image here to replace it", type=IMAGE_DROP_TYPES, key=f"drop_{key}_{n}",
                          label_visibility="collapsed")
    if up is not None:
        path = ui.save_upload(up, prefix="replace_")
        if st.session_state.get(f"replaced_{key}") != path:
            st.session_state[f"replaced_{key}"] = path
            st.rerun()                                     # show the new picture on the tile
    if _replaced(key):
        def revert() -> None:
            st.session_state.pop(f"replaced_{key}", None)
            st.session_state[f"replace_n_{key}"] = n + 1   # a fresh, empty upload area

        st.button("", icon=":material/undo:", key=f"revert_{key}", type="tertiary", on_click=revert,
                  help="Back to the extracted image")


def _shown(image: Image.Image, key: str) -> Image.Image:
    """The tile's picture: the designer's replacement, if any."""
    path = _replaced(key)
    if not path:
        return image
    with Image.open(path) as im:
        return im.copy()


def _tile(image: Image.Image, key: str, label: str, default: bool, size: int = 60, kind: str = "mark") -> bool:
    """One pickable tile: the image (coral ring when picked), an image
    dropped on it replaces it, and the checkbox under it picks it. Returns
    whether it's picked."""
    picked = st.session_state.get(key, default)
    with st.container(key=f"tile_{key}", width="content", gap=None):
        st.markdown(ui.thumbs([{"image": _shown(image, key), "kind": kind, "state": "on" if picked else "off"}],
                              size=size), unsafe_allow_html=True)
        _drop_zone(key)
        return st.checkbox(label, value=default, key=key)


@st.cache_data(show_spinner="Stage 0: K-Means palette and SIFT saliency...")
def _ingest(path: str, mtime: float) -> dict:
    return TemplateIngestor(n_colors=3).ingest(path)


@st.cache_data(show_spinner="Stage 0c: text-free background, motifs, title artwork...")
def _style_kit(path: str, mtime: float, nodes_json: str) -> dict:
    nodes = json.loads(nodes_json)
    stem = os.path.splitext(os.path.basename(path))[0]
    return build_style_kit(path, nodes, os.path.join(DNA_DIR, stem), stem,
                           logo_boxes=[n["bbox"] for n in nodes if n.get("semantic_category") == "logo"])


@st.cache_data(show_spinner=False)
def _poster_uri(path: str, mtime: float) -> str:
    """The master as a preview for its card."""
    with Image.open(path) as img:
        im = img.convert("RGB")
    im.thumbnail((1000, 1000))
    return ui.data_uri(im, "JPEG")


@st.dialog("Master layout", width="large")
def _full_view(path: str, nodes: list) -> None:
    show = st.toggle("Show Stage 0b detections", value=False, disabled=not nodes)
    st.image(_annotated(path, nodes) if show and nodes else path, width="stretch")
    if show and nodes:
        st.markdown(_legend(nodes), unsafe_allow_html=True)
    with Image.open(path) as img:
        st.caption(f"{os.path.basename(path)} · {img.width}×{img.height} px")


@st.dialog("Relational Node Graph", width="large")
def _node_graph(path: str, nodes: list, yolo_error: str) -> None:
    if yolo_error:
        st.warning(f"Stage 0b unavailable — {yolo_error}")
        return
    if not nodes:
        st.info("No nodes detected above the confidence threshold.")
        return
    counts = {}
    for n in nodes:
        counts[n["semantic_category"]] = counts.get(n["semantic_category"], 0) + 1
    st.markdown(f'<div class="bn-big">{len(nodes)}<small> nodes parsed from the master (Stage 0b: '
                f'YOLOv8 + Tesseract OCR)</small></div><div class="bn-chips">'
                + "".join(f'<span class="bn-chip">{c} <i>{k}</i></span>' for c, k in sorted(counts.items()))
                + "</div>", unsafe_allow_html=True)
    left, right = st.columns([1, 1.1], gap="medium")
    with left:
        st.image(_annotated(path, nodes), width="stretch")
        st.markdown(_legend(nodes), unsafe_allow_html=True)
    with right, st.container(height=520, border=False):
        st.markdown('<div class="bn-nodes">' + "".join(_node_row(n) for n in nodes) + "</div>",
                    unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

actions = ui.enter_step(1, "New design · upload a master layout, review its Visual DNA, set up the target")
st.session_state.setdefault("target_panel", False)


def _toggle_panel() -> None:
    st.session_state["target_panel"] = not st.session_state["target_panel"]


# The page (A1/A2): the master layout on the left, the cards on the right.
# The target panel (A3) is a fixed overlay, so opening it moves nothing.
# Cards are laid out first and filled in the order their values depend on
# each other.
left_col, right_col = st.columns([0.86, 1], gap="medium")
card_master = left_col.container(border=True, key="card_master")
with right_col, st.container(key="right_stack", gap=None):
    card_assets = st.container(border=True, key="card_assets")
    card_type = st.container(border=True, key="card_type")
    card_content = st.container(border=True, key="card_content")
drawer = st.container(key="ts_drawer") if st.session_state["target_panel"] else None

dna = None
typography = dict(DEFAULT_TYPOGRAPHY)
logo_images, motif_paths, use_wordmark, wordmark_path, background_path = None, [], False, None, None

# ---------------------------------------------------------------------------
# The Master Layout (left)
# ---------------------------------------------------------------------------
with card_master:
    master_path = st.session_state.get("master_path")
    has_master = bool(master_path and os.path.exists(master_path))
    extracted = has_master and st.session_state.get("dna_for") == master_path

    open_graph = False
    with st.container(horizontal=True, key="master_head", vertical_alignment="center"):
        ui.card_title("image", "Master Layout")
        if has_master:
            with st.popover("", icon=":material/upload:", help="Upload a different master layout"):
                replacement = st.file_uploader("A different master layout (event poster, banner, letterhead...)",
                                               type=IMAGE_TYPES, key="master_replace")
            if replacement is not None:
                new_path = ui.save_upload(replacement)
                if new_path != master_path:
                    st.session_state["master_path"] = new_path
                    st.session_state.pop("dna_for", None)
                    st.rerun()
        if extracted:
            open_graph = st.button("", icon=":material/info:", key="node_graph_btn",
                                   help="Relational Node Graph: the elements Stage 0b parsed from the master")

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
        if open_graph:
            _node_graph(master_path, nodes, yolo_error)

    # The preview (or, with nothing uploaded, the upload area)
    with st.container(key="master_view", gap=None):
        if has_master:
            stage = "a2" if dna else "a1"
            st.markdown(f'<div class="ts-poster {stage}"><img src="{_poster_uri(master_path, os.path.getmtime(master_path))}"'
                        ' alt="master layout"></div>', unsafe_allow_html=True)
            with st.container(key="preview_tools"):
                if st.button("", icon=":material/open_in_full:", key="full_view_btn", help="View full size"):
                    _full_view(master_path, dna["nodes"] if dna else [])
        else:
            with st.container(key="master_drop"):
                uploaded = st.file_uploader("Upload a master layout (event poster, banner, letterhead...)",
                                            type=IMAGE_TYPES, key="master_upload", label_visibility="collapsed")
            if uploaded is not None:
                st.session_state["master_path"] = ui.save_upload(uploaded)
                st.rerun()

    if dna is None:
        # A1: extraction not run yet
        if st.button("Extract Visual DNA", icon=":material/biotech:", type="primary", disabled=not has_master,
                     width="stretch", help="Stage 0 (K-Means + SIFT), Stage 0b (YOLOv8 + OCR) and Stage 0c "
                                           "(stylistic markers) on the uploaded image."):
            st.session_state["dna_for"] = master_path
            st.rerun()
        st.toggle("Show Stage 0b detections", value=False, disabled=True,
                  help="After extraction, the (i) icon and the full-size view show the detections.")
    else:
        # A2: the autonomous extraction beneath the preview
        ing = dna["ingestion"]
        km_col, sift_col = st.columns([1.05, 1], gap="medium")
        with km_col:
            ui.card_title("palette", "K-Means Color Centroids")
            palette = _palette_from_centroids(ing["color_centroids"])
            st.markdown('<div class="ts-swatches">' + "".join(
                f'<div class="ts-swatch" title="{h}"><span style="background:{h}"></span><code>{h}</code></div>'
                for h in ing["palette_hex"]) + "</div>", unsafe_allow_html=True)
            st.caption(f"Primary `{palette['primary']}` · accent `{palette['accent']}`")
        with sift_col:
            ui.card_title("scatter_plot", "SIFT Keypoints")
            logos_found = any(n.get("semantic_category") == "logo" for n in dna["nodes"])
            stats = [("Saliency", f"{ing['saliency_weight']:.4f}"), ("Logo", "Yes" if logos_found else "No"),
                     ("Size", f"{ing['image_wh'][0]}×{ing['image_wh'][1]}")]
            st.markdown('<div class="ts-stats">' + "".join(
                f'<div class="ts-stat"><small>{k}</small><b>{v}</b></div>' for k, v in stats) + "</div>",
                unsafe_allow_html=True)
            st.caption("Keypoint density; its map drives Formula 3.15.")

kit = dna["kit"] if dna else None

# ---------------------------------------------------------------------------
# Organisation logos and stylistic markers (right, top)
# ---------------------------------------------------------------------------
with card_assets:
    logos_col, markers_col = st.columns(2, gap="large")

with logos_col, st.container(key="assets_logos"):
    cands = ui.logo_detections(master_path, dna["nodes"]) if dna else []
    ui.card_title("verified", "Organisation Logos", f"{len(cands)} detected" if dna else "")
    ticked = []
    with st.container(key="logo_grid", gap=None):
        if not dna:
            _placeholder("The master's logos appear here after extraction.")
        elif not cands:
            _placeholder("No logos detected — a drawn badge stands in unless you add one.")
        else:
            with st.container(horizontal=True, key="logo_tiles", gap="small"):
                for c in cands:
                    key = f"logo_{dna['stem']}_{c['id']}"
                    if _tile(c["image"], key, f"{c['label']} · {c['conf']:.2f}", c["auto"]):
                        ticked.append(dict(c, replaced=_replaced(key)))
        note_slot = st.empty()
    with st.container(key="logos_btn"):
        with st.popover("Add Logos", icon=":material/add_photo_alternate:", width="stretch", disabled=not dna):
            extra = st.file_uploader("Logos Stage 0b missed (transparent PNGs look best)",
                                     type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True,
                                     key="logo_upload")
            if cands:
                st.image(ui.annotate(master_path, [(c["label"], c["bbox"], ui.GREEN if c in ticked else ui.RED)
                                                   for c in cands]), caption="Detections: green = picked",
                         width="stretch")
        if dna:
            uploads = [ui.save_upload(f, prefix="logo_") for f in extra or []]
            auto_ids = {c["id"] for c in cands if c["auto"]}
            if (cands and {c["id"] for c in ticked} == auto_ids and not uploads
                    and not any(c["replaced"] for c in ticked)):
                note = "✓ ThemeSync's automatic pick"
            elif ticked or uploads:
                os.makedirs(os.path.join(ui.UPLOAD_DIR, "logos"), exist_ok=True)
                logo_images = []
                for c in sorted(ticked, key=lambda c: (not c["primary"], c["x"])):
                    if c["replaced"]:                      # an image dropped on the tile
                        logo_images.append(c["replaced"])
                        continue
                    path = os.path.join(ui.UPLOAD_DIR, "logos", f"{dna['stem']}_{c['id']}.png")
                    c["image"].save(path)
                    logo_images.append(path)
                logo_images = (logo_images + uploads) or None
                note = "Manual pick · the first is the certificate seal" + (
                    f" · {len(uploads)} uploaded" if uploads else "")
            else:
                note = "No logo picked — a drawn badge stands in"
            note_slot.markdown(f'<div class="ts-note">{html.escape(note)}</div>', unsafe_allow_html=True)

with markers_col, st.container(key="assets_markers"):
    ui.card_title("auto_awesome_mosaic", "Stylistic Markers", "Stage 0c" if dna else "")
    with st.container(key="marker_grid", gap=None):
        if not dna:
            _placeholder("The text-free background, title artwork and motifs appear here after extraction.")
        else:
            # One row: the background, the title artwork, the motifs
            with st.container(horizontal=True, key="marker_tiles", gap="small"):
                bg_key = f"background_{dna['stem']}"
                with Image.open(kit["background"]) as bg, st.container(key="tile_background", width="content",
                                                                        gap=None):
                    st.markdown(ui.thumbs([{"image": _shown(bg.convert("RGB"), bg_key).convert("RGB"),
                                            "kind": "photo", "caption": "Text-free background"}], size=60),
                                unsafe_allow_html=True)
                    _drop_zone(bg_key)
                background_path = _replaced(bg_key)
                if kit["wordmark"]:
                    wm_key = f"wordmark_{dna['stem']}"
                    with Image.open(kit["wordmark"]["path"]) as wm:
                        use_wordmark = _tile(wm.copy(), wm_key, "Title artwork", True)
                    wordmark_path = _replaced(wm_key) or wordmark_path
                for i, m in enumerate(kit["motifs"]):
                    m_key = f"motif_{dna['stem']}_{i}"
                    with Image.open(m["path"]) as im:
                        if _tile(im.copy(), m_key, f"M{i + 1} · {m['confidence']:.2f}", True):
                            motif_paths.append(_replaced(m_key) or m["path"])
        marker_note = st.empty()
    with st.container(key="markers_btn"):
        with st.popover("Upload Title Artwork", icon=":material/upload:", width="stretch", disabled=not dna):
            up = st.file_uploader("Title artwork (transparent PNG)", type=["png", "webp"], key="wordmark_upload")
        if up:
            wordmark_path = ui.save_upload(up, prefix="wordmark_")
            use_wordmark = True
        if dna:
            title = ("Title artwork on the event ID" if use_wordmark else
                     "Event title typed" + ("" if kit["wordmark"] else " (no title artwork separated cleanly)"))
            motifs = (f"{len(motif_paths)} of {len(kit['motifs'])} motifs travel" if kit["motifs"]
                      else "no motifs separated cleanly")
            marker_note.markdown(f'<div class="ts-note">{html.escape(title)} · {motifs}</div>',
                                 unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Administrative typography (right, middle): one row
# ---------------------------------------------------------------------------
with card_type:
    ui.card_title("text_fields", "Administrative Typography")
    font_col, weight_col, size_col = st.columns([1.5, 1.15, 1], gap="small")
    with font_col:
        family = ui.font_picker("type", "Primary Font", DEFAULT_TYPOGRAPHY["family"])
    weight = weight_col.selectbox("Font Weight", FONT_WEIGHTS, index=FONT_WEIGHTS.index(700),
                                  format_func=lambda w: f"{w} — {WEIGHT_NAMES[w]}")
    base = size_col.number_input("Base Size (px)", min_value=1.0, max_value=400.0, value=48.0, step=1.0,
                                 help="The certificate title's size; the whole type scale is built on it. "
                                      "Checked against its JSON Schema before orchestration (p.43).")
    typography = {"family": family, "weight": int(weight), "base_size": float(base)}

# ---------------------------------------------------------------------------
# The target: chosen in the panel, remembered while the panel is closed
# ---------------------------------------------------------------------------
formats = _discover_target_formats()
if not formats:
    st.error("No *_payload.json files found under data/raw/.")
    st.stop()
labels = list(formats)
if st.session_state.get("target_label") not in formats:
    st.session_state["target_label"] = labels[0]
st.session_state.setdefault("use_gnn", True)


def _canvas(meta: dict) -> tuple:
    return pipeline._derive_canvas(meta, None, None)


if drawer is not None:
    with drawer:
        with st.container(horizontal=True, key="drawer_head", vertical_alignment="center"):
            ui.card_title("flag", "Target Initialization")
            st.button("", icon=":material/close:", key="drawer_close", on_click=_toggle_panel,
                      help="Close the panel")

        def _pick_target() -> None:
            st.session_state["target_label"] = st.session_state["target_radio"]

        captions = []
        for label in labels:
            meta = formats[label]["meta"]
            w, h = _canvas(meta)
            captions.append(f"{meta.get('target_aspect_ratio', '?')} · {w}×{h} px · "
                            f"{'landscape' if w > h else 'portrait'}")
        st.radio("Target format", labels, index=labels.index(st.session_state["target_label"]),
                 captions=captions, key="target_radio", on_change=_pick_target,
                 format_func=lambda label: label.split(" (")[0])

target = formats[st.session_state["target_label"]]
full_schema = target["meta"].get("variable_schema", {})
canvas_w, canvas_h = _canvas(target["meta"])
domain = target["meta"].get("domain_context")
# The elements the layout keeps: the target panel's checkboxes (notes §3.54).
# The payload is cut down to them, so they are what is validated, filled in
# and instantiated.
nodes_key = f"nodes_{domain}"
kept = [v for v in st.session_state.get(nodes_key, list(full_schema)) if v in full_schema] or list(full_schema)
# How many of each repeating group (signature blocks), 1 to MAX_REPEATS
counts_key = f"counts_{domain}"
counts = st.session_state.get(counts_key, {})
schema = {k: (dict(v, instantiation_count=int(counts[k])) if k in counts else v)
          for k, v in full_schema.items() if k in kept}
target_meta = dict(target["meta"], variable_schema=schema)

# ---------------------------------------------------------------------------
# Content payload (right, bottom): two columns of fields
# ---------------------------------------------------------------------------
sample_path = _CONTENT_DATA_BY_DOMAIN.get(domain)
sample = json.load(open(sample_path)) if sample_path and os.path.exists(sample_path) else {}
content = {}
with card_content:
    with st.container(horizontal=True, key="content_head", vertical_alignment="center"):
        ui.card_title("edit_note", "Content Payload", _friendly(domain) if domain else "")

        def _fill_sample() -> None:
            for var, props in schema.items():
                if props.get("structural_class") != "image_node":
                    for key in _content_keys(var, props):
                        st.session_state[f"content_{domain}_{key}"] = str(sample.get(key, sample.get(f"{key}_0", "")))

        st.button("", icon=":material/text_snippet:", key=f"sample_{domain}", on_click=_fill_sample,
                  help="Fill the fields with sample text")
        lines = _poster_lines(master_path, os.path.getmtime(master_path)) if dna else []
        with st.popover("", icon=":material/document_scanner:", disabled=not lines,
                        help="The text read from the poster (OCR), to copy into any field"):
            st.caption("Read from the master layout by OCR, top to bottom. Copy a line into any field.")
            for line in lines:
                st.code(line["text"], language=None)
        with st.popover("", icon=":material/upload_file:", help="Load a JSON payload, or a CSV for a mail merge"):
            payload_upload = st.file_uploader(
                "A JSON payload fills the fields below. A CSV makes a mail merge: one layout per row, "
                "its columns named after the fields (e.g. Participant Name, Participant Role).",
                type=["json", "csv"], key=f"payload_{domain}")
    upload_is_csv = payload_upload is not None and payload_upload.name.lower().endswith(".csv")
    if (payload_upload is not None and not upload_is_csv
            and st.session_state.get("payload_applied") != payload_upload.file_id):
        # applied once per file, so edits made afterwards aren't overwritten on rerun
        try:
            loaded = json.loads(payload_upload.getvalue().decode("utf-8"))
            for key, value in loaded.items():
                st.session_state[f"content_{domain}_{key}"] = str(value)
            st.session_state["payload_applied"] = payload_upload.file_id
        except (ValueError, UnicodeDecodeError, AttributeError) as e:
            st.error(f"Could not read that JSON: {e}")
    # Fields in two columns: short ones pair up, a long one takes a row
    # Suggestions from the poster's text (poster_text.suggest_fields): they
    # fill empty fields once per poster; a new poster replaces the earlier
    # poster's suggestions the designer hasn't changed
    filled_key = f"poster_filled_{domain}"
    if dna and st.session_state.get(f"poster_applied_{domain}") != dna["stem"]:
        limits = {k: p.get("max_characters") for v, p in schema.items() if p.get("structural_class") == "text_node"
                  for k in _content_keys(v, p)}
        for key, old in st.session_state.get(filled_key, {}).items():
            if st.session_state.get(f"content_{domain}_{key}") == old:
                st.session_state[f"content_{domain}_{key}"] = ""
        filled = {}
        for key, value in poster_text.suggest_fields(lines, domain, limits).items():
            if not st.session_state.get(f"content_{domain}_{key}"):
                st.session_state[f"content_{domain}_{key}"] = filled[key] = value
        st.session_state[filled_key] = filled
        st.session_state[f"poster_applied_{domain}"] = dna["stem"]
    from_poster = {k for k, v in st.session_state.get(filled_key, {}).items()
                   if st.session_state.get(f"content_{domain}_{k}") == v}
    fields = []                                    # (key, label, long?, max_characters)
    base_content = {}                              # every field's value in the form
    examples = {}                                  # the sample text, shown as each field's hint
    for var, props in schema.items():
        count = props.get("instantiation_count", 1)
        for key in _content_keys(var, props):
            example = examples[key] = str(sample.get(key, sample.get(f"{key}_0", "")))
            wkey = f"content_{domain}_{key}"
            if props.get("structural_class") == "image_node":
                st.session_state.setdefault(wkey, example)
                content[key] = base_content[key] = st.session_state[wkey]   # alt text only; the image is the logo
                continue
            st.session_state.setdefault(wkey, "")  # fields start empty (notes §3.54)
            base_content[key] = st.session_state[wkey]
            label = _friendly(key) if count == 1 else f"{_friendly(var)} {int(key.rsplit('_', 1)[1]) + 1}"
            long = ("\n" in example or props.get("max_characters", 0) > 80
                    or props.get("structural_class") == "repeating_group")
            fields.append((key, label, long, props.get("max_characters")))
    # A CSV: the mail merge (mail_merge.py), applied once per file
    merge_key = f"merge_{domain}"
    if upload_is_csv and st.session_state.get("payload_applied") != payload_upload.file_id:
        st.session_state["payload_applied"] = payload_upload.file_id
        try:
            st.session_state[merge_key] = mail_merge.build(
                payload_upload.getvalue(), {k: (label, mx) for k, label, _, mx in fields}, base_content,
                target_meta, payload_upload.name)
        except ValueError as e:
            st.error(f"Mail merge: {e}")
    merge = st.session_state.get(merge_key)
    if merge:
        with st.container(horizontal=True, key="merge_note", vertical_alignment="center", gap="small"):
            left_out = f' · <b>{len(merge["invalid"])} left out</b>' if merge["invalid"] else ""
            st.markdown(f'<div class="ts-note"><b>Mail merge</b> · {len(merge["rows"])} of {merge["total"]} rows '
                        f'from {html.escape(merge["source"])} · {html.escape(", ".join(merge["labels"].values()))}'
                        f'{left_out}</div>', unsafe_allow_html=True)
            if merge["invalid"]:
                with st.popover("", icon=":material/warning:", help="The rows left out, and why"):
                    for number, errors in merge["invalid"]:
                        st.markdown(f"**Row {number}:** " + html.escape("; ".join(errors)))
            st.button("", icon=":material/close:", key="merge_clear", type="tertiary", help="Stop the mail merge",
                      on_click=lambda: st.session_state.pop(merge_key, None))
    empty = any(not str(base_content.get(k, "")).strip() for k, *_ in fields if not (merge and k in merge["fields"]))
    note = []
    if from_poster:
        note.append(f"<b>{len(from_poster)} field{'s' if len(from_poster) > 1 else ''} filled from the poster's text "
                    f"(OCR)</b>; check {'them' if len(from_poster) > 1 else 'it'}.")
    if empty:
        note.append("An empty field shows as a placeholder, such as «Student Name», on the canvas.")
    if note:
        st.markdown(f'<div class="ts-note">{" ".join(note)}</div>', unsafe_allow_html=True)
    rows, pending = [], []
    for field in fields:
        if field[2]:
            rows.append([field])
        else:
            pending.append(field)
            if len(pending) == 2:
                rows.append(pending)
                pending = []
    if pending:
        rows.append(pending)
    with st.container(border=False, key="content_fields"):
        for row in rows:
            cols = st.columns(2, gap="small") if len(row) == 2 or not row[0][2] else [st.container()]
            for (key, label, long, max_chars), col in zip(row, cols):
                wkey = f"content_{domain}_{key}"
                if merge and key in merge["fields"]:
                    # One layout to edit: the merged field shows its placeholder
                    content[key] = merge["placeholders"][key]
                    widget = col.text_area if long else col.text_input
                    widget(label, value=content[key], disabled=True, key=f"merged_{wkey}",
                           help=f"Filled from {merge['source']} for each layout")
                    continue
                hint = f"e.g. {examples[key]}" if examples.get(key) else ""
                shown = f"{label} · from the poster" if key in from_poster else label
                tip = "Read from the master layout by OCR; check it." if key in from_poster else None
                if long:
                    value = col.text_area(shown, key=wkey, height=68, max_chars=max_chars, placeholder=hint,
                                          help=tip)
                else:
                    value = col.text_input(shown, key=wkey, max_chars=max_chars, placeholder=hint, help=tip)
                # An empty field becomes a placeholder on the canvas, editable in Step 2
                content[key] = value if value.strip() else mail_merge.placeholder(label, max_chars)

# Pre-orchestration schema validation (Chapter 3, p.43)
checks = {"typography": validate_typography(typography, canvas_w, canvas_h),
          "content": validate_content(content, target_meta)}
problems = [f"{name}: {e}" for name, v in checks.items() for e in v["errors"]]
ready = dna is not None and not problems

# ---------------------------------------------------------------------------
# The rest of the target panel, ending with Initialize
# ---------------------------------------------------------------------------
if drawer is not None:
    with drawer:
        def _pick_nodes(changed: str) -> None:
            chosen = [v for v in full_schema if st.session_state.get(f"nodecb_{domain}_{v}", v in kept)]
            st.session_state[nodes_key] = chosen or [changed]     # a layout keeps at least one element

        with st.expander(f"Layout elements · {len(schema)} of {len(full_schema)}", icon=":material/checklist:",
                         expanded=True), st.container(key="node_picks"):
            st.caption("Untick an element to leave it out of the layout.")
            singles = [(v, p) for v, p in full_schema.items() if p.get("structural_class") != "repeating_group"]
            groups = [(v, p) for v, p in full_schema.items() if p.get("structural_class") == "repeating_group"]
            cols = st.columns(2, gap="small")
            for i, (var, props) in enumerate(singles):
                cols[i % 2].checkbox(_friendly(var), value=var in kept, key=f"nodecb_{domain}_{var}",
                                     on_change=_pick_nodes, args=(var,), disabled=var in kept and len(kept) == 1)

            def _pick_count(var: str) -> None:
                st.session_state[counts_key] = dict(st.session_state.get(counts_key, {}),
                                                    **{var: int(st.session_state[f"nodecount_{domain}_{var}"])})

            for var, props in groups:                  # a repeating group: how many, 1 to MAX_REPEATS
                with st.container(horizontal=True, key=f"nodegroup_{var.strip('{}')}", vertical_alignment="center",
                                  gap="small"):
                    st.checkbox(_friendly(var), value=var in kept, key=f"nodecb_{domain}_{var}",
                                on_change=_pick_nodes, args=(var,), disabled=var in kept and len(kept) == 1)
                    st.number_input("How many", min_value=1, max_value=MAX_REPEATS, step=1,
                                    value=int(counts.get(var, props.get("instantiation_count", 1))),
                                    key=f"nodecount_{domain}_{var}", on_change=_pick_count, args=(var,),
                                    disabled=var not in kept, label_visibility="collapsed", width=110,
                                    help=f"1 to {MAX_REPEATS}: from six, the blocks overlap on the certificate")

        def _pick_gnn() -> None:
            st.session_state["use_gnn"] = st.session_state["gnn_toggle"]

        st.toggle("Structure mapping + GNN", value=st.session_state["use_gnn"], key="gnn_toggle",
                  on_change=_pick_gnn,
                  help="On: the master's structure is mapped onto the target and refined by the GNN. "
                       "Off: the baseline, with neither; the solver stacks the elements in reading order.")
        if problems:
            st.error("Schema validation — initialization would be rejected:\n\n"
                     + "\n".join(f"- {p}" for p in problems))
        else:
            st.success("Schema validation passed: typography and content payload conform.",
                       icon=":material/task_alt:")

        with st.container(key="drawer_cta"):
            notice = st.empty()
            if dna is None:
                st.caption("Extract the Visual DNA of a master layout first.")
            elif st.session_state.get("orch") is not None:
                st.caption("Initializing starts a new layout; the one you were editing stays saved in its "
                           "session folder.")
            clicked = st.button("Initialize", icon=":material/play_arrow:", type="primary", disabled=not ready,
                                width="stretch", key="initialize_btn",
                                help="Run Stages 1-6 (instantiation → GNN → CSP → ranking → render → state "
                                     "chain) and open Step 2.")
        if clicked:
            out_dir = os.path.join(ui.SESSIONS_DIR, f"{time.strftime('%Y%m%d_%H%M%S')}_{dna['stem']}_{domain}")
            payload_path = target["path"]
            if schema != full_schema:              # the payload cut down to the kept elements and counts
                os.makedirs(out_dir, exist_ok=True)
                payload_path = os.path.join(out_dir, os.path.basename(target["path"]))
                with open(payload_path, "w", encoding="utf-8") as f:
                    json.dump(target_meta, f, indent=2)
            session = pipeline.OrchestrationSession(
                payload_path, template_image=master_path, content_data=content, typography=typography,
                use_gnn=st.session_state["use_gnn"], output_dir=out_dir, logo_images=logo_images,
                use_wordmark=use_wordmark, wordmark_path=wordmark_path, motif_paths=motif_paths,
                detected_nodes=dna["nodes"], background_path=background_path,
            )
            session.merge = merge or None          # the merged fields keep their placeholders on the canvas
            try:
                with notice, st.spinner("Running Stages 1-6..."):
                    session.run()
            except ValueError as e:
                notice.error(str(e))
            else:
                st.session_state["orch"] = session
                st.session_state["orch_master"] = master_path
                ui.go_to_step(2)

# ---------------------------------------------------------------------------
# The top bar: the target panel's button
# ---------------------------------------------------------------------------
with actions:
    _, panel_btn = st.columns([1.15, 1], gap="small")
    is_open = drawer is not None
    panel_btn.button("Target Initialization", on_click=_toggle_panel, width="stretch", key="panel_btn",
                     type="secondary" if is_open else "primary",
                     icon=":material/right_panel_close:" if is_open else ":material/right_panel_open:",
                     help=("Close" if is_open else "Open") + " the target panel: format, structural fields, "
                          "GNN or baseline, schema validation, and Initialize.")
