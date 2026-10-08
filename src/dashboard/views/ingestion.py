"""
ThemeSync — Perceptual Ingestion & Initialization Dashboard (Figure 2)
=======================================================================
Chapter 3, pp. 50-51: the uploaded master template, the "Hybrid Visual
DNA" in its two parts, and the target set-up, on one workspace that fits
the screen (the user's layout, 2026-10-08, notes §3.36):

  Top row: what the new layout carries
    Organisation logos (detected, picked, or uploaded), the stylistic
    markers Stage 0c cut from the master (text-free background, title
    artwork, motifs), the administrative typography (font family, weight,
    baseline size), and the content payload. Typography and content are
    validated against their JSON Schemas before orchestration may start
    (p.43).
  Bottom row: the master template and its autonomous extraction
    The master (upload, Extract Visual DNA, Stage 0b detections, full
    view), the K-Means colour centroids (Stage 0), the SIFT/SURF keypoints
    (saliency, logo detected), and the relational node graph YOLO parsed
    (Stage 0b).
  Right: the target panel, retractable from the top bar
    Target format and its structural fields, GNN-guided or baseline, and
    the schema validation. "Initialize Orchestration" sits in the top bar,
    so it stays in reach with the panel closed; it runs Stages 1-6 and
    moves on to Step 2, the Figure 3 workspace.

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
from stylistic_markers import build_style_kit                        # noqa: E402
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
EMPTY_TOP = "Upload a master layout (bottom left) and extract its Visual DNA."


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


def _empty(text: str = EMPTY_TOP) -> None:
    st.markdown(f'<div class="bn-empty">{html.escape(text)}</div>', unsafe_allow_html=True)


def _group(text: str) -> None:
    st.markdown(f'<div class="bn-group">{html.escape(text)}</div>', unsafe_allow_html=True)


def _annotated(path: str, nodes: list) -> Image.Image:
    return ui.annotate(path, [(n["semantic_category"][:4], n["bbox"],
                               CATEGORY_COLOURS.get(n["semantic_category"], (255, 255, 255))) for n in nodes])


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
def _poster_uri(path: str, mtime: float, nodes_json: str = None) -> str:
    """The master as a small preview for its card, with the Stage 0b boxes
    drawn on it when `nodes_json` is given."""
    if nodes_json is None:
        with Image.open(path) as img:
            im = img.convert("RGB")
    else:
        im = _annotated(path, json.loads(nodes_json))
    im.thumbnail((900, 900))
    return ui.data_uri(im, "JPEG")


@st.dialog("Master template", width="large")
def _full_view(path: str, nodes: list, show_nodes: bool) -> None:
    if show_nodes and nodes:
        st.image(_annotated(path, nodes), width="stretch")
    else:
        st.image(path, width="stretch")
    with Image.open(path) as img:
        st.caption(f"{os.path.basename(path)} · {img.width}×{img.height} px")


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

actions = ui.enter_step(1, "New design · upload a master layout, review its Visual DNA, set up the target")

st.session_state.setdefault("target_panel", True)


def _toggle_panel() -> None:
    st.session_state["target_panel"] = not st.session_state["target_panel"]


# The workspace and, on the right, the retractable target panel. The cards
# are laid out first and filled in the order their values depend on each
# other; the panel and the top bar's Initialize come last.
if st.session_state["target_panel"]:
    work_col, panel_col = st.columns([1, 0.235], gap="medium")
else:
    work_col, panel_col = st.container(), None

with work_col, st.container(key="ts_work"):
    notice = st.empty()            # Initialize's progress and errors
    _group("Visual DNA · carried into the new layout")
    with st.container(key="bento_top"):
        t1, t2, t3, t4 = st.columns([0.95, 1.1, 0.85, 1.35], gap="small")
        card_logos = t1.container(border=True, key="card_logos")
        card_markers = t2.container(border=True, key="card_markers")
        card_type = t3.container(border=True, key="card_type")
        card_content = t4.container(border=True, key="card_content")
    _group("Master template · autonomous extraction")
    with st.container(key="bento_bottom"):
        b1, b2, b3 = st.columns([1.45, 1.2, 1.0], gap="small")
        card_master = b1.container(border=True, key="card_master")
        card_colours = b2.container(border=True, key="card_colours")
        card_sift = b2.container(border=True, key="card_sift")
        card_graph = b3.container(border=True, key="card_graph")

dna = None
master_path = None
typography = dict(DEFAULT_TYPOGRAPHY)
logo_images, motif_paths, use_wordmark, wordmark_path = None, [], True, None

# ---------------------------------------------------------------------------
# The master template: upload, extract, detections, full view
# ---------------------------------------------------------------------------
with card_master:
    ui.card_title("image", "Master Template", "Phase 1 input")
    view_col, ctrl_col = st.columns([1, 1.05], gap="small")
    with ctrl_col:
        uploaded = st.file_uploader("Upload a master layout (event poster, banner, letterhead...)",
                                    type=["png", "jpg", "jpeg", "bmp", "webp"], label_visibility="collapsed")
        if uploaded is not None:
            st.session_state["master_path"] = ui.save_upload(uploaded)
        master_path = st.session_state.get("master_path")
        has_master = bool(master_path and os.path.exists(master_path))
        extracted = has_master and st.session_state.get("dna_for") == master_path
        if st.button("Extract Visual DNA", icon=":material/biotech:", type="primary",
                     disabled=not has_master or extracted, width="stretch",
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
            seen = {n["semantic_category"] for n in dna["nodes"]}
            st.markdown('<div class="ts-legend">' + "".join(
                f'<span><i style="background:rgb{CATEGORY_COLOURS[c]}"></i>{c}</span>'
                for c in CATEGORY_COLOURS if c in seen) + "</div>", unsafe_allow_html=True)
        if st.button("View full size", icon=":material/open_in_full:", disabled=not has_master,
                     width="stretch"):
            _full_view(master_path, dna["nodes"] if dna else [], bool(dna and show_nodes))
    with view_col:
        if has_master:
            mtime = os.path.getmtime(master_path)
            uri = _poster_uri(master_path, mtime, json.dumps(dna["nodes"]) if dna and show_nodes else None)
            st.markdown(f'<div class="ts-poster"><img src="{uri}" alt="master layout"></div>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<div class="ts-poster empty"><b>⤒</b>Start here: upload the master layout '
                        "(event poster, banner, letterhead). Its colours, style, elements and logos "
                        "drive every card on this page.</div>", unsafe_allow_html=True)

ing = dna["ingestion"] if dna else None
kit = dna["kit"] if dna else None

with card_colours:
    ui.card_title("palette", "K-Means Color Centroids", "Stage 0")
    if not dna:
        _empty("The master's dominant colours, after extraction.")
    else:
        palette = _palette_from_centroids(ing["color_centroids"])
        st.markdown('<div class="bn-swatches">' + "".join(
            f'<div class="bn-swatch"><span style="background:{h}"></span>'
            f'<code>{h}</code></div>' for i, h in enumerate(ing["palette_hex"])) + "</div>",
            unsafe_allow_html=True)
        st.caption(f"Primary `{palette['primary']}` · accent `{palette['accent']}` · "
                   f"certificate panel `{palette['panel']}`")

with card_sift:
    ui.card_title("scatter_plot", "SIFT/SURF Keypoints", "Stage 0")
    if not dna:
        _empty("Saliency and logo detection, after extraction.")
    else:
        logos_found = [n for n in dna["nodes"] if n.get("semantic_category") == "logo"]
        stats = [("Saliency weight", f"{ing['saliency_weight']:.4f}"),
                 ("Logo detected", "Yes" if logos_found else "No"),
                 ("Native size", f"{ing['image_wh'][0]}×{ing['image_wh'][1]}")]
        st.markdown('<div class="bn-stats">' + "".join(
            f'<div class="bn-stat"><small>{k}</small><b>{v}</b></div>' for k, v in stats) + "</div>",
            unsafe_allow_html=True)
        st.caption("SIFT keypoint density; its map drives the legibility penalty (Formula 3.15).")

with card_graph:
    if not dna or dna["yolo_error"] or not dna["nodes"]:
        ui.card_title("account_tree", "Relational Node Graph", "Stage 0b")
    if not dna:
        _empty("The elements YOLO parses from the master, after extraction.")
    elif dna["yolo_error"]:
        st.warning(f"Stage 0b unavailable — {dna['yolo_error']}")
    elif not dna["nodes"]:
        st.caption("No nodes detected above the confidence threshold.")
    else:
        ui.card_title("account_tree", "Relational Node Graph", f"{len(dna['nodes'])} nodes · Stage 0b")
        counts = {}
        for n in dna["nodes"]:
            counts[n["semantic_category"]] = counts.get(n["semantic_category"], 0) + 1
        st.markdown('<div class="bn-chips">' + "".join(f'<span class="bn-chip">{c} <i>{k}</i></span>'
                                                       for c, k in sorted(counts.items())) + "</div>",
                    unsafe_allow_html=True)
        with st.container(border=False, key="node_list"):
            st.markdown('<div class="bn-nodes">' + "".join(_node_row(n) for n in dna["nodes"]) + "</div>",
                        unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Top row: what the new layout carries
# ---------------------------------------------------------------------------
with card_markers:
    ui.card_title("auto_awesome_mosaic", "Stylistic Markers", "Stage 0c")
    if not dna:
        _empty()
    else:
        items = []
        with Image.open(kit["background"]) as bg:
            items.append({"image": bg.convert("RGB"), "caption": "Text-free background", "kind": "photo"})
        if kit["wordmark"]:
            with Image.open(kit["wordmark"]["path"]) as wm:
                items.append({"image": wm.copy(), "caption": "Title artwork"})
        st.markdown(ui.thumbs(items, size=84), unsafe_allow_html=True)
        if kit["wordmark"]:
            use_wordmark = st.checkbox("Use the title artwork on the event ID", value=True)
        else:
            use_wordmark = False
            st.caption("No title artwork separated cleanly — the event title is typed.")
        with st.popover("Upload title artwork", icon=":material/upload:"):
            up = st.file_uploader("Title artwork (transparent PNG)", type=["png", "webp"], key="wordmark_upload")
        if up:
            wordmark_path = ui.save_upload(up, prefix="wordmark_")
            use_wordmark = True
        if kit["motifs"]:
            motif_slot = st.empty()
            picked = st.pills("Motifs that travel", list(range(len(kit["motifs"]))),
                              selection_mode="multi", default=list(range(len(kit["motifs"]))),
                              format_func=lambda i: f"M{i + 1} · {kit['motifs'][i]['confidence']:.2f}",
                              key=f"motifs_{dna['stem']}")
            motif_paths = [kit["motifs"][i]["path"] for i in picked or []]
            tiles = []
            for i, m in enumerate(kit["motifs"]):
                with Image.open(m["path"]) as im:
                    tiles.append({"image": im.copy(), "caption": f"M{i + 1}",
                                  "state": "on" if i in (picked or []) else "off"})
            motif_slot.markdown(ui.thumbs(tiles, size=54), unsafe_allow_html=True)
        else:
            motif_paths = []
            st.caption("No motifs separated cleanly from this master.")

with card_logos:
    if not dna:
        ui.card_title("verified", "Organisation Logos")
        _empty()
    else:
        cands = ui.logo_detections(master_path, dna["nodes"])
        ui.card_title("verified", "Organisation Logos", f"{len(cands)} detected")
        tile_slot = st.empty()
        if cands:
            picked = st.pills("Logos to use", list(range(len(cands))), selection_mode="multi",
                              default=[i for i, c in enumerate(cands) if c["auto"]],
                              format_func=lambda i: f"{cands[i]['label']} · {cands[i]['conf']:.2f}",
                              key=f"logos_{dna['stem']}")
            ticked = [cands[i] for i in picked or []]
            tile_slot.markdown(ui.thumbs([{"image": c["image"], "caption": c["label"],
                                           "state": "on" if c in ticked else "off"} for c in cands], size=66),
                               unsafe_allow_html=True)
        else:
            ticked = []
        with st.popover("Add logos", icon=":material/add_photo_alternate:"):
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
            st.caption("Manual logo pick — the first is the certificate seal."
                       + (f" Plus {len(uploads)} uploaded." if uploads else ""))

with card_type:
    ui.card_title("text_fields", "Administrative Typography")
    font_label = st.selectbox("Primary Font", list(FONT_OPTIONS.keys()), disabled=not dna)
    weight = st.selectbox("Font Weight", FONT_WEIGHTS, index=FONT_WEIGHTS.index(700), disabled=not dna,
                          format_func=lambda w: f"{w} — {WEIGHT_NAMES[w]}")
    base = st.number_input("Base Size (px)", min_value=1.0, max_value=400.0, value=48.0, step=1.0,
                           disabled=not dna,
                           help="The certificate title's size; the whole type scale is built on it.")
    if dna:
        typography = {"family": FONT_OPTIONS[font_label], "weight": int(weight), "base_size": float(base)}
    st.caption("Checked against its JSON Schema before orchestration (p.43).")

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
target = formats[st.session_state["target_label"]]


def _canvas(meta: dict) -> tuple:
    return pipeline._derive_canvas(meta, None, None)


drawer = panel_col.container(key="ts_drawer") if panel_col is not None else None
if drawer is not None:
    with drawer:
        with st.container(horizontal=True, key="drawer_head"):
            ui.card_title("flag", "Target Initialization")
            st.button("", icon=":material/right_panel_close:", key="drawer_close", on_click=_toggle_panel,
                      help="Hide this panel (the top bar's Target button brings it back).")

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

schema = target["meta"].get("variable_schema", {})
canvas_w, canvas_h = _canvas(target["meta"])
domain = target["meta"].get("domain_context")

# Content payload (top row, right)
sample_path = _CONTENT_DATA_BY_DOMAIN.get(domain)
sample = json.load(open(sample_path)) if sample_path and os.path.exists(sample_path) else {}
content = {}
with card_content:
    with st.container(horizontal=True, key="content_head"):
        ui.card_title("edit_note", "Content Payload", _friendly(domain) if domain else "")
        with st.popover("", icon=":material/upload_file:", help="Load a JSON payload"):
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
    with st.container(border=False, key="content_fields"):
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
                    content[key] = st.text_area(label, key=wkey, height=68,
                                                max_chars=props.get("max_characters"))
                else:
                    content[key] = st.text_input(label, key=wkey, max_chars=props.get("max_characters"))

# Pre-orchestration schema validation (Chapter 3, p.43)
checks = {"typography": validate_typography(typography, canvas_w, canvas_h),
          "content": validate_content(content, target["meta"])}
problems = [f"{name}: {e}" for name, v in checks.items() for e in v["errors"]]
ready = dna is not None and not problems

if drawer is not None:
    with drawer:
        with st.expander(f"Required structural fields ({len(schema)})", icon=":material/schema:"):
            st.markdown('<div class="bn-chips">' + "".join(
                f'<span class="bn-chip">{props.get("instantiation_count", 1)}× {_friendly(var)} '
                f'<i>{props.get("structural_class")}</i></span>' for var, props in schema.items()) + "</div>",
                unsafe_allow_html=True)

        def _pick_gnn() -> None:
            st.session_state["use_gnn"] = st.session_state["gnn_toggle"]

        st.toggle("GNN-guided layout", value=st.session_state["use_gnn"], key="gnn_toggle", on_change=_pick_gnn,
                  help="Off: the no-GNN baseline (the naive stack the CSP builds on its own).")
        if problems:
            st.error("Schema validation — initialization would be rejected:\n\n"
                     + "\n".join(f"- {p}" for p in problems))
        else:
            st.success("Schema validation passed: typography and content payload conform.",
                       icon=":material/task_alt:")
        note = ("Extract the Visual DNA (bottom left) first." if dna is None else
                "Ready: <b>Initialize</b> (top right) runs Stages 1–6 and opens Step 2." if ready else
                "Fix the fields above, then <b>Initialize</b> (top right).")
        if dna is not None and st.session_state.get("orch") is not None:
            note += " It starts a new layout; the one you were editing stays saved in its session folder."
        st.markdown(f'<div class="ts-drawer-note">{note}</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# The top bar's actions: the target panel, and Initialize Orchestration
# ---------------------------------------------------------------------------
with actions:
    _, panel_btn, init_btn = st.columns([0.2, 1.25, 1.2], gap="small")
    short = st.session_state["target_label"].split(" (")[0]
    panel_btn.button(f"Target: {short}", on_click=_toggle_panel, width="stretch",
                     icon=":material/right_panel_close:" if panel_col is not None else ":material/right_panel_open:",
                     help=("Hide" if panel_col is not None else "Show") + " the target panel: format, structural "
                          "fields, GNN or baseline, schema validation.")
    reason = ("Extract the Visual DNA first." if dna is None else
              "Schema validation failed: " + "; ".join(problems) if problems else
              f"Run Stages 1-6 for the {short} and open Step 2.")
    clicked = init_btn.button("Initialize", icon=":material/play_arrow:", type="primary", disabled=not ready,
                              width="stretch", help=reason)

if clicked:
    out_dir = os.path.join(ui.SESSIONS_DIR, f"{time.strftime('%Y%m%d_%H%M%S')}_{dna['stem']}_{domain}")
    session = pipeline.OrchestrationSession(
        target["path"], template_image=master_path, content_data=content, typography=typography,
        use_gnn=st.session_state["use_gnn"], output_dir=out_dir, logo_images=logo_images,
        use_wordmark=use_wordmark, wordmark_path=wordmark_path, motif_paths=motif_paths,
        detected_nodes=dna["nodes"],
    )
    try:
        with notice, st.spinner("Running Stages 1-6 (instantiation → GNN → CSP → ranking → render → state chain)..."):
            session.run()
    except ValueError as e:
        notice.error(str(e))
    else:
        st.session_state["orch"] = session
        st.session_state["orch_master"] = master_path
        ui.go_to_step(2)
