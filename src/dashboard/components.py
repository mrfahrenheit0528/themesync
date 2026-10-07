"""
ThemeSync — shared dashboard components
=========================================
Pieces the dashboard pages share: the path bootstrap, one cached YOLO
detector for the whole app, cut-outs and thumbnails, the numbered-box poster
view used by every logo/motif picker, SVG → PNG previews rendered with the
same Cairo + bundled-font path as the printed outputs, and the three-step
workflow (the step bar, the sidebar, and moving between steps).
"""

import hashlib
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

_STEP_CSS = """<style>
.ts-steps {display:flex; align-items:center; gap:.6rem; margin:.2rem 0 1.1rem;}
.ts-step {display:flex; align-items:center; gap:.55rem; padding:.45rem .9rem .45rem .5rem;
          border-radius:999px; border:1.5px solid rgba(128,128,128,.35);}
.ts-num {width:1.7rem; height:1.7rem; border-radius:50%; display:inline-flex; align-items:center;
         justify-content:center; font-weight:700; font-size:.9rem; background:rgba(128,128,128,.22);}
.ts-label {display:flex; flex-direction:column; line-height:1.15; font-size:.95rem;}
.ts-label small {font-size:.72rem; opacity:.75; text-transform:uppercase; letter-spacing:.04em;}
.ts-line {flex:1; height:2px; min-width:1rem; background:rgba(128,128,128,.35);}
.ts-active {border-color:#ff4b4b; background:rgba(255,75,75,.08);}
.ts-active .ts-num {background:#ff4b4b; color:#fff;}
.ts-active .ts-label {font-weight:700;}
.ts-done .ts-num {background:#21a35a; color:#fff;}
.ts-todo {opacity:.45;}
</style>"""


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


def step_bar(active: int) -> None:
    """The three steps across the top: done ✓, the current one highlighted,
    the rest greyed out."""
    cells = []
    for n, _, title, _ in STEPS:
        state = "done" if n < active else "active" if n == active else "todo"
        mark = "✓" if state == "done" else str(n)
        cells.append(f'<div class="ts-step ts-{state}"><span class="ts-num">{mark}</span>'
                     f'<span class="ts-label"><small>Step {n}</small>{title}</span></div>')
    st.markdown(_STEP_CSS + '<div class="ts-steps">' + '<div class="ts-line"></div>'.join(cells) + "</div>",
                unsafe_allow_html=True)


def enter_step(step: int) -> None:
    """Top of a step's page: a step opened out of turn (an old link, the
    address bar) goes to the current step instead; then the step bar."""
    now = current_step()
    if now != step:
        st.switch_page(STEPS[now - 1][1])
    step_bar(step)


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


def back_to_step_one(key: str) -> None:
    """A confirmed way back to Step 1: it closes the layout being edited."""
    session = st.session_state.get("orch")
    with st.popover("↺ Back to Step 1", width="stretch"):
        st.markdown("Going back closes this layout. Its files stay saved"
                    + (f" in `{os.path.relpath(session.output_dir, ROOT)}`" if session else "")
                    + "; initializing again starts a new layout.")
        if st.button("Yes, go back to Step 1", key=key, type="primary"):
            go_to_step(1)
