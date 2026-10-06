"""
ThemeSync — shared dashboard components
=========================================
Pieces the dashboard pages share: the path bootstrap, one cached YOLO
detector for the whole app, cut-outs and thumbnails, the numbered-box poster
view used by every logo/motif picker, and SVG → PNG previews rendered with
the same Cairo + bundled-font path as the printed outputs.
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
