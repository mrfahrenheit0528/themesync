"""
ThemeSync — Frames, decor placement and background composition
=================================================================
Everything drawn *behind* the content of a certificate or event ID:

  frames  how a layout archetype frames its content (notes §3.27): the
          certificate panel ("paper") the master's background frames, a
          split layout with a column of the master's artwork, a header
          banner, a translucent card on an event ID, a full-width role band
  motifs  the master's decorations (Stage 0c) placed around the solved
          layout — corners and sides, bleeding slightly off the edge, the way
          the group's 18 real event IDs frame their content with the pubmat's
          characters — or, as the "hero", filling the largest gap in the
          layout (a poster whose title sits low leaves room above it)

compose_background() rasterises the same stack the SVG renderer draws. The
Legibility Penalty (Formula 3.15) is scored against its SIFT saliency map,
and text colours are picked against it.

Motifs are shrunk, then dropped, rather than allowed to cover any text,
logo, or each other.
"""

import functools
import os

from PIL import Image

import numpy as np

# Motif arrangements: TL/TR/BL/BR corners, ML/MR middle of the left/right
# edge; "HERO" fills the largest gap between stacked elements.
ARRANGEMENTS = [
    ("diagonal", ("TL", "BR")),
    ("anti-diagonal", ("TR", "BL")),
    ("four corners", ("TL", "TR", "BL", "BR")),
    ("side columns", ("ML", "MR")),
    ("base pair", ("BL", "BR")),
    ("crown pair", ("TL", "TR")),
    ("hero", ("HERO",)),
]
BLEED = 0.18           # share of a motif allowed past the canvas edge
SCALES = (1.0, 0.85, 0.7, 0.55)
PANEL_INSET = 0.065    # certificate panel inset, share of the shorter side
PANEL_OPACITY = 0.90
WATERMARK_OPACITY = 0.08
SPLIT_COLUMN = 0.36    # share of the width the split archetype gives the art
HERO_MIN_GAP = 0.12    # a gap this tall (share of the height) can hold the hero


def _intersects(a: list, b: list) -> bool:
    return (a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and
            a[1] < b[1] + b[3] and b[1] < a[1] + a[3])


def _slot_box(slot: str, width: float, height: float, w: float, h: float) -> list:
    left, right = -BLEED * w, width - (1.0 - BLEED) * w
    top, bottom = -BLEED * h, height - (1.0 - BLEED) * h
    return {
        "TL": [left, top, w, h], "TR": [right, top, w, h],
        "BL": [left, bottom, w, h], "BR": [right, bottom, w, h],
        "ML": [left, (height - h) / 2.0, w, h], "MR": [right, (height - h) / 2.0, w, h],
    }[slot]


def _fit(aspect: float, max_w: float, max_h: float) -> tuple:
    w = max_w
    h = w / aspect
    if h > max_h:
        h = max_h
        w = h * aspect
    return w, h


def _decor_node(index: int, box: list, motif: dict, slot: str, arrangement: str) -> dict:
    return {
        "node_id": f"decor_motif_{index}",
        "semantic_category": "embellishment",
        "structural_class": "decor",
        "spatial_hierarchy": 100 + index,
        "constraint_type": "Soft",
        "bbox": [round(v, 2) for v in box],
        "motif_path": motif["path"],
        "slot": slot,
        "arrangement": arrangement,
        # mirror right-hand motifs so pairs face each other
        "flip": slot in ("TR", "BR", "MR"),
    }


def _hero_box(width: float, height: float, content_boxes: list, aspect: float, pad: float):
    """The largest vertical gap between stacked content boxes, if it is at
    least HERO_MIN_GAP of the height: a box for the hero motif inside it."""
    boxes = sorted(content_boxes, key=lambda b: b[1])
    best = None
    for a, b in zip(boxes, boxes[1:]):
        top, bottom = a[1] + a[3], b[1]
        if bottom - top >= HERO_MIN_GAP * height and (best is None or bottom - top > best[1] - best[0]):
            best = (top, bottom)
    if best is None:
        return None
    avail_h = best[1] - best[0] - 2 * pad
    w, h = _fit(aspect, width * 0.62, avail_h)
    return [(width - w) / 2.0, best[0] + pad + (avail_h - h) / 2.0, w, h]


def place_motifs(width: float, height: float, content_boxes: list, motifs: list,
                 arrangement: int) -> list:
    """
    Decor nodes for one arrangement of the motifs around a solved layout.

    content_boxes: [x, y, w, h] of every text/logo node (kept clear).
    motifs: Stage 0c motif descriptions ({"path", "aspect", ...}), ranked.
    arrangement: index into ARRANGEMENTS; also rotates which motifs are
      used, so candidates differ in both where and which. "hero" puts the
      top-ranked motif in the largest gap between stacked elements, and
      falls back to the diagonal when no gap is tall enough.

    Returns node dicts ({"node_id", "structural_class": "decor", "bbox",
    "motif_path", "flip", ...}) ready to join the layout's node list.
    """
    if not motifs:
        return []
    name, slots = ARRANGEMENTS[arrangement % len(ARRANGEMENTS)]
    short = min(width, height)
    pad = short * 0.015
    if slots == ("HERO",):
        motif = motifs[0]
        box = _hero_box(width, height, content_boxes, max(0.2, float(motif.get("aspect") or 1.0)), pad)
        if box:
            return [_decor_node(0, box, motif, "HERO", name)]
        name, slots = ARRANGEMENTS[0]
    base = short * (0.30 if len(slots) <= 2 else 0.22)
    clear = [[x - pad, y - pad, w + 2 * pad, h + 2 * pad] for x, y, w, h in content_boxes]
    placed = []
    for k, slot in enumerate(slots):
        motif = motifs[(arrangement + k) % len(motifs)]
        aspect = max(0.2, min(5.0, float(motif.get("aspect") or 1.0)))
        for scale in SCALES:
            size = base * scale
            w, h = (size, size / aspect) if aspect >= 1.0 else (size * aspect, size)
            box = _slot_box(slot, width, height, w, h)
            if not any(_intersects(box, c) for c in clear + [p["bbox"] for p in placed]):
                placed.append(_decor_node(len(placed), box, motif, slot, name))
                break
    return placed


# ---------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------

_DARKNESS = {}


def background_is_dark(background_path: str) -> bool:
    """Whether the master's text-free background is predominantly dark
    (mean relative luminance below 0.2), e.g. SIKLAB's night sky."""
    if background_path not in _DARKNESS:
        with Image.open(background_path) as bg:
            small = bg.convert("RGB").resize((32, 32))
        _DARKNESS[background_path] = mean_luminance(small, [0, 0, 32, 32]) < 0.2
    return _DARKNESS[background_path]


def frame_layers(domain: str, frame: str, width: float, height: float, content_nodes: list,
                 palette: dict, dark: bool = False) -> dict:
    """
    What an archetype's frame draws behind the content:
        panel       [x, y, w, h] of the light certificate panel / ID card, or None
        panel_style "panel" (certificate paper, double border) or "card"
        panel_fill  hex fill of the panel/card, panel_opacity its opacity — an
                    event-ID card on a dark master is dark (`dark`), so the
                    master's light-on-dark title artwork keeps its contrast
        overlays    [{"box", "fill", "opacity", "rx"}] solid shapes (banner)
        art_box     [x, y, w, h] showing the master's title artwork at full
                    strength (split archetype's art column), or None
        watermark   whether the title artwork is watermarked on the panel
        role_band   "full" when the event-ID role band spans the whole width
    """
    W, H = float(width), float(height)
    layers = {"panel": None, "panel_style": "panel", "overlays": [], "art_box": None,
              "watermark": False, "role_band": None, "panel_fill": palette.get("panel", "#FFFFFF"),
              "panel_opacity": PANEL_OPACITY}
    inset = min(W, H) * PANEL_INSET
    stack = sorted((n for n in content_nodes if n.get("structural_class") not in ("decor", "repeating_group")),
                   key=lambda n: n["spatial_hierarchy"])
    if domain == "identification_card":
        if frame == "card" and stack:
            top = min(n["bbox"][1] for n in stack) - 24.0
            bottom = max(n["bbox"][1] + n["bbox"][3] for n in content_nodes
                         if n.get("structural_class") != "decor") + 24.0
            layers.update(panel=[0.06 * W, max(8.0, top), 0.88 * W, min(H - 8.0, bottom) - max(8.0, top)],
                          panel_style="card",
                          panel_fill=palette.get("card_dark", "#101018") if dark else palette.get("panel", "#FFFFFF"),
                          panel_opacity=0.80 if dark else 0.86)
        elif frame == "band":
            layers["role_band"] = "full"
        return layers
    # certificates
    if frame == "split":
        column = SPLIT_COLUMN * W
        layers.update(panel=[column, inset, W - column - inset, H - 2 * inset],
                      art_box=[inset, inset, column - 2 * inset, H - 2 * inset])
        return layers
    layers.update(panel=[inset, inset, W - 2 * inset, H - 2 * inset], watermark=True)
    if frame == "banner" and len(stack) >= 2:
        band_bottom = stack[1]["bbox"][1] + stack[1]["bbox"][3] + 18.0
        layers["overlays"].append({"box": [inset, inset, W - 2 * inset, band_bottom - inset],
                                   "fill": palette.get("band", palette["accent"]), "opacity": 1.0, "rx": 14})
    return layers


def panel_box(domain: str, width: float, height: float) -> list:
    """The classic frame's panel (kept for callers that don't pick an
    archetype): the certificate paper; event IDs are full-bleed."""
    if domain == "identification_card":
        return None
    inset = min(width, height) * PANEL_INSET
    return [inset, inset, width - 2 * inset, height - 2 * inset]


def watermark_box(panel: list, aspect: float) -> list:
    """Where the event's title artwork sits as a faint watermark on the
    certificate panel: centred, at most 62% of the panel's width and 46% of
    its height, keeping its proportions."""
    px, py, pw, ph = panel
    w, h = _fit(max(aspect, 0.1), pw * 0.62, ph * 0.46)
    return [px + (pw - w) / 2.0, py + (ph - h) / 2.0, w, h]


def art_image_box(art_box: list, aspect: float) -> list:
    """The title artwork (or hero motif) centred in a split layout's art
    column, at most 86% of its width and 40% of its height."""
    x, y, w, h = art_box
    iw, ih = _fit(max(aspect, 0.1), w * 0.86, h * 0.40)
    return [x + (w - iw) / 2.0, y + (h - ih) / 2.0, iw, ih]


def _hex_rgb(hexcode: str) -> tuple:
    return tuple(int(hexcode[i:i + 2], 16) for i in (1, 3, 5))


def _file_key(path: str) -> tuple:
    """A file's identity (path, size, modification time) for the caches."""
    st = os.stat(path)
    return (os.path.abspath(path), st.st_size, st.st_mtime_ns)


@functools.lru_cache(maxsize=32)
def _decoded(key: tuple) -> Image.Image:
    """A motif or artwork file decoded to RGBA, once per file (notes §3.47).
    Callers only resize it, which returns a new image."""
    with Image.open(key[0]) as im:
        return im.convert("RGBA")


@functools.lru_cache(maxsize=8)
def _covered(key: tuple, width: int, height: int) -> Image.Image:
    """The background file scaled to cover width × height, once per file
    and size (notes §3.47). Callers only convert it, which returns a new
    image."""
    from stylistic_markers import cover  # data_preprocessing is on sys.path in every entry point

    with Image.open(key[0]) as bg:
        return cover(bg.convert("RGB"), int(width), int(height))


def _paste(canvas: Image.Image, path: str, box: list, opacity: float = 1.0, flip: bool = False) -> Image.Image:
    x, y, w, h = box
    if w < 2 or h < 2:
        return canvas
    art = _decoded(_file_key(path)).resize((int(round(w)), int(round(h))), Image.LANCZOS)
    if flip:
        art = art.transpose(Image.FLIP_LEFT_RIGHT)
    if opacity < 1.0:
        art.putalpha(art.getchannel("A").point(lambda a: int(a * opacity)))
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.paste(art, (int(round(x)), int(round(y))), art)
    return Image.alpha_composite(canvas, layer)


BACKGROUND_ITEMS = ("bg_backdrop", "bg_panel", "bg_watermark", "bg_art")


def compose_background(background_path: str, width: int, height: int,
                       decor_nodes: list = (), panel: list = None,
                       panel_rgb: tuple = (255, 255, 255), panel_opacity: float = PANEL_OPACITY,
                       watermark: dict = None, layers: dict = None, art: dict = None,
                       edits: dict = None) -> Image.Image:
    """
    Rasterises the output's background layer at canvas size: the text-free
    master background (scaled to cover), the frame (`layers`, from
    frame_layers — or a bare `panel` for older callers), the title artwork
    as a watermark or in a split layout's art column (`watermark`/`art`: a
    style-kit wordmark or motif entry), and the motifs — the same stack the
    SVG renderer draws, used for the saliency map (Legibility Penalty) and
    for picking legible text colours. `edits`: the designer's background
    styles (bg_backdrop, bg_panel, bg_watermark, bg_art: box, opacity,
    image, hidden; notes §3.64), drawn as the renderer draws them.
    """
    e = lambda k: (edits or {}).get(k) or {}
    backdrop = e("bg_backdrop")
    canvas = _covered(_file_key(backdrop.get("image") or background_path), int(width), int(height)).convert("RGBA")
    if backdrop.get("hidden") or backdrop.get("opacity") is not None:
        white = Image.new("RGBA", canvas.size, (255, 255, 255, 255))
        canvas = white if backdrop.get("hidden") else Image.blend(white, canvas, float(backdrop["opacity"]))
    if layers is None:
        layers = {"panel": panel, "panel_style": "panel", "overlays": [], "art_box": None,
                  "watermark": bool(panel and watermark)}
    shapes = []
    if layers.get("panel") and not e("bg_panel").get("hidden"):
        fill = _hex_rgb(layers["panel_fill"]) if layers.get("panel_fill") else panel_rgb
        shapes.append((layers["panel"], fill,
                       layers.get("panel_opacity", panel_opacity) * float(e("bg_panel").get("opacity", 1.0))))
    shapes += [(o["box"], _hex_rgb(o["fill"]), o["opacity"]) for o in layers.get("overlays", [])]
    for box, rgb, opacity in shapes:
        x, y, w, h = [int(round(v)) for v in box]
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        overlay.paste(Image.new("RGBA", (max(1, w), max(1, h)), tuple(rgb) + (int(255 * opacity),)), (x, y))
        canvas = Image.alpha_composite(canvas, overlay)
    mark = e("bg_watermark")
    if watermark and layers.get("watermark") and layers.get("panel") and not mark.get("hidden"):
        canvas = _paste(canvas, mark.get("image") or watermark["path"],
                        mark.get("box") or watermark_box(layers["panel"], watermark["aspect"]),
                        opacity=float(mark.get("opacity", WATERMARK_OPACITY)))
    column = e("bg_art")
    if art and layers.get("art_box") and not column.get("hidden"):
        canvas = _paste(canvas, column.get("image") or art["path"],
                        column.get("box") or art_image_box(layers["art_box"], art["aspect"]),
                        opacity=float(column.get("opacity", 1.0)))
    for node in decor_nodes or []:
        canvas = _paste(canvas, node["motif_path"], node["bbox"], flip=node.get("flip", False))
    return canvas.convert("RGB")


def mean_luminance(image: Image.Image, bbox: list) -> float:
    """Mean relative luminance (0-1) of the composed background under a box."""
    x, y, w, h = bbox
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(image.width, int(x + w)), min(image.height, int(y + h))
    if x1 <= x0 or y1 <= y0:
        return 1.0
    region = np.asarray(image.crop((x0, y0, x1, y1)), dtype=np.float32) / 255.0
    lin = np.where(region <= 0.04045, region / 12.92, ((region + 0.055) / 1.055) ** 2.4)
    return float((lin @ np.array([0.2126, 0.7152, 0.0722])).mean())
