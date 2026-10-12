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

import base64
import functools
import hashlib
import html
import io
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
from stylistic_markers import cover, cut_out       # noqa: E402

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


def data_uri(img: Image.Image, fmt: str = "PNG") -> str:
    """An image as a data: URI, for pictures drawn in HTML (thumbnails)."""
    buf = io.BytesIO()
    if fmt == "JPEG":
        img.convert("RGB").save(buf, "JPEG", quality=85, optimize=True)
    else:
        img.save(buf, "PNG", optimize=True)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(buf.getvalue()).decode()


def thumbs(items: list, size: int = 72) -> str:
    """
    Thumbnails as an HTML grid with gaps between them (st.image draws a
    list of images edge to edge). Each item is a dict:
      image    a PIL image
      caption  the text under it
      state    "on" (picked: a coral ring) or "off" (dimmed); optional
      kind     "mark": a cut-out shown whole on a checkerboard, so white
               and transparent parts show (logos, title artwork, motifs);
               "photo": cropped to fill a wide tile (the background)
    Returns the HTML for st.markdown(..., unsafe_allow_html=True).
    """
    cells = []
    for item in items:
        kind = item.get("kind", "mark")
        if kind == "photo":
            uri = data_uri(cover(item["image"].convert("RGB"), int(size * 3.2), size * 2), "JPEG")
        else:
            im = item["image"].convert("RGBA")
            im.thumbnail((size * 2, size * 2))
            uri = data_uri(im)
        cells.append(f'<figure class="ts-thumb {kind} {item.get("state") or ""}"><div class="ts-frame">'
                     f'<img src="{uri}" alt=""></div><figcaption>{html.escape(item.get("caption", ""))}'
                     f"</figcaption></figure>")
    return f'<div class="ts-thumbs" style="--s:{size}px">' + "".join(cells) + "</div>"


def card_title(icon: str, title: str, meta: str = "") -> None:
    """A card's heading: a tinted Material icon, the title, and an optional
    note on the right (a count, the pipeline stage)."""
    st.markdown(f":material/{icon}: **{html.escape(title)}**"
                + (f' <span class="ts-meta">{html.escape(meta)}</span>' if meta else ""),
                unsafe_allow_html=True)


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
# Fonts: the bundled families, each shown in its own typeface (notes §3.53)
# ---------------------------------------------------------------------------

FONT_DIR = os.path.join(ROOT, "assets", "fonts")
# label → (the family stack the renderer writes into the SVG, its folder in
# assets/fonts/). Every family ships in the repo (src/renderers/
# build_fonts.py), so the canvas, the thumbnails and the PNG/PDF exports
# draw the same typeface on the server and on Windows. Tinos, metrically
# compatible with Times New Roman, replaces it: Times New Roman can't be
# bundled and isn't on the server.
FONTS = {
    "Montserrat (default)": (pipeline.DEFAULT_TYPOGRAPHY["family"], "montserrat"),
    "Lato":                 ("Lato, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", "lato"),
    "Open Sans":            ("'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                             "opensans"),
    "Playfair Display":     ("'Playfair Display', Georgia, 'Times New Roman', serif", "playfairdisplay"),
    "Merriweather":         ("Merriweather, Georgia, serif", "merriweather"),
    "Tinos":                ("Tinos, 'Times New Roman', Times, serif", "tinos"),
}
FONT_FACES = {"Regular": (400, "normal"), "Italic": (400, "italic"), "SemiBold": (600, "normal"),
              "Bold": (700, "normal"), "BoldItalic": (700, "italic"), "ExtraBold": (800, "normal"),
              "Black": (900, "normal")}


def first_family(stack: str) -> str:
    """'Open Sans' from "'Open Sans', -apple-system, ..."."""
    return (stack or "").split(",")[0].strip().strip("'\" ")


def font_folder(stack: str):
    """The assets/fonts/ folder of a stack's first family, or None."""
    folder = first_family(stack).replace(" ", "").lower()
    return folder if folder and os.path.isdir(os.path.join(FONT_DIR, folder)) else None


def font_label(stack: str) -> str:
    """The picker's label for a family stack (its first family otherwise)."""
    for label, (s, folder) in FONTS.items():
        if s == stack or folder == font_folder(stack):
            return label
    return first_family(stack) or "Montserrat (default)"


def font_faces(folder: str) -> list:
    """[(ttf path, weight, style)] of a bundled family's faces, which are
    named <Family>-<Face>.ttf (Montserrat-BoldItalic.ttf)."""
    directory = os.path.join(FONT_DIR, folder)
    files = {f.rsplit("-", 1)[-1][:-4]: os.path.join(directory, f)
             for f in os.listdir(directory) if f.lower().endswith(".ttf")} if os.path.isdir(directory) else {}
    return [(files[name], weight, style) for name, (weight, style) in FONT_FACES.items() if name in files]


def _woff(ttf: str, text: str = None) -> bytes:
    """A WOFF of `ttf` cut down to `text` (or to Latin script)."""
    from fontTools import subset
    from fontTools.ttLib import TTFont

    options = subset.Options()
    options.flavor = "woff"
    options.layout_features = ["kern", "liga"]
    font = TTFont(ttf)
    subsetter = subset.Subsetter(options)
    if text:
        subsetter.populate(text=text)
    else:
        subsetter.populate(unicodes=[*range(0x20, 0x7F), *range(0xA0, 0x250), *range(0x1E00, 0x1F00),
                                     *range(0x2000, 0x2070), 0x20AC, 0x2122])
    subsetter.subset(font)
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


@functools.lru_cache(maxsize=1)
def font_preview_css() -> str:
    """@font-face rules that draw each picker label in its own family: one
    face per family, cut down to the label's letters (a few KB each)."""
    rules = []
    for label, (_, folder) in FONTS.items():
        faces = {(weight, style): path for path, weight, style in font_faces(folder)}
        path = faces.get((400, "normal")) or faces.get((600, "normal"))
        if not path:
            continue
        b64 = base64.b64encode(_woff(path, label)).decode("ascii")
        rules.append(f'@font-face {{font-family: "TS {folder}"; font-weight: 400; '
                     f'src: url(data:font/woff;base64,{b64}) format("woff");}}')
    return "\n".join(rules)


def _pick_font(state_key: str, label: str, popover_key: str) -> None:
    st.session_state[state_key] = label
    st.session_state[popover_key] = False          # close the list


def font_picker(key: str, label: str, current: str) -> str:
    """A dropdown that shows every font in its own typeface (Streamlit's
    selectbox can't style its options one by one). `current` is a family
    stack; returns the chosen one. Picking a font closes the list through
    the popover's keyed open state."""
    state_key = f"{key}_font"
    st.session_state.setdefault(state_key, font_label(current))
    chosen = st.session_state[state_key]
    if chosen not in FONTS:
        chosen = st.session_state[state_key] = font_label(current)
    css = [f'.st-key-{key}_font_btn button p {{font-family: "TS {FONTS[chosen][1]}", sans-serif;}}']
    css += [f'.st-key-{key}_font_opt_{folder} button p {{font-family: "TS {folder}", sans-serif; '
            f'font-size: 1rem;}}' for _, folder in FONTS.values()]
    # The label and the button share one gapless container, so the button
    # sits under its label as a selectbox does
    with st.container(key=f"{key}_font_btn", gap=None):
        st.markdown(f"<style>{font_preview_css()}\n{''.join(css)}</style>"
                    f'<div class="ts-wlabel">{html.escape(label)}</div>', unsafe_allow_html=True)
        with st.popover(chosen, width="stretch", key=f"{key}_font_pop", on_change="rerun"):
            for option, (_, folder) in FONTS.items():
                st.button(option, key=f"{key}_font_opt_{folder}", width="stretch",
                          type="primary" if option == chosen else "tertiary",
                          on_click=_pick_font, args=(state_key, option, f"{key}_font_pop"))
    return FONTS[chosen][0]


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
[data-testid="stMainBlockContainer"] {padding: 0 1.75rem 1rem !important; max-width: 100%;}
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
.st-key-ts_topbar button:disabled {opacity: .5; cursor: not-allowed;}
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
[class*="st-key-bento_"] [data-testid="stColumn"] > [data-testid="stVerticalBlock"] {height: 100%;}
[class*="st-key-bento_"] [data-testid="stColumn"] > [data-testid="stVerticalBlock"]
  > [data-testid="stLayoutWrapper"]:has(> [class*="st-key-card_"]) {height: 100%;}
[class*="st-key-bento_"] [data-testid="stColumn"] [class*="st-key-card_"] {height: 100%;}
/* Step 3 (Evaluation Report): the evaluated layout fixed on the left at the
   window's height, the report scrolling on the right; the page itself
   doesn't scroll (user's request, 2026-10-09, notes §3.39) */
.st-key-card_preview {height: var(--ts-avail) !important; flex: none !important; overflow: hidden;
  flex-wrap: nowrap;}
.st-key-card_preview > * {flex-shrink: 0;}
.st-key-card_preview [data-testid="stImage"] img {max-height: calc(var(--ts-avail) - 255px);
  width: auto !important; max-width: 100%; object-fit: contain; margin: 0 auto; display: block;
  border-radius: 6px; box-shadow: 0 4px 16px rgba(16, 24, 40, .18);}
.st-key-card_preview [data-testid="stFullScreenFrame"] {display: flex; justify-content: center;}
.st-key-report_scroll {height: var(--ts-avail); overflow-y: auto; overflow-x: hidden; flex: none !important;
  flex-wrap: nowrap; scrollbar-width: thin; padding-right: .45rem; gap: .7rem;}
.st-key-report_scroll > * {flex-shrink: 0;}
[class*="st-key-bento_"] {gap: .7rem;}

/* Card headings (ui.card_title): a tinted icon, the title, a note on the right */
[class*="st-key-card_"] p:has(> [data-testid="stIconMaterial"]:first-child) {display: flex; align-items: center;
  gap: .5rem; margin: 0; font-size: .97rem; color: #13294b;}
[class*="st-key-card_"] p > [data-testid="stIconMaterial"]:first-child {color: #cf4836; background: #fdecea;
  border-radius: 8px; padding: 4px; font-size: 1.05rem;}
.ts-meta {margin-left: auto; font-size: .68rem; font-weight: 650; color: #5b6370; background: #f1f3f6;
  border-radius: 999px; padding: .12rem .55rem; white-space: nowrap; letter-spacing: .02em;}

/* Thumbnails (ui.thumbs): a grid with gaps, rounded tiles, captions */
.ts-thumbs {display: flex; flex-wrap: wrap; gap: 10px; margin: .1rem 0 .4rem;}
.ts-thumb {margin: 0; display: flex; flex-direction: column; align-items: center; gap: 4px;}
.ts-frame {position: relative; width: var(--s); height: var(--s); border-radius: 12px; overflow: hidden;
  display: flex; align-items: center; justify-content: center; border: 1px solid #dfe3ea;
  background: repeating-conic-gradient(#8b919d 0 25%, #9ba1ac 0 50%) 50% / 12px 12px;
  box-shadow: 0 1px 2px rgba(16, 24, 40, .08); transition: box-shadow .15s, opacity .15s;}
.ts-frame img {max-width: 86%; max-height: 86%; object-fit: contain;}
.ts-thumb.photo .ts-frame {width: calc(var(--s) * 1.6);}
.ts-thumb.photo .ts-frame img {width: 100%; height: 100%; max-width: none; max-height: none; object-fit: cover;}
.ts-thumb figcaption {font-size: .7rem; color: #5b6370; line-height: 1.1; max-width: calc(var(--s) * 1.6);
  text-align: center;}
.ts-thumb.on .ts-frame {box-shadow: 0 0 0 2px #fff, 0 0 0 4px #cf4836;}
.ts-thumb.on .ts-frame::after {content: "✓"; position: absolute; top: 4px; right: 4px; width: 18px; height: 18px;
  border-radius: 50%; background: #cf4836; color: #fff; font-size: 11px; font-weight: 800;
  display: flex; align-items: center; justify-content: center;}
.ts-thumb.off .ts-frame {opacity: .4;}

/* Step 1 (Perceptual Ingestion), from the user's mockups A1-A3: the master
   layout on the left, three cards stacked on the right, all inside one
   screen (a card whose content runs longer scrolls inside itself), and
   the target panel as an overlay that moves nothing. Heights are set from
   one variable, so the parts always add up to the window. */
:root {--ts-avail: max(560px, calc(100vh - 110px)); --ts-assets-max: calc(var(--ts-avail) * .42);}
.st-key-card_master, .st-key-right_stack, .st-key-card_assets, .st-key-card_type {flex: none !important;}
.st-key-card_master, .st-key-right_stack {height: var(--ts-avail) !important;}
.st-key-right_stack {gap: .75rem !important; flex-wrap: nowrap;}
/* On the right, the logos/markers card and the typography take what they
   need (the first up to a cap, its tiles scrolling beyond it); the content
   payload takes the rest of the column. */
.st-key-card_assets {max-height: var(--ts-assets-max);}
.st-key-right_stack > [data-testid="stLayoutWrapper"]:has(> .st-key-card_content) {flex: 1 1 0 !important;
  min-height: 180px;}
.st-key-card_content {flex: 1 1 auto !important; height: 100%; min-height: 0;}
.st-key-card_content > [data-testid="stLayoutWrapper"]:has(> .st-key-content_fields) {flex: 1 1 0 !important;
  min-height: 0;}
.st-key-card_master, .st-key-card_assets, .st-key-card_type, .st-key-card_content {overflow: hidden;
  flex-wrap: nowrap; gap: .6rem;}
.st-key-card_master > *, .st-key-card_assets > *, .st-key-card_content > * {flex-shrink: 0;}
/* Headings with icon buttons on the right */
.st-key-master_head, .st-key-content_head, .st-key-drawer_head {flex-wrap: nowrap !important; align-items: center;}
.st-key-master_head > :first-child, .st-key-content_head > :first-child,
.st-key-drawer_head > :first-child {flex: 1 1 auto; min-width: 0;}
.st-key-master_head button, .st-key-content_head button, .st-key-drawer_head button {min-height: 2.1rem;
  padding: .15rem .55rem; border-radius: 999px;}
.st-key-ts_drawer p:has(> [data-testid="stIconMaterial"]:first-child) {display: flex; align-items: center;
  gap: .5rem; margin: 0; font-size: 1.05rem; color: #13294b;}
.st-key-ts_drawer p > [data-testid="stIconMaterial"]:first-child {color: #cf4836; background: #fdecea;
  border-radius: 8px; padding: 4px; font-size: 1.05rem;}
/* The master layout: the preview (or upload area), its tools, and beneath
   it Extract (A1) or the K-Means and SIFT results (A2) */
.st-key-master_view {position: relative;}
.ts-poster {display: flex; align-items: center; justify-content: center; border-radius: 14px;
  background: radial-gradient(circle at 50% 35%, #f7f8fb, #e7eaf0); overflow: hidden;
  height: calc(var(--ts-avail) - 166px); border: 1px solid #e4e7ec;}
.ts-poster.a2 {height: calc(var(--ts-avail) - 226px);}
.ts-poster img {max-width: 92%; max-height: 92%; object-fit: contain; border-radius: 6px;
  box-shadow: 0 6px 22px rgba(16, 24, 40, .22);}
.st-key-master_view > [data-testid="stLayoutWrapper"]:has(> .st-key-preview_tools) {position: absolute;
  top: 10px; right: 10px; z-index: 3; width: auto !important;}
.st-key-preview_tools button {background: rgba(255, 255, 255, .94); border-color: #dfe3ea;
  box-shadow: 0 2px 8px rgba(16, 24, 40, .15); min-height: 2.1rem; padding: .15rem .5rem;}
.st-key-master_drop [data-testid="stFileUploaderDropzone"] {height: calc(var(--ts-avail) - 166px);
  flex-direction: column; justify-content: center; align-items: center; gap: .9rem; text-align: center;
  border: 2px dashed #e6a59c; background: #fdf6f5; border-radius: 14px;}
.st-key-master_drop [data-testid="stFileUploaderDropzone"] > * {flex: 0 0 auto !important; margin: 0 !important;}
.st-key-master_drop [data-testid="stFileUploaderDropzone"]::before {content: "⬆"; font-size: 3.2rem;
  line-height: 1; color: #cf4836;}
.ts-swatches {display: flex; gap: .45rem;}
.ts-swatch {flex: 1; min-width: 0; display: flex; flex-direction: column; gap: .2rem;}
.ts-swatch span {height: 42px; border-radius: 10px; border: 1px solid rgba(0, 0, 0, .12);}
.ts-swatch code {font-size: .66rem; background: none; padding: 0; color: #3c4250; text-align: center;}
.ts-stats {display: grid; grid-template-columns: repeat(3, 1fr); gap: .45rem;}
.ts-stat {background: #f4f6f9; border-radius: 10px; padding: .45rem .4rem; text-align: center; min-width: 0;}
.ts-stat small {display: block; font-size: .6rem; text-transform: uppercase; letter-spacing: .05em; color: #5b6370;}
.ts-stat b {display: block; font-size: .86rem; font-variant-numeric: tabular-nums; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis;}
.st-key-card_master [data-testid="stCaptionContainer"] {font-size: .72rem;}
/* Logos and stylistic markers: pickable tiles above the card's buttons */
.st-key-logo_grid, .st-key-marker_grid, .st-key-content_fields, .st-key-logo_tiles, .st-key-marker_tiles,
[class*="st-key-tile_"] {flex: none !important;}
/* 6px of padding inside the scrolling tile area keeps the picked ring
   (drawn outside the tile) from being clipped; the negative margin keeps
   the tiles aligned with the title */
.st-key-logo_grid, .st-key-marker_grid {max-height: calc(var(--ts-assets-max) - 118px); overflow-y: auto;
  overflow-x: hidden; scrollbar-width: thin; gap: .45rem; align-content: flex-start;
  padding: 6px 6px 2px; margin: -6px -6px 0;}
/* The two halves' buttons line up along the card's foot */
.st-key-card_assets [data-testid="stHorizontalBlock"] {align-items: stretch;}
.st-key-card_assets [data-testid="stColumn"] > [data-testid="stVerticalBlock"],
.st-key-card_assets [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"],
.st-key-assets_logos, .st-key-assets_markers {height: 100%;}
.st-key-assets_logos > [data-testid="stLayoutWrapper"]:has(> .st-key-logos_btn),
.st-key-assets_markers > [data-testid="stLayoutWrapper"]:has(> .st-key-markers_btn) {margin-top: auto;}
.st-key-logo_tiles, .st-key-marker_tiles {gap: .6rem .7rem !important;}
[class*="st-key-tile_"] {align-items: center; gap: .15rem !important;}
[class*="st-key-tile_"] .ts-thumbs {margin: 0;}
[class*="st-key-tile_"] [data-testid="stCheckbox"] label p {font-size: .72rem; color: #3c4250;}
/* Drop an image on a tile to replace it (notes §3.53): a transparent upload
   area over the picture, shown on hover; the ↺ button on the tile's corner */
[class*="st-key-tile_"] {position: relative; --tile-w: 60px;}
.st-key-tile_background {--tile-w: 96px;}
[class*="st-key-tile_"] [data-testid="stElementContainer"]:has([data-testid="stFileUploader"]) {
  position: absolute !important; top: .1rem; left: calc(50% - var(--tile-w) / 2); width: var(--tile-w) !important;
  min-width: 0 !important; max-width: var(--tile-w); height: 60px; z-index: 4; margin: 0; overflow: hidden;}
[class*="st-key-tile_"] [data-testid="stFileUploader"],
[class*="st-key-tile_"] [data-testid="stFileUploader"] > section {height: 100%; width: 100%; min-width: 0;}
[class*="st-key-tile_"] [data-testid="stFileUploaderDropzone"] {width: 100%; min-width: 0;}
[class*="st-key-tile_"] [data-testid="stFileUploaderDropzone"] {position: relative; height: 100%; min-height: 0;
  padding: 0; border-radius: 12px; border: 2px dashed #e8735a; background: rgba(255, 246, 243, .9);
  opacity: 0; transition: opacity .12s; cursor: copy;}
[class*="st-key-tile_"] [data-testid="stFileUploaderDropzone"]:hover {opacity: 1;}
[class*="st-key-tile_"] [data-testid="stFileUploaderDropzone"] > * {opacity: 0;}
[class*="st-key-tile_"] [data-testid="stFileUploaderDropzone"]::after {content: "Drop or click to replace";
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; text-align: center;
  font-size: .6rem; font-weight: 650; line-height: 1.15; color: #b5452c; padding: .2rem; pointer-events: none;}
[class*="st-key-tile_"] [data-testid="stFileUploader"] > :not(section),
[class*="st-key-tile_"] [data-testid="stFileUploaderFile"] {display: none !important;}
[class*="st-key-tile_"] [class*="st-key-revert_"] {position: absolute !important; top: -.35rem;
  left: calc(50% - var(--tile-w) / 2 - .45rem); z-index: 5; width: auto !important; margin: 0;}
[class*="st-key-revert_"] button {min-height: 1.5rem; height: 1.5rem; width: 1.5rem; padding: 0; border-radius: 50%;
  background: #fff !important; border: 1px solid #e4e7ec !important; box-shadow: 0 1px 3px rgba(16, 24, 40, .18);}
.ts-thumb figcaption:empty {display: none;}
.ts-thumb.photo figcaption {max-width: none; white-space: nowrap;}
.ts-note {font-size: .74rem; color: #5b6370;}
.ts-placeholder {color: #8a919c; font-size: .82rem; padding: .7rem .8rem; border: 1px dashed #d6dae1;
  border-radius: 12px; background: #fafbfc; line-height: 1.35;}
/* Typography in one row; the content payload in two columns */
.st-key-card_type [data-testid="stWidgetLabel"] p, .st-key-card_content [data-testid="stWidgetLabel"] p {
  font-size: .76rem; color: #3c4250;}
.st-key-merge_note {gap: .35rem !important; flex: none !important; background: #fff6f3; border-radius: 8px;
  padding: .15rem .2rem .15rem .55rem;}
.st-key-merge_note [data-testid="stElementContainer"]:has([data-testid="stMarkdownContainer"]) {flex: 1;}
.st-key-merge_note button {min-height: 1.7rem; padding: 0 .35rem;}
.st-key-content_fields {height: 100%; overflow-y: auto; scrollbar-width: thin;
  padding-right: .3rem; gap: .35rem;}
/* Streamlit pulls the element after a markdown block up by 1rem (its
   paragraphs' margin); the page's HTML blocks have none, so it overlapped */
:is(.st-key-card_master, .st-key-card_assets, .st-key-card_type, .st-key-card_content, .st-key-ts_drawer,
     [role="dialog"])
  [data-testid="stMarkdownContainer"]:has(> div[class^="ts-"], > div[class^="bn-"]) {margin-bottom: 0 !important;}
/* The font picker (ui.font_picker): a label like a widget's, a button like
   a selectbox, and a list where each font is drawn in its own typeface */
.ts-wlabel {font-size: .875rem; color: #31333f; line-height: 1.6; margin: 0 0 .25rem;}
.st-key-card_type .ts-wlabel {font-size: .76rem; color: #3c4250; margin-bottom: 7px; padding-top: 2px;}
[class*="_font_btn"] [data-testid="stMarkdownContainer"]:has(> .ts-wlabel) {margin-bottom: 0 !important;}
/* Measured from the selectbox beside it: #f4f5f7, 1px #e0e2e7, 8px corners,
   40px tall, 14px regular text 8px in, a dark chevron on the right */
[class*="_font_btn"] button {background: #f4f5f7 !important; border: 1px solid #e0e2e7 !important;
  border-radius: 8px; height: 40px; min-height: 40px; padding: 0 .4rem 0 .5rem !important;
  color: #0e1318 !important; box-shadow: none !important;}
[class*="_font_btn"] button:hover, [class*="_font_btn"] button:focus-visible {border-color: #c3c8d0 !important;
  color: #0e1318 !important;}
[class*="_font_btn"] button > div {width: 100%; justify-content: space-between;}
[class*="_font_btn"] button [data-testid="stMarkdownContainer"] {flex: 1; min-width: 0; text-align: left;}
[class*="_font_btn"] button p {white-space: nowrap; overflow: hidden; text-overflow: ellipsis; text-align: left;
  font-size: 14px; font-weight: 400;}
[class*="_font_btn"] button > div > div:first-child {flex: 1; min-width: 0; display: flex;
  justify-content: flex-start;}
[class*="_font_btn"] button [data-testid="stIconMaterial"] {color: #31333f; font-size: 1.25rem;}
[role="dialog"] [data-testid="stImage"] img {max-height: 66vh; object-fit: contain;}
.ts-legend {display: flex; flex-wrap: wrap; gap: .25rem .6rem; font-size: .72rem; color: #5b6370;}
.ts-legend i {display: inline-block; width: .6rem; height: .6rem; border-radius: 2px; margin-right: .25rem;}
/* The target panel (A3): an overlay under the top bar; Initialize at its foot */
[data-testid="stLayoutWrapper"]:has(> .st-key-ts_drawer) {position: fixed !important; top: 60px; right: 0;
  bottom: 0; width: min(400px, 94vw) !important; z-index: 990; margin: 0 !important;}
.st-key-ts_drawer {height: 100%; background: #fff; border-left: 1px solid #e4e7ec;
  box-shadow: -14px 0 34px rgba(16, 24, 40, .18); padding: 20px 22px 18px !important; overflow-y: auto;
  scrollbar-width: thin; flex-wrap: nowrap; gap: .85rem; animation: ts-slide .2s ease-out;}
@keyframes ts-slide {from {transform: translateX(32px); opacity: 0;} to {transform: none; opacity: 1;}}
.st-key-ts_drawer [data-testid="stRadio"] label p {font-weight: 600;}
/* The layout's elements (notes §3.54): two compact columns of checkboxes */
.st-key-node_picks {gap: .3rem !important;}
.st-key-node_picks [data-testid="stColumn"] > [data-testid="stVerticalBlock"] {gap: .15rem !important;}
.st-key-node_picks [data-testid="stCheckbox"] label p {font-size: .8rem;}
.st-key-node_picks [data-testid="stCaptionContainer"] {margin-bottom: -.1rem;}
.st-key-ts_drawer > [data-testid="stLayoutWrapper"]:has(> .st-key-drawer_cta) {margin-top: auto;}
.st-key-drawer_cta {border-top: 1px solid #eef0f3; padding-top: .85rem; gap: .5rem;}
.st-key-drawer_cta button {min-height: 2.9rem; font-size: 1rem; font-weight: 650;}
.st-key-bento_tiles {margin-bottom: .2rem;}
.bn-group {display: flex; align-items: center; gap: .45rem; font-size: .7rem; font-weight: 700;
  letter-spacing: .08em; text-transform: uppercase; color: #5b6370; margin: .25rem 0 -.1rem;}
.bn-group::before {content: ""; width: .5rem; height: .5rem; border-radius: 2px; background: #cf4836;}
.bn-empty {color: #8a919c; font-size: .84rem; padding: .7rem .8rem; border: 1px dashed #d6dae1;
  border-radius: 12px; background: #fafbfc; line-height: 1.35;}
.bn-swatches {display: flex; gap: .55rem;}
.bn-swatch {flex: 1; display: flex; flex-direction: column; gap: .15rem; min-width: 0;}
.bn-swatch span {height: 46px; border-radius: 10px; border: 1px solid rgba(0, 0, 0, .12);}
.st-key-card_colours .bn-swatch span {height: 34px;}
.st-key-card_colours .bn-swatches {margin-bottom: .25rem;}
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

/* Step 2 (Active Orchestration), on one screen (user's request, 2026-10-09,
   notes §3.38): the canvas on a grey workspace with the Recommendation
   Engine's strip beneath it, the white side panel on the right. The canvas
   component sizes its page from --ts-canvas-h. */
.st-key-ts_workspace {background: #e8eaee; border-radius: 16px; padding: 14px 18px;
  height: calc(100vh - 252px); min-height: 380px; justify-content: center; flex: none !important;
  --ts-canvas-h: max(352px, calc(100vh - 282px));}
.st-key-ts_panel {background: #fff; border: 1px solid #e4e7ec; border-radius: 16px;
  padding: .4rem 1rem 1rem; box-shadow: 0 1px 3px rgba(16, 24, 40, .06);
  height: calc(100vh - 110px); min-height: 520px; overflow-y: auto; scrollbar-width: thin;
  flex: none !important; flex-wrap: nowrap; gap: .55rem;}
.st-key-ts_panel > * {flex-shrink: 0;}
/* Style tools (notes §3.53): colour swatches as round buttons */
[class*="st-key-swatches_"] {flex-wrap: wrap !important; gap: .4rem !important;}
[class*="st-key-sw_"] button {width: 1.75rem; height: 1.75rem; min-height: 1.75rem !important; padding: 0;
  border-radius: 50%; border: 1.5px solid #d0d5dd;}
[class*="st-key-sw_"] button p {font-size: 0 !important;}
[class*="st-key-sw_"] button:hover {box-shadow: 0 0 0 2px #fff, 0 0 0 4px #e8735a;}
[class*="st-key-swatches_"] [data-testid="stColorPicker"] {width: auto;}
.st-key-sel_head {flex-wrap: nowrap !important; align-items: center;}
.st-key-sel_head button {min-height: 2.1rem; padding: .15rem .5rem;}
.st-key-sel_head > :last-child {flex: 1 1 auto; min-width: 0;}
.ts-selname {display: flex; align-items: center; flex-wrap: wrap; gap: .35rem .5rem; padding-left: .35rem;
  border-left: 1px solid #e3e5e8; font-size: .92rem;}
.ts-selname b {color: #13294b;}
.ts-muted {color: #8a919c; font-size: .84rem;}
.ts-chip {border-radius: 999px; padding: .05rem .55rem; font-size: .72rem; font-weight: 650;
  border: 1px solid transparent;}
.ts-chip.soft {color: #1d3f6e; background: rgba(29, 63, 110, .08); border-color: rgba(29, 63, 110, .3);}
.ts-chip.hard {color: #92400e; background: rgba(245, 158, 11, .14); border-color: rgba(245, 158, 11, .55);}
.ts-unit {font-size: .74rem; color: #8a919c;}
/* The Recommendation Engine: small thumbnails in a strip, like a slide
   sorter; the whole thumbnail is the button that opens its details */
.st-key-reco_strip {height: 112px; background: #fff; border: 1px solid #e4e7ec; border-radius: 14px;
  padding: 10px 14px; flex-wrap: nowrap !important; overflow-x: auto; overflow-y: hidden; gap: .75rem !important;
  scrollbar-width: thin; margin-top: .1rem;}
.ts-strip-label {font-size: .68rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
  color: #5b6370; line-height: 1.3; padding-right: .75rem; border-right: 1px solid #eef0f3; white-space: nowrap;}
.ts-strip-label small {display: block; text-transform: none; letter-spacing: 0; font-weight: 500;
  color: #8a919c; font-size: .7rem;}
[class*="st-key-cand_"] {position: relative; flex: none !important;}
.ts-cand {position: relative; height: 80px; border-radius: 8px; overflow: hidden; background: #fff;
  border: 2px solid transparent; box-shadow: 0 1px 4px rgba(16, 24, 40, .2);
  transition: transform .12s, box-shadow .12s;}
.ts-cand img {height: 100%; width: auto; display: block;}
.ts-cand b {position: absolute; left: 4px; bottom: 4px; min-width: 18px; height: 18px; padding: 0 5px;
  border-radius: 999px; background: rgba(19, 41, 75, .88); color: #fff; font-size: 11px;
  display: flex; align-items: center; justify-content: center;}
.ts-cand.rec::after {content: "★"; position: absolute; top: 2px; right: 5px; color: #f59e0b; font-size: 14px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, .45);}
[class*="st-key-cand_on_"] .ts-cand {border-color: #cf4836; box-shadow: 0 0 0 2px rgba(207, 72, 54, .22);}
[class*="st-key-cand_"]:hover .ts-cand {transform: translateY(-2px); box-shadow: 0 6px 14px rgba(16, 24, 40, .24);}
[class*="st-key-cand_"] > [data-testid="stElementContainer"]:has([data-testid="stButton"]) {position: absolute;
  inset: 0; z-index: 2; margin: 0;}
[class*="st-key-cand_"] [data-testid="stButton"], [class*="st-key-cand_"] [data-testid="stButton"] div,
[class*="st-key-cand_"] [data-testid="stButton"] button {width: 100%; height: 100%; min-height: 0;}
[class*="st-key-cand_"] [data-testid="stButton"] button {opacity: 0; cursor: pointer;}
/* On narrower windows Step 2's top-bar buttons show their icons only
   (their tooltips name them); Evaluate keeps its label */
@media (max-width: 1500px) {
  .st-key-s2_actions button:not([data-testid="stBaseButton-primary"]) [data-testid="stMarkdownContainer"] {
    display: none;}
}
:is(.st-key-reco_strip, .st-key-ts_panel) [data-testid="stMarkdownContainer"]:has(> div[class^="ts-"]) {
  margin-bottom: 0 !important;}
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
    return f"{session.domain.replace('_', ' ').title()} · {poster} · {condition_label(session, short=True)}"


def condition_label(session, short: bool = False) -> str:
    """Chapter 4's names for the Stage 2 conditions: structure mapping + GNN
    (the GNN alone without a master to map), structure mapping only, or the
    baseline (neither). `short` gives the tables' forms ("mapping + GNN")
    for the top bar, where the full name doesn't fit."""
    mapping = "mapping" if short else "structure mapping"
    if session.use_gnn:
        return f"{mapping} + GNN" if getattr(session, "structure_guided", False) else "GNN"
    return f"{mapping} only" if session.use_structure else "baseline"


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
