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
import json
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
import mail_merge                                  # noqa: E402
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
    remember_upload(path)
    return path


# ---------------------------------------------------------------------------
# Images: the pictures a designer uploaded in this browser session, and the
# keys the Images sidebar and the canvas use for them (notes §3.58)
# ---------------------------------------------------------------------------

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")
_UPLOADS = "_my_uploads"       # this session's uploaded pictures, newest last
_ASSETS = "_image_assets"      # key → path of every picture the sidebar shows


def remember_upload(path: str) -> None:
    if path.lower().endswith(IMAGE_EXTS):
        uploads = [p for p in st.session_state.get(_UPLOADS, []) if p != path]
        st.session_state[_UPLOADS] = uploads + [path]


def my_uploads() -> list:
    """This session's uploaded pictures that still exist, newest first."""
    return [p for p in reversed(st.session_state.get(_UPLOADS, [])) if os.path.exists(p)]


def asset_key(path: str) -> str:
    """A short key for a picture, registered so the canvas can name it."""
    key = hashlib.sha1(os.path.abspath(path).encode("utf-8")).hexdigest()[:12]
    st.session_state.setdefault(_ASSETS, {})[key] = path
    return key


def asset_path(key: str):
    return st.session_state.get(_ASSETS, {}).get(key)


MAX_DROP_BYTES = 10 * 1024 * 1024


def save_data_uri(uri: str, name: str, prefix: str = "element_") -> str:
    """Saves a picture the browser sent as a data: URI (a file dropped on
    the canvas), as save_upload saves an upload. Raises ValueError for
    anything but a PNG, JPEG or WEBP under 10 MB."""
    match = re.match(r"data:image/(png|jpeg|webp);base64,(.+)", uri or "", re.S)
    if not match:
        raise ValueError("Drop a PNG, JPG or WEBP picture.")
    data = base64.b64decode(match.group(2))
    if len(data) > MAX_DROP_BYTES:
        raise ValueError("That picture is over 10 MB.")
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
    except Exception:
        raise ValueError("That file isn't a picture ThemeSync can read.")
    base = os.path.splitext(safe_name(name or "picture"))[0] or "picture"
    ext = {"png": ".png", "jpeg": ".jpg", "webp": ".webp"}[match.group(1)]
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = os.path.join(UPLOAD_DIR, f"{prefix}{base}_{hashlib.sha1(data).hexdigest()[:8]}{ext}")
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(data)
    remember_upload(path)
    return path


@st.cache_data(show_spinner=False, max_entries=400)
def thumb_uri(path: str, mtime: float, size: int = 160) -> str:
    """A small PNG data: URI of a picture, transparency kept (sidebar tiles)."""
    with Image.open(path) as im:
        im = im.convert("RGBA")
        im.thumbnail((size, size))
        return data_uri(im, "PNG")


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


def font_picker(key: str, label: str, current: str, show_label: bool = True) -> str:
    """A dropdown that shows every font in its own typeface (Streamlit's
    selectbox can't style its options one by one). `current` is a family
    stack; returns the chosen one. Picking a font closes the list through
    the popover's keyed open state. Without its label (a toolbar), the
    label is the button's tooltip."""
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
                    + (f'<div class="ts-wlabel">{html.escape(label)}</div>' if show_label else ""),
                    unsafe_allow_html=True)
        with st.popover(chosen, width="stretch", key=f"{key}_font_pop", on_change="rerun",
                        help=None if show_label else label):
            for option, (_, folder) in FONTS.items():
                st.button(option, key=f"{key}_font_opt_{folder}", width="stretch",
                          type="primary" if option == chosen else "tertiary",
                          on_click=_pick_font, args=(state_key, option, f"{key}_font_pop"))
    return FONTS[chosen][0]


WEIGHT_NAMES = {100: "Thin", 200: "Extra Light", 300: "Light", 400: "Regular", 500: "Medium",
                600: "Semibold", 700: "Bold", 800: "Extra Bold", 900: "Black"}


def font_weights(stack: str) -> list:
    """The upright weights a family ships in assets/fonts/, ascending (as
    Canva lists only the weights a font has); Montserrat's for an unknown
    family."""
    folder = font_folder(stack) or "montserrat"
    return sorted({weight for _, weight, style in font_faces(folder) if style == "normal"}) or [400, 700]


@functools.lru_cache(maxsize=None)
def weight_preview_css(folder: str) -> str:
    """@font-face rules that draw each weight's name in that weight of the
    family: one face per weight, cut down to the names' letters."""
    text = "".join(WEIGHT_NAMES.values()) + "0123456789"
    return "\n".join(
        f'@font-face {{font-family: "TSW {folder}"; font-weight: {weight}; '
        f'src: url(data:font/woff;base64,{base64.b64encode(_woff(path, text)).decode("ascii")}) format("woff");}}'
        for path, weight, style in font_faces(folder) if style == "normal")


def _pick_value(state_key: str, value, popover_key: str) -> None:
    st.session_state[state_key] = value
    st.session_state[popover_key] = False          # close the list


def weight_picker(key: str, stack: str, current: int = 700, help: str = None, label: str = None,
                  default_label: str = None, on_pick=None) -> int:
    """A dropdown of the family's weights, each drawn in its own weight.
    A weight the family lacks shows as its nearest one. `label` goes above
    it as a widget's label; `default_label` adds a first option, value 0
    (Step 2's "Layout's own"); `on_pick(weight)` runs when one is picked."""
    state_key = f"{key}_weight"
    available = font_weights(stack)
    options = ([0] if default_label else []) + available
    weight = int(st.session_state.get(state_key, current) or 0)
    if weight not in options:
        weight = min(available, key=lambda w: (abs(w - weight), -w))
    st.session_state[state_key] = weight
    names = {**WEIGHT_NAMES, **({0: default_label} if default_label else {})}
    folder = font_folder(stack) or "montserrat"
    css = [f'.st-key-{key}_weight_btn button p {{font-family: "TSW {folder}", sans-serif; '
           f'font-weight: {weight or 400} !important;}}']
    css += [f'.st-key-{key}_weight_opt_{w} button p {{font-family: "TSW {folder}", sans-serif; '
            f'font-weight: {w or 400} !important; font-size: 1rem;}}' for w in options]

    def _pick(w: int) -> None:
        _pick_value(state_key, w, f"{key}_weight_pop")
        if on_pick:
            on_pick(w)

    with st.container(key=f"{key}_weight_btn", gap=None):
        st.markdown(f"<style>{weight_preview_css(folder)}\n{''.join(css)}</style>"
                    + (f'<div class="ts-wlabel">{html.escape(label)}</div>' if label else ""),
                    unsafe_allow_html=True)
        with st.popover(names[weight], width="stretch", key=f"{key}_weight_pop", on_change="rerun",
                        help=help):
            for w in options:
                st.button(names[w], key=f"{key}_weight_opt_{w}", width="stretch",
                          type="primary" if w == weight else "tertiary", on_click=_pick, args=(w,))
    return weight


SIZE_PRESETS = [12, 16, 20, 24, 28, 32, 36, 40, 48, 56, 64, 72, 80, 96, 120]


def size_stepper(key: str, current: float = 48.0, lo: float = 1.0, hi: float = 400.0, help: str = None) -> float:
    """A font size as Canva and Word set it: − and + on either side, the
    value typed in place, and a dropdown of common sizes beside it. The
    number box holds the size itself (its key is the state)."""
    state_key = f"{key}_size"
    st.session_state.setdefault(state_key, float(current))

    def _step(delta: float) -> None:
        st.session_state[state_key] = min(hi, max(lo, float(st.session_state[state_key] or current) + delta))

    def _typed() -> None:
        if st.session_state[state_key] is None:    # a cleared box keeps the size it had
            st.session_state[state_key] = float(current)

    size = float(st.session_state[state_key] or current)
    with st.container(horizontal=True, key=f"{key}_size_box", gap=None, vertical_alignment="center"):
        st.button("", icon=":material/remove:", key=f"{key}_size_dn", type="tertiary", help="Smaller",
                  on_click=_step, args=(-1.0,), disabled=size <= lo)
        st.number_input("Size (px)", min_value=lo, max_value=hi, step=1.0, format="%g", key=state_key,
                        on_change=_typed, label_visibility="collapsed", help=help)
        with st.popover("", key=f"{key}_size_pop", on_change="rerun", help="Common sizes"):
            for preset in SIZE_PRESETS:
                st.button(str(preset), key=f"{key}_size_opt_{preset}", width="stretch",
                          type="primary" if preset == size else "tertiary",
                          on_click=_pick_value, args=(state_key, float(preset), f"{key}_size_pop"))
        st.button("", icon=":material/add:", key=f"{key}_size_up", type="tertiary", help="Larger",
                  on_click=_step, args=(1.0,), disabled=size >= hi)
    return size


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
/* Blocks that only carry a script (the brand toggle, autocomplete, image
   tiles) take no room: out of the flow, so the page's gaps skip them */
[data-testid="stElementContainer"]:has(> [data-testid="stHtml"] > script:only-child),
[data-testid="stHtml"]:has(> script:only-child) {position: absolute !important; width: 0; height: 0; overflow: hidden;}
/* The » is hidden: the brand opens the sidebar (§3.65) */
[data-testid="stExpandSidebarButton"] {display: none !important;}
.ts-brand[data-ts-sidebar] {cursor: pointer; border-radius: 10px; padding: 2px 6px 2px 2px;}
.ts-brand[data-ts-sidebar]:hover {background: rgba(255, 255, 255, .10);}
[data-testid="stExpandSidebarButton"]:hover, [data-testid="stMainMenuButton"]:hover {
  background: rgba(255, 255, 255, .16) !important;}
/* The bar spans the window and stays put when the sidebar (Step 2's
   Images) opens: it is fixed to the window, its wrapper keeps its place in
   the page, and the sidebar opens below it (the user's request, §3.58) */
[data-testid="stLayoutWrapper"]:has(> .st-key-ts_topbar) {height: 60px; margin: 0 0 1rem; flex: none;}
.st-key-ts_topbar {position: fixed; top: 0; left: 0; right: 0; z-index: 1000; height: 60px;
  background: linear-gradient(90deg, #13294b 0%, #1d3f6e 55%, #2a5a8c 100%);
  padding: 0 3.6rem 0 1.4rem; justify-content: center;
  box-shadow: 0 2px 12px rgba(19, 41, 75, .28);}
[data-testid="stSidebar"] {top: 60px !important; height: calc(100vh - 60px) !important;}
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
/* When the window is narrow, the steps other than the current one show
   only their number (their name is the tooltip). */
@media (max-width: 1380px) {
  .ts-step:not(.ts-active) .ts-label {display: none;}
  .ts-step:not(.ts-active) {padding-right: .26rem;}
}

/* Bento cards: any container keyed card_*, white on the grey page. In a
   .st-key-bento_grid row the cards share the row's height. */
[class*="st-key-card_"] {background: #fff; border: 1.5px solid #d3d8e0 !important; border-radius: 16px !important;
  padding: 14px 16px 12px !important;
  box-shadow: 0 1px 2px rgba(16, 24, 40, .06), 0 4px 14px rgba(16, 24, 40, .08);}
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
/* Step 2's Images sidebar (ui.images_panel): tiles on a checkerboard, so
   transparent cut-outs read as such; drag one onto the canvas */
.ts-assets-h {font-size: .7rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
  color: #5b6370; margin: .55rem 0 .35rem;}
.ts-assets {display: grid; grid-template-columns: repeat(3, 1fr); gap: .4rem;}
.ts-asset {aspect-ratio: 1; border-radius: 10px; border: 1px solid #e0e3e8; cursor: grab; overflow: hidden;
  display: flex; align-items: center; justify-content: center; padding: 6px;
  background: repeating-conic-gradient(#eef0f3 0 25%, #fff 0 50%) 0 0 / 14px 14px;
  transition: box-shadow .12s, transform .12s;}
.ts-asset:hover {box-shadow: 0 0 0 2px #e8735a; transform: translateY(-1px);}
.ts-asset:active {cursor: grabbing;}
.ts-asset img {max-width: 100%; max-height: 100%; object-fit: contain; pointer-events: none;}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:has(> .ts-assets-h) {margin-bottom: 0 !important;}
/* A field the mail merge fills from the list: locked, and plainly so */
[class*="st-key-merged_content_"] :is([data-testid="stTextInputRootElement"], [data-testid="stTextAreaRootElement"],
  [data-baseweb="input"], [data-baseweb="textarea"]) {
  background: repeating-linear-gradient(135deg, #eceef2 0 8px, #e4e7ec 8px 16px) !important;
  border: 1px dashed #b9c0cb !important; cursor: not-allowed;}
[class*="st-key-merged_content_"] :is(input, textarea) {background: transparent !important;
  color: #5b6370 !important; -webkit-text-fill-color: #5b6370; font-style: italic; cursor: not-allowed;}
[class*="st-key-merged_content_"] [data-testid="stWidgetLabel"] p {color: #b8392a !important; font-weight: 600;}
/* Autocomplete from the sample text (ui.autocomplete_samples): the rest of
   the hint, grey, after what was typed; Tab or → takes it */
.ts-ghost {position: absolute; inset: 0; pointer-events: none; overflow: hidden; color: transparent;
  white-space: pre; z-index: 1;}
.ts-ghost.multi {white-space: pre-wrap; overflow-wrap: break-word;}
.ts-ghost b {font-weight: inherit; color: #a3a9b3;}
.ts-ghost i {font-style: normal; font-size: .68rem; color: #8a919c; border: 1px solid #d6dae1;
  border-radius: 4px; padding: 0 .25rem; margin-left: .4rem; background: #fff; vertical-align: 1px;}
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
:is([class*="_font_btn"], [class*="_weight_btn"]) [data-testid="stMarkdownContainer"]:has(> .ts-wlabel) {
  margin-bottom: 0 !important;}
/* Measured from the selectbox beside it: #f4f5f7, 1px #e0e2e7, 8px corners,
   40px tall, 14px regular text 8px in, a dark chevron on the right */
:is([class*="_font_btn"], [class*="_weight_btn"]) button {background: #f4f5f7 !important;
  border: 1px solid #e0e2e7 !important;
  border-radius: 8px; height: 40px; min-height: 40px; padding: 0 .4rem 0 .5rem !important;
  color: #0e1318 !important; box-shadow: none !important;}
:is([class*="_font_btn"], [class*="_weight_btn"]) button:is(:hover, :focus-visible) {border-color: #c3c8d0 !important;
  color: #0e1318 !important;}
[class*="_font_btn"] button > div {width: 100%; justify-content: space-between;}
[class*="_font_btn"] button [data-testid="stMarkdownContainer"] {flex: 1; min-width: 0; text-align: left;}
[class*="_font_btn"] button p {white-space: nowrap; overflow: hidden; text-overflow: ellipsis; text-align: left;
  font-size: 14px; font-weight: 400;}
[class*="_font_btn"] button > div > div:first-child {flex: 1; min-width: 0; display: flex;
  justify-content: flex-start;}
[class*="_font_btn"] button [data-testid="stIconMaterial"] {color: #31333f; font-size: 1.25rem;}
/* Step 1's typography as a toolbar, as in Canva or Word: the font, its
   weight and the size in one strip, split by thin rules, each a dropdown
   (ui.font_picker, weight_picker, size_stepper) */
.st-key-type_bar {flex-wrap: nowrap !important; align-items: center; background: #f4f5f7;
  border: 1px solid #d9dde3; border-radius: 10px; padding: 3px; gap: 0 !important;}
.st-key-type_bar > * {min-width: 0;}
.st-key-type_bar > :has(.st-key-type_font_btn) {flex: 1.7 1 0 !important;}
.st-key-type_bar > :has(.st-key-type_weight_btn) {flex: 1 1 0 !important; border-left: 1px solid #d9dde3;
  margin-left: 3px; padding-left: 3px;}
.st-key-type_bar > :has(.st-key-type_size_box) {flex: none !important; width: auto !important;
  border-left: 1px solid #d9dde3; margin-left: 3px; padding-left: 3px;}
.st-key-type_size_box {width: auto !important;}
.st-key-type_bar :is([class*="_font_btn"], [class*="_weight_btn"]) button {background: transparent !important;
  border: 1px solid transparent !important; height: 36px; min-height: 36px; border-radius: 7px;}
.st-key-type_bar :is([class*="_font_btn"], [class*="_weight_btn"], [class*="_size_box"]) button:hover {
  background: #fff !important; border-color: #d9dde3 !important;}
[class*="_weight_btn"] button {padding: 0 .4rem 0 .6rem !important; color: #0e1318 !important;
  box-shadow: none !important;}
[class*="_weight_btn"] button > div {width: 100%; justify-content: space-between;}
[class*="_weight_btn"] button [data-testid="stMarkdownContainer"] {flex: 1; min-width: 0; text-align: left;}
[class*="_weight_btn"] button p {white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  text-align: left; font-size: 14px;}
[class*="_weight_btn"] button > div > div:first-child {flex: 1; min-width: 0; display: flex;
  justify-content: flex-start;}
[class*="_weight_btn"] button [data-testid="stIconMaterial"] {color: #31333f; font-size: 1.25rem;}
[class*="_weight_btn"] [data-testid="stMarkdownContainer"]:has(> style:only-child),
[class*="_font_btn"] [data-testid="stMarkdownContainer"]:has(> style:only-child) {display: none;}
[class*="_size_box"] {flex-wrap: nowrap !important; align-items: center;}
[class*="_size_box"] button {height: 36px; min-height: 36px; border-radius: 7px; color: #0e1318 !important;
  border: 1px solid transparent !important; box-shadow: none !important; background: transparent !important;}
[class*="_size_box"] > * {width: auto !important; flex: none !important;}
[class*="_size_box"] [data-testid="stNumberInput"] {width: 3.6rem;}
[class*="_size_box"] [data-testid="stNumberInputContainer"] {height: 36px; border-radius: 7px;
  background: #fff; border: 1px solid #d9dde3;}
[class*="_size_box"] [data-testid="stNumberInputContainer"] input {text-align: center; font-weight: 600;
  font-size: 14px; padding: 0 .2rem; font-variant-numeric: tabular-nums; background: transparent;}
[class*="_size_box"] :is([data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"]),
[class*="_size_box"] [data-testid="InputInstructions"] {display: none !important;}
[class*="_size_box"] [data-testid="stPopover"] button {width: 24px; padding: 0 !important; min-width: 0;}
[class*="_size_box"] > :not(:has(:is([data-testid="stPopover"], [data-testid="stNumberInput"]))) button {
  width: 34px; padding: 0 !important;}
/* Their lists read like a menu: compact rows, left-aligned, the current
   choice tinted rather than filled */
[data-testid="stPopoverBody"]:has(:is([class*="_font_opt_"], [class*="_weight_opt_"], [class*="_size_opt_"]))
  > [data-testid="stVerticalBlock"] {gap: 2px !important;}
[data-testid="stPopoverBody"]:has([class*="_size_opt_"]) {max-height: min(360px, 60vh) !important;
  overflow-y: auto !important; scrollbar-width: thin; min-width: 9rem;}
:is([class*="_font_opt_"], [class*="_weight_opt_"], [class*="_size_opt_"]) button {min-height: 2.1rem;
  padding: .2rem .75rem !important; justify-content: flex-start; border-radius: 7px;}
:is([class*="_font_opt_"], [class*="_weight_opt_"], [class*="_size_opt_"]) button > div {justify-content: flex-start;}
:is([class*="_font_opt_"], [class*="_weight_opt_"], [class*="_size_opt_"]) button:hover {background: #f1f3f6;}
:is([class*="_font_opt_"], [class*="_weight_opt_"], [class*="_size_opt_"]) button[kind="primary"] {
  background: #fdecea; color: #b8392a; border-color: transparent;}
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
    st.html(_BRAND_JS, unsafe_allow_javascript=True)


# Autocomplete from the sample text: a content field whose hint is
# "e.g. <sample>" shows the rest of the sample, grey, while what is typed
# matches its start (any case); Tab, or → at the end, takes it. The value
# is set through React's own setter, so Streamlit sees a typed change.
_AUTOCOMPLETE_JS = """<script>
(() => {
  if (window.__tsAutocomplete) return;
  window.__tsAutocomplete = true;
  const doc = window.parent && window.parent.document && window.parent !== window ? window.parent.document : document;
  const FIELD = '.st-key-content_fields input, .st-key-content_fields textarea';
  const sample = el => (el.placeholder || '').startsWith('e.g. ') ? el.placeholder.slice(5) : '';
  const rest = el => {
    const s = sample(el), v = el.value;
    return v && !el.disabled && s.length > v.length && s.toLowerCase().startsWith(v.toLowerCase())
      ? s.slice(v.length) : '';
  };
  const ghostOf = el => {
    const box = el.parentElement;
    let g = box.querySelector(':scope > .ts-ghost');
    if (!g) {
      g = doc.createElement('div');
      g.className = 'ts-ghost' + (el.tagName === 'TEXTAREA' ? ' multi' : '');
      if (getComputedStyle(box).position === 'static') box.style.position = 'relative';
      box.appendChild(g);
    }
    const cs = getComputedStyle(el);
    for (const p of ['fontFamily', 'fontSize', 'fontWeight', 'letterSpacing', 'lineHeight', 'paddingTop',
                     'paddingRight', 'paddingBottom', 'paddingLeft', 'borderTopWidth', 'borderLeftWidth'])
      g.style[p] = cs[p];
    g.style.borderStyle = 'solid'; g.style.borderColor = 'transparent';
    g.style.borderRightWidth = '0'; g.style.borderBottomWidth = '0';
    return g;
  };
  const show = el => {
    const r = rest(el);
    const g = r || el.parentElement.querySelector(':scope > .ts-ghost') ? ghostOf(el) : null;
    if (!g) return;
    g.textContent = '';
    if (!r || doc.activeElement !== el) return;
    g.scrollTop = el.scrollTop;
    g.append(doc.createTextNode(el.value));
    const b = doc.createElement('b'); b.textContent = r; g.append(b);
    const i = doc.createElement('i'); i.textContent = 'Tab'; g.append(i);
  };
  const take = el => {
    const r = rest(el);
    if (!r) return false;
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, sample(el));
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.setSelectionRange(el.value.length, el.value.length);
    show(el);
    return true;
  };
  doc.addEventListener('input', e => e.target.matches && e.target.matches(FIELD) && show(e.target), true);
  doc.addEventListener('focusin', e => e.target.matches && e.target.matches(FIELD) && show(e.target), true);
  doc.addEventListener('focusout', e => e.target.matches && e.target.matches(FIELD) && setTimeout(() => show(e.target)), true);
  doc.addEventListener('scroll', e => e.target.matches && e.target.matches(FIELD) && show(e.target), true);
  doc.addEventListener('keydown', e => {
    const el = e.target;
    if (!el.matches || !el.matches(FIELD) || e.shiftKey || e.altKey || e.ctrlKey || e.metaKey) return;
    const atEnd = el.selectionStart === el.value.length && el.selectionEnd === el.value.length;
    if ((e.key === 'Tab' || (e.key === 'ArrowRight' && atEnd)) && take(el)) e.preventDefault();
  }, true);
})();
</script>"""


def autocomplete_samples() -> None:
    """Tab-completion of the content fields from their sample text (Step 1)."""
    st.html(_AUTOCOMPLETE_JS, unsafe_allow_javascript=True)


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


# A temporary logo (the user's request, §3.65): a puzzle piece, Material's
# "extension" glyph
PUZZLE_ICON = ('<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="currentColor" '
               'd="M20.5 11H19V7c0-1.1-.9-2-2-2h-4V3.5C13 2.12 11.88 1 10.5 1S8 2.12 8 3.5V5H4c-1.1 0-1.99.9-1.99 '
               '2v3.8H3.5c1.49 0 2.7 1.21 2.7 2.7s-1.21 2.7-2.7 2.7H2V20c0 1.1.9 2 2 2h3.8v-1.5c0-1.49 1.21-2.7 '
               '2.7-2.7 1.49 0 2.7 1.21 2.7 2.7V22H17c1.1 0 2-.9 2-2v-4h1.5c1.38 0 2.5-1.12 2.5-2.5S21.88 11 20.5 '
               '11z"/></svg>')

# The » that opens the sidebar is hidden; the brand opens and closes it
_BRAND_JS = """<script>
(() => {
  if (window.__tsBrand) return;
  window.__tsBrand = true;
  const doc = window.parent && window.parent !== window ? window.parent.document : document;
  doc.addEventListener('click', e => {
    if (!(e.target.closest && e.target.closest('[data-ts-sidebar]'))) return;
    const open = doc.querySelector('[data-testid="stSidebar"][aria-expanded="true"]');
    const btn = open ? doc.querySelector('[data-testid="stSidebarCollapseButton"] button')
                     : doc.querySelector('[data-testid="stExpandSidebarButton"]');
    if (btn) btn.click();
  }, true);
})();
</script>"""


def top_bar(active: int, subtitle: str = "", tool: str = None):
    """The bar across the top of a page, like a design tool's header: the
    brand and the design being edited, the three steps (or, on a research
    tool's page, the tool's name), and an empty column that the page fills
    with its actions (returned)."""
    with st.container(key="ts_topbar"):
        brand, steps, actions = st.columns([1.25, 2.7, 2.05], vertical_alignment="center", gap="small")
        brand.markdown(f'<div class="ts-brand" data-ts-sidebar title="Show or hide the sidebar">'
                       f'<span class="ts-logo">{PUZZLE_ICON}</span><span><b>ThemeSync</b>'
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
        # A page's own panel goes above the workflow (Step 2's Images)
        st.session_state["_sidebar_top"] = st.container()
        st.markdown("**Workflow**")
        for n, page, title, icon in STEPS:
            st.page_link(page, label=f"Step {n} · {title}", icon=icon, disabled=n != now)
        st.caption("One step at a time. The buttons on each page move you on or back.")
        st.markdown("**Research tools**")
        for page, title, icon in RESEARCH_PAGES:
            st.page_link(page, label=title, icon=icon)


# The Images sidebar's tiles: dragged onto the canvas they carry their key;
# clicked, they ask the canvas (canvas_editor.js) to add them.
_TILES_JS = """<script>
(() => {
  if (window.__tsTiles) return;
  window.__tsTiles = true;
  const doc = window.parent && window.parent !== window ? window.parent.document : document;
  doc.addEventListener('dragstart', e => {
    const t = e.target.closest && e.target.closest('[data-ts-asset]');
    if (!t) return;
    e.dataTransfer.setData('application/x-themesync-asset', t.dataset.tsAsset);
    e.dataTransfer.effectAllowed = 'copy';
  }, true);
  doc.addEventListener('click', e => {
    const t = e.target.closest && e.target.closest('[data-ts-asset]');
    if (t) doc.dispatchEvent(new CustomEvent('themesync-add-asset', {detail: {asset: t.dataset.tsAsset}}));
  }, true);
})();
</script>"""


def _tiles(title: str, paths: list, empty: str = None) -> None:
    paths = [p for p in dict.fromkeys(paths) if p and os.path.exists(p)]
    if not paths and not empty:
        return
    tiles = "".join(
        f'<div class="ts-asset" draggable="true" data-ts-asset="{asset_key(p)}" '
        f'title="{html.escape(os.path.basename(p))} · drag onto the canvas, or click to add">'
        f'<img src="{thumb_uri(p, os.path.getmtime(p))}" alt="" draggable="false"></div>' for p in paths)
    st.markdown(f'<div class="ts-assets-h">{html.escape(title)}</div>'
                + (f'<div class="ts-assets">{tiles}</div>' if paths else f'<div class="ts-note">{empty}</div>'),
                unsafe_allow_html=True)


def images_panel(session) -> None:
    """Step 2's Images, in the retractable left sidebar as in Canva: the
    master's logos and stylistic markers, and the pictures uploaded in this
    session. Drag one onto the canvas to place it there, or click it to add
    it in the layout's largest empty space."""
    top = st.session_state.get("_sidebar_top")
    if top is None:
        return
    kit = session.style_kit or {}
    marks = [(kit.get("wordmark") or {}).get("path"), *[m.get("path") for m in kit.get("motifs") or []]]
    with top:
        st.markdown("**Images**")
        st.caption("Drag a picture onto the canvas, or click it to add it.")
        _tiles("Logos", [*(session.logos.get("row") or []), session.logos.get("primary")])
        _tiles("From the poster", [*marks, kit.get("background")])
        ups = st.file_uploader("Upload images", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True,
                               key="sidebar_uploads", label_visibility="collapsed")
        for up in ups or []:
            save_upload(up, prefix="element_")
        _tiles("Uploads", my_uploads(), empty="Pictures you upload, or drop on the canvas, appear here.")
        st.html(_TILES_JS, unsafe_allow_javascript=True)
        st.divider()


def mail_merge_download(session, state: dict, key: str = "merge") -> None:
    """The mail merge's download (Step 2's Download menu, Step 3's
    downloads): the current layout once per CSV row (mail_merge.py), as PNG
    or PDF files in a ZIP, built on request. `key` keeps the two pages'
    widgets apart."""
    merge = session.merge
    if not merge or not merge.get("rows"):
        return
    st.divider()
    st.caption(f"Mail merge: {len(merge['rows'])} layouts from {merge['source']}, with "
               f"{', '.join(merge['labels'].values())} filled in from each row.")
    fmt = st.segmented_control("Format", ["PNG", "PDF"], default="PNG", key=f"{key}_fmt",
                               label_visibility="collapsed") or "PNG"
    stamp = (id(session), state["state_id"], fmt, json.dumps(session.typography, sort_keys=True))
    built = st.session_state.get("merge_zip")
    if not (built and built[0] == stamp and os.path.exists(built[1])):
        if not st.button(f"Build {len(merge['rows'])} layouts ({fmt})", icon=":material/folder_zip:",
                         width="stretch", key=f"{key}_build"):
            return
        bar = st.progress(0.0, text="Rendering…")
        path = mail_merge.zip_layouts(session, fmt.lower(),
                                      progress=lambda done, total: bar.progress(done / total,
                                                                                text=f"{done} of {total}"))
        built = st.session_state["merge_zip"] = (stamp, path)
    st.download_button(f"Download the ZIP ({os.path.getsize(built[1]) / 1e6:.1f} MB)", data=reader(built[1]),
                       file_name=os.path.basename(built[1]), mime="application/zip", type="primary",
                       icon=":material/download:", width="stretch")


def back_to_step_one(key: str, label: str = "Step 1") -> None:
    """A confirmed way back to Step 1: it closes the layout being edited."""
    session = st.session_state.get("orch")
    with st.popover(label, icon=":material/undo:", width="stretch", help="Back to Step 1"):
        st.markdown("Going back closes this layout. Its files stay saved"
                    + (f" in `{os.path.relpath(session.output_dir, ROOT)}`" if session else "")
                    + "; initializing again starts a new layout.")
        if st.button("Yes, go back to Step 1", key=key, type="primary"):
            go_to_step(1)
