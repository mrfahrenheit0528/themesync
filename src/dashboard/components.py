"""
ThemeSync — shared dashboard components
=========================================
Pieces the dashboard pages share: the path bootstrap, one cached YOLO
detector for the whole app, cut-outs and thumbnails, the numbered-box poster
view used by every logo/motif picker, SVG → PNG previews rendered with the
same Cairo + bundled-font path as the printed outputs, and the three-step
workflow (the top bar with its steps, the sidebar, and moving between
steps), and the editor styling every page shares.
"""

import hashlib
import html
import os
import re
import sys

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(DASHBOARD_DIR)
ROOT = os.path.dirname(SRC)
for _sub in ("evaluation", "renderers", "models", "solvers", "data_preprocessing"):
    _p = os.path.join(SRC, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import rasterize                                   # noqa: E402 — first: Cairo gets the bundled fonts
import pipeline                                    # noqa: E402
from layout_extractor import LayoutExtractor       # noqa: E402
from stylistic_markers import cut_out              # noqa: E402

LABEL_FONT = os.path.join(ROOT, "assets", "fonts", "montserrat", "Montserrat-Bold.ttf")
UPLOAD_DIR = os.path.join(ROOT, "data", "raw", "dashboard_uploads")
SESSIONS_DIR = os.path.join(ROOT, "data", "rendered", "dashboard")

GREEN, RED = (0, 200, 90), (235, 50, 50)


def safe_name(name: str) -> str:
    base, ext = os.path.splitext(name)
    return re.sub(r"[^A-Za-z0-9_-]+", "_", base).strip("_") + ext.lower()


def save_upload(uploaded_file, directory: str = UPLOAD_DIR, prefix: str = "") -> str:
    """Writes a Streamlit upload to `directory` under a safe name; the
    content hash in the name keeps two different files called
    "poster.jpg" apart and makes re-saving the same file a no-op."""
    os.makedirs(directory, exist_ok=True)
    data = uploaded_file.getbuffer()
    digest = hashlib.sha1(data).hexdigest()[:8]
    base, ext = os.path.splitext(safe_name(uploaded_file.name))
    path = os.path.join(directory, f"{prefix}{base}_{digest}{ext}")
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(data)
    return path


@st.cache_resource(show_spinner="Loading the YOLO detector...")
def extractor():
    return LayoutExtractor(weights_path=pipeline.DEFAULT_YOLO_WEIGHTS)


@st.cache_data(show_spinner="Running Stage 0b (YOLO + OCR) on the master layout...")
def detect(path: str, mtime: float) -> list:
    return extractor().extract(path)


def detect_file(path: str) -> list:
    return detect(path, os.path.getmtime(path))


@st.cache_data(show_spinner=False)
def crop(path: str, mtime: float, bbox: tuple) -> Image.Image:
    with Image.open(path) as img:
        return cut_out(img, list(bbox))


def tile(img: Image.Image, size: int = 120) -> Image.Image:
    """An element on a neutral grey tile, so white and transparent marks show."""
    im = img.convert("RGBA")
    im.thumbnail((size, size))
    out = Image.new("RGBA", (size, size), (128, 128, 140, 255))
    out.alpha_composite(im, ((size - im.width) // 2, (size - im.height) // 2))
    return out.convert("RGB")


def logo_detections(poster_path: str, nodes: list) -> list:
    """
    Every logo Stage 0b detected on the master, numbered in reading order
    and cut out exactly as the pipeline cuts them; `auto` marks the logo row
    ThemeSync picks by itself (pipeline._select_logo_row) and `primary` the
    one it would use as the certificate seal.
    """
    mtime = os.path.getmtime(poster_path)
    with Image.open(poster_path) as img:
        height = img.height
    auto = pipeline._select_logo_row(nodes, height)
    auto_boxes = [tuple(n["bbox"]) for n in auto]
    primary_box = (tuple(max(auto, key=lambda n: n.get("detection_confidence", 0.0))["bbox"])
                   if auto else None)
    logos = sorted((n for n in nodes if n.get("semantic_category") == "logo"),
                   key=lambda n: (round(n["bbox"][1] / (0.05 * height)), n["bbox"][0]))
    out = []
    for k, n in enumerate(logos, start=1):
        box = tuple(n["bbox"])
        x, y = int(box[0]), int(box[1])
        out.append({
            "id": f"det_{x}_{y}", "label": f"#{k}", "kind": "detected", "bbox": box, "x": box[0],
            "conf": n.get("detection_confidence", 0.0), "auto": box in auto_boxes,
            "primary": box == primary_box, "image": crop(poster_path, mtime, box),
        })
    return out


def annotate(poster_path: str, boxes: list) -> Image.Image:
    """The poster with numbered boxes drawn on it: boxes = [(label, [x, y, w, h], rgb)]."""
    with Image.open(poster_path) as img:
        out = img.convert("RGB")
    draw = ImageDraw.Draw(out)
    line = max(3, out.width // 350)
    try:
        font = ImageFont.truetype(LABEL_FONT, max(18, out.width // 45))
    except OSError:
        font = ImageFont.load_default()
    for label, (x, y, w, h), colour in boxes:
        draw.rectangle([x, y, x + w, y + h], outline=colour, width=line)
        tx0, ty0, tx1, ty1 = draw.textbbox((0, 0), label, font=font)
        pad = line * 2
        lx, ly = x, max(0, y - (ty1 - ty0) - 2 * pad)
        draw.rectangle([lx, ly, lx + (tx1 - tx0) + 2 * pad, ly + (ty1 - ty0) + 2 * pad], fill=colour)
        draw.text((lx + pad - tx0, ly + pad - ty0), label, font=font, fill=(255, 255, 255))
    return out


def png_of(svg_path: str, scale: float = 1.0) -> str:
    """PNG preview of an SVG output, rendered by Cairo with the bundled
    fonts (what the printed packet shows), next to the SVG."""
    stem, _ = os.path.splitext(svg_path)
    png = f"{stem}@{scale:g}x.png"
    return rasterize.svg_to_png(svg_path, png, scale=scale)


def reader(path: str):
    """Deferred file read for st.download_button: large files load only
    when someone clicks download."""
    def read() -> bytes:
        with open(path, "rb") as f:
            return f.read()
    return read


# ---------------------------------------------------------------------------
# The workflow: one step at a time (the consultant's remark, 2026-09-29)
# ---------------------------------------------------------------------------

STEPS = [  # (number, page, title, icon)
    (1, "views/ingestion.py", "Perceptual Ingestion", "🧬"),
    (2, "views/orchestration.py", "Active Orchestration", "🧩"),
    (3, "views/report.py", "Evaluation Report", "📋"),
]
RESEARCH_PAGES = [("views/phase4.py", "Phase 4 Evaluation Set", "🗂️")]

# The look: laid out like a design tool such as Canva (the user's request,
# 2026-10-08), in ThemeSync's own colours: a navy bar and a coral accent.
# Colours and radii come from .streamlit/config.toml; this adds the layout
# pieces: the top bar, the grey workspace, the white side panel, the cards.
EDITOR_CSS = """<style>
[data-testid="stAppDeployButton"], [data-testid="stDecoration"] {display: none;}
[data-testid="stMain"] {background: #f4f5f8;}
[data-testid="stMainBlockContainer"] {padding: 0 1.75rem 2.5rem !important; max-width: 100%;}
h1, h2, h3 {letter-spacing: -0.01em;}

/* The bar across the top of every step, pinned while the page scrolls.
   Streamlit's own header (the sidebar's » and the ⋮ menu) floats over it:
   transparent, letting clicks through except on its buttons, drawn white. */
[data-testid="stHeader"], [data-testid="stHeader"] div {background: transparent; pointer-events: none !important;}
[data-testid="stHeader"] button, [data-testid="stHeader"] a,
[data-testid="stHeader"] [role="button"] {pointer-events: auto !important;}
[data-testid="stExpandSidebarButton"], [data-testid="stExpandSidebarButton"] *,
[data-testid="stMainMenuButton"], [data-testid="stMainMenuButton"] *,
[data-testid="stStatusWidget"], [data-testid="stStatusWidget"] * {color: #fff !important;}
[data-testid="stExpandSidebarButton"]:hover, [data-testid="stMainMenuButton"]:hover {
  background: rgba(255, 255, 255, .16) !important;}
[data-testid="stLayoutWrapper"]:has(> .st-key-ts_topbar) {position: sticky; top: 0; z-index: 1000;
  margin: 0 -1.75rem 1rem; width: calc(100% + 3.5rem) !important; max-width: none;}
.st-key-ts_topbar {background: linear-gradient(90deg, #13294b 0%, #1d3f6e 55%, #2a5a8c 100%);
  min-height: 60px; padding: 0 3.6rem 0 3.4rem; justify-content: center;
  box-shadow: 0 2px 12px rgba(19, 41, 75, .28);}
body:has([data-testid="stSidebar"][aria-expanded="true"]) .st-key-ts_topbar {padding-left: 1.4rem;}
.st-key-ts_topbar [data-testid="stMarkdownContainer"] p {margin: 0;}
.st-key-ts_topbar [data-testid="stElementContainer"] {overflow: visible;}
.st-key-ts_topbar button {background: rgba(255, 255, 255, .14) !important; color: #fff !important;
  border: 1px solid rgba(255, 255, 255, .34) !important; font-weight: 600; min-height: 2.25rem;}
.st-key-ts_topbar button:hover {background: rgba(255, 255, 255, .26) !important;}
.st-key-ts_topbar button p, .st-key-ts_topbar button span {color: inherit !important;}
.st-key-ts_topbar [data-testid="stBaseButton-primary"] {background: #fff !important;
  color: #13294b !important; border-color: #fff !important;}
.st-key-ts_topbar [data-testid="stBaseButton-primary"]:hover {background: #eef2f8 !important;}
.ts-brand {display: flex; align-items: center; gap: .6rem; color: #fff;}
.ts-logo {width: 2.1rem; height: 2.1rem; flex: none; border-radius: 10px; display: inline-flex;
  align-items: center; justify-content: center; font-weight: 800; font-size: 1.05rem;
  background: rgba(255, 255, 255, .22); border: 1px solid rgba(255, 255, 255, .35);}
.ts-brand b {font-size: 1.1rem; display: block; line-height: 1.15;}
.ts-brand > span:last-child {min-width: 0;}
.ts-brand small {display: block; font-size: .74rem; opacity: .9; line-height: 1.2; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis;}
.ts-steps {display: flex; align-items: center; justify-content: center; flex-wrap: nowrap; gap: .35rem;}
.ts-step {display: flex; align-items: center; gap: .4rem; padding: .24rem .75rem .24rem .26rem;
  border-radius: 999px; color: #fff; background: rgba(255, 255, 255, .12);
  border: 1px solid rgba(255, 255, 255, .28); white-space: nowrap;}
.ts-num {width: 1.45rem; height: 1.45rem; border-radius: 50%; display: inline-flex; align-items: center;
  justify-content: center; font-weight: 700; font-size: .8rem; background: rgba(255, 255, 255, .25);}
.ts-label {display: flex; flex-direction: column; line-height: 1.1; font-size: .86rem;}
.ts-label small {font-size: .6rem; opacity: .85; text-transform: uppercase; letter-spacing: .06em;}
.ts-line {width: 1.2rem; height: 2px; border-radius: 2px; background: rgba(255, 255, 255, .45);}
.ts-active {background: #fff; color: #13294b; border-color: #fff; box-shadow: 0 1px 4px rgba(0, 0, 0, .14);}
.ts-active .ts-num {background: #cf4836; color: #fff;}
.ts-active .ts-label {font-weight: 700;}
.ts-done .ts-num {background: #fff; color: #0f9d74;}
.ts-todo {opacity: .55;}
/* When the sidebar is open, or the window is narrow, the steps other than
   the current one show only their number (their name is the tooltip). */
body:has([data-testid="stSidebar"][aria-expanded="true"]) .ts-step:not(.ts-active) .ts-label {display: none;}
body:has([data-testid="stSidebar"][aria-expanded="true"]) .ts-step:not(.ts-active) {padding-right: .26rem;}
@media (max-width: 1380px) {
  .ts-step:not(.ts-active) .ts-label {display: none;}
  .ts-step:not(.ts-active) {padding-right: .26rem;}
}

/* Bento cards: any container keyed card_*, white on the grey page. In a
   .st-key-bento_grid row the cards share the row's height. */
[class*="st-key-card_"] {background: #fff; border: 1px solid #e4e7ec !important; border-radius: 16px !important;
  padding: 14px 16px 12px !important; box-shadow: 0 1px 2px rgba(16, 24, 40, .05);}
[class*="st-key-card_m_"] [data-testid="stMetricValue"] {font-size: 2rem; font-weight: 650; color: #13294b;}
[class*="st-key-bento_"] [data-testid="stColumn"] > [data-testid="stVerticalBlock"],
[data-testid="stColumn"]:has(.st-key-card_master) > [data-testid="stVerticalBlock"],
[data-testid="stColumn"]:has(.st-key-card_preview) > [data-testid="stVerticalBlock"] {height: 100%;}
[class*="st-key-bento_"] [data-testid="stColumn"] > [data-testid="stVerticalBlock"]
  > [data-testid="stLayoutWrapper"]:has(> [class*="st-key-card_"]) {height: 100%;}
[class*="st-key-bento_"] [data-testid="stColumn"] [class*="st-key-card_"] {height: 100%;}
[data-testid="stLayoutWrapper"]:has(> .st-key-card_master),
[data-testid="stLayoutWrapper"]:has(> .st-key-card_preview) {position: sticky; top: 76px;}
.st-key-card_master {min-height: calc(100vh - 100px);}
.st-key-card_master img {max-height: 64vh; object-fit: contain;}
[class*="st-key-bento_"] {gap: .7rem;}
.st-key-bento_tiles {margin-bottom: .2rem;}
.bn-group {display: flex; align-items: center; gap: .45rem; font-size: .7rem; font-weight: 700;
  letter-spacing: .08em; text-transform: uppercase; color: #5b6370; margin: .25rem 0 -.1rem;}
.bn-group::before {content: ""; width: .5rem; height: .5rem; border-radius: 2px; background: #cf4836;}
.bn-empty {color: #8a919c; font-size: .86rem; padding: .35rem 0 .2rem;}
.bn-swatches {display: flex; gap: .55rem;}
.bn-swatch {flex: 1; display: flex; flex-direction: column; gap: .15rem; min-width: 0;}
.bn-swatch span {height: 46px; border-radius: 10px; border: 1px solid rgba(0, 0, 0, .12);}
.bn-swatch small {font-size: .7rem; color: #5b6370;}
.bn-swatch code {font-size: .74rem; padding: 0; background: none; color: #0e1318;}
.bn-stats {display: grid; grid-template-columns: repeat(3, 1fr); gap: .5rem;}
.bn-stat {background: #f4f6f9; border-radius: 12px; padding: .55rem .65rem;}
.bn-stat small {display: block; font-size: .66rem; color: #5b6370; text-transform: uppercase; letter-spacing: .05em;}
.bn-stat b {display: block; font-size: 1.12rem; margin-top: .1rem; font-variant-numeric: tabular-nums;}
.bn-big {font-size: 1.9rem; font-weight: 750; line-height: 1.1; color: #13294b; margin-bottom: .35rem;}
.bn-big small {font-size: .82rem; font-weight: 500; color: #5b6370;}
.bn-chips {display: flex; flex-wrap: wrap; gap: .3rem;}
.bn-chip {font-size: .74rem; border-radius: 999px; padding: .08rem .55rem; background: #eef2f8; color: #1d3f6e;
  white-space: nowrap;}
.bn-chip i {font-style: normal; opacity: .65;}
.bn-nodes {display: flex; flex-direction: column; gap: .15rem; margin-top: .2rem;}
.bn-node {display: grid; grid-template-columns: 1fr auto auto; gap: .6rem; align-items: baseline;
  font-size: .8rem; padding: .22rem .1rem; border-bottom: 1px solid #f0f1f4;}
.bn-node b {font-weight: 600; color: #13294b; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;}
.bn-node span {color: #3c4250;}
.bn-node i {font-style: normal; color: #8a919c; font-variant-numeric: tabular-nums;}
.bn-ocr {font-size: .74rem; color: #6b7280; padding: 0 .1rem .2rem;}

/* Step 2: the grey workspace around the page, and the white side panel */
.st-key-ts_workspace {background: #e8eaee; border-radius: 16px; padding: 14px 18px 12px;}
.st-key-ts_panel {background: #fff; border: 1px solid #e4e7ec; border-radius: 16px;
  padding: .25rem 1rem 1rem; box-shadow: 0 1px 3px rgba(16, 24, 40, .06);}
.st-key-ts_panel button[role="tab"] p {font-weight: 650;}
.ts-section {font-size: .7rem; font-weight: 700; letter-spacing: .07em; text-transform: uppercase;
  color: #5b6370; margin: .55rem 0 .1rem;}
.ts-status {display: flex; flex-wrap: wrap; gap: .35rem; align-items: center; font-size: .8rem; color: #3c4250;}
.ts-pill {background: #fff; border: 1px solid #dcdfe5; border-radius: 999px; padding: .1rem .6rem;
  white-space: nowrap;}
.ts-pill.total {background: #fdecea; border-color: #f4c3bc; color: #a8322a; font-weight: 600;}
.ts-row {display: flex; align-items: baseline; gap: .45rem; font-size: .86rem; line-height: 1.3;}
.ts-row code {font-size: .78rem; background: #e8eef7; color: #1d3f6e; padding: .02rem .35rem; border-radius: 6px;}
.ts-row.now {font-weight: 650;}
.ts-badge {display: inline-block; font-size: .7rem; font-weight: 700; padding: .04rem .5rem;
  border-radius: 999px; background: #e8eef7; color: #1d3f6e; margin-right: .2rem;}
.ts-badge.rec {background: #e2f8f4; color: #08766a;}
.ts-badge.on {background: #cf4836; color: #fff;}
[class*="st-key-cand_"] {transition: box-shadow .15s, border-color .15s;}
[class*="st-key-cand_"]:hover {border-color: #e79a8f !important; box-shadow: 0 2px 12px rgba(207, 72, 54, .14);}
[class*="st-key-cand_on_"] {border: 2px solid #cf4836 !important;}
</style>"""


def theme() -> None:
    """The editor look, on every page (app.py calls it first)."""
    st.html(EDITOR_CSS)


def current_step() -> int:
    """The step the user is on. Steps 2 and 3 need an orchestrated layout,
    so without one it is Step 1."""
    step = st.session_state.get("step", 1)
    if step > 1 and st.session_state.get("orch") is None:
        step = 1
    st.session_state["step"] = step
    return step


def go_to_step(step: int) -> None:
    st.session_state["step"] = step
    st.switch_page(STEPS[step - 1][1])


def _step_pills(active: int) -> str:
    """The three steps: done ✓, the current one highlighted, the rest greyed
    out (the consultant's remark)."""
    cells = []
    for n, _, title, _ in STEPS:
        state = "done" if n < active else "active" if n == active else "todo"
        mark = "✓" if state == "done" else str(n)
        cells.append(f'<div class="ts-step ts-{state}" title="Step {n} · {title}">'
                     f'<span class="ts-num">{mark}</span><span class="ts-label">{title}</span></div>')
    return '<div class="ts-steps">' + '<div class="ts-line"></div>'.join(cells) + "</div>"


def top_bar(active: int, subtitle: str = "", tool: str = None):
    """The bar across the top of a page, like a design tool's header: the
    brand and the design being edited, the three steps (or, on a research
    tool's page, the tool's name), and an empty column that the page fills
    with its actions (returned)."""
    with st.container(key="ts_topbar"):
        brand, steps, actions = st.columns([1.25, 2.7, 2.05], vertical_alignment="center", gap="small")
        brand.markdown(f'<div class="ts-brand"><span class="ts-logo">T</span><span><b>ThemeSync</b>'
                       + (f'<small title="{html.escape(subtitle)}">{html.escape(subtitle)}</small>' if subtitle else "")
                       + "</span></div>", unsafe_allow_html=True)
        steps.markdown(_step_pills(active) if tool is None else
                       f'<div class="ts-steps"><div class="ts-step ts-active"><span class="ts-num">R</span>'
                       f'<span class="ts-label">{html.escape(tool)}</span></div></div>', unsafe_allow_html=True)
    return actions


def design_name(session) -> str:
    """The design being edited, for the top bar: its format, the master
    poster it takes its theme from (upload hash dropped), and the mode."""
    if session is None:
        return ""
    poster = os.path.splitext(os.path.basename(session.template_image or ""))[0]
    poster = re.sub(r"_[0-9a-f]{8}$", "", poster) or "no master"
    return (f"{session.domain.replace('_', ' ').title()} · {poster} · "
            f"{'GNN-guided' if session.use_gnn else 'no-GNN baseline'}")


def enter_step(step: int, subtitle: str = ""):
    """Top of a step's page: a step opened out of turn (an old link, the
    address bar) goes to the current step instead; then the top bar.
    Returns the bar's actions column."""
    now = current_step()
    if now != step:
        st.switch_page(STEPS[now - 1][1])
    return top_bar(step, subtitle)


def sidebar() -> None:
    """The workflow's steps, only the current one enabled, then the
    research tools, which sit outside the workflow."""
    now = current_step()
    with st.sidebar:
        st.markdown("**Workflow**")
        for n, page, title, icon in STEPS:
            st.page_link(page, label=f"Step {n} · {title}", icon=icon, disabled=n != now)
        st.caption("One step at a time. The buttons on each page move you on or back.")
        st.markdown("**Research tools**")
        for page, title, icon in RESEARCH_PAGES:
            st.page_link(page, label=title, icon=icon)


def back_to_step_one(key: str, label: str = "Step 1") -> None:
    """A confirmed way back to Step 1: it closes the layout being edited."""
    session = st.session_state.get("orch")
    with st.popover(label, icon=":material/undo:", width="stretch", help="Back to Step 1"):
        st.markdown("Going back closes this layout. Its files stay saved"
                    + (f" in `{os.path.relpath(session.output_dir, ROOT)}`" if session else "")
                    + "; initializing again starts a new layout.")
        if st.button("Yes, go back to Step 1", key=key, type="primary"):
            go_to_step(1)
