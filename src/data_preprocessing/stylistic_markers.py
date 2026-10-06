"""
ThemeSync — Stylistic Marker Extraction (Stage 0c)
===================================================
Phase 1 (Chapter 3, p.38 "Stylistic Marker Identification"; p.51 "scale-
invariant stylistic markers"): extracts from the master layout what the
Aesthetic Rendering Pipeline projects onto the target format besides the
K-Means palette and the logos:

  1. background — the master's text-free background layer, ThemeSync's
     counterpart of CGL's inpainted backgrounds (Figure 1(b)). The
     Legibility Penalty (Formula 3.15) is scored against this layer's
     SIFT saliency, so it is also what the output is rendered on.
  2. motifs — the master's decorative elements cut out of the poster with
     their surroundings cleared: YOLO "illustration" detections
     (characters, mascots, emblems, objects) when the model has that class
     (annotation guidelines v2), otherwise "embellishment" detections;
     ranked by class, YOLO confidence and SIFT keypoint density (the
     element's stylistic descriptor, s_i in Formula 3.6).
  3. wordmark — the event's title artwork (the largest title-sized text
     detection), cut out when it separates cleanly from the poster;
     otherwise the renderer types the title in the administrative font.

Also home to the cut-out helpers shared with logo extraction (pipeline.py)
and the dashboard pages.

See notes/gnn_fixes_and_methodology_notes.md §3.23.
"""

import os

import cv2
import numpy as np
from PIL import Image, ImageDraw

# Background: the poster is reduced to this long side, its central area is
# rebuilt from the border, and the renderer scales it up to the canvas.
BACKGROUND_WORK_SIDE = 64
BACKGROUND_INSET = 0.16

MOTIF_MIN_CONF = 0.25
# Motif sources, best first, with the largest share of the poster each may
# cover: an illustration (a mascot, an emblem) can be big; the v1-v4
# "embellishment" class mixes art with small accents. A 4-class model
# (v1-v4) has no "illustration" class, so its motifs are embellishments.
MOTIF_MAX_TEXT = 0.25   # a motif candidate this covered by text detections is lettering
MOTIF_CLASSES = {"illustration": {"weight": 1.0, "max_area": 0.35},
                 "embellishment": {"weight": 0.6, "max_area": 0.20}}
# Title-sized text survives Stage 0b down to 0.15 (layout_extractor
# TITLE_CONFIDENCE): big stylised titles score low, and false positives
# that large are rare.
WORDMARK_MIN_CONF = 0.15
TITLE_MIN_AREA = 0.05
MAX_MOTIFS = 6


# ---------------------------------------------------------------------------
# Cut-outs (shared with logo extraction)
# ---------------------------------------------------------------------------

def clear_crop_background(crop: Image.Image, thresh: int = 48,
                          max_cleared: float = 0.85) -> Image.Image:
    """
    Makes the poster background around a cropped element transparent, so it
    doesn't arrive on the certificate/ID as a pasted-on rectangle of the
    master layout's artwork. Flood-fills from every border pixel whose
    region hasn't been reached yet (tolerance `thresh`), so only background
    *connected to the crop's edges* is cleared — the element's own interior
    is never touched, even where it shares the background's colour.

    Safety valve: if the fill would clear more than `max_cleared` of the
    crop (element not visually separable from its surroundings), the
    original crop is returned unchanged rather than a hollowed-out element.
    """
    sentinel = (255, 0, 255)
    rgb = crop.convert("RGB")
    w, h = rgb.size
    border = ([(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)] +
              [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)])
    for xy in border:
        if rgb.getpixel(xy) != sentinel:
            ImageDraw.floodfill(rgb, xy, sentinel, thresh=thresh)
    mask = np.all(np.asarray(rgb) == sentinel, axis=2)
    if mask.mean() > max_cleared:
        return crop
    out = np.asarray(crop.convert("RGBA")).copy()
    out[mask, 3] = 0
    return Image.fromarray(out, "RGBA")


def cut_out(img: Image.Image, bbox: list, pad: float = 0.04) -> Image.Image:
    """A detected element cut from the master layout: its [x, y, w, h] box
    plus `pad` padding, with the surrounding poster background cleared."""
    x, y, w, h = bbox
    pad_x, pad_y = w * pad, h * pad
    box = (max(0, int(x - pad_x)), max(0, int(y - pad_y)),
           min(img.width, int(x + w + pad_x)), min(img.height, int(y + h + pad_y)))
    return clear_crop_background(img.convert("RGBA").crop(box))


def grow_cut_out(img: Image.Image, bbox: list, max_steps: int = 8, step: float = 0.06,
                 touch: float = 0.02) -> tuple:
    """
    cut_out() that grows the box on any side where the cut-out still runs
    into artwork (more than `touch` of that edge's pixels left uncleared),
    by `step` of the box size per side and step, up to `max_steps` times —
    YOLO's boxes are often a little tight on stylised lettering (e.g. a
    three-line wordmark whose last line got clipped). Returns (cut-out,
    final [x, y, w, h]).
    """
    x, y, w, h = [float(v) for v in bbox]
    for attempt in range(max_steps + 1):
        rgba = cut_out(img, [x, y, w, h])
        visible = np.asarray(rgba)[:, :, 3] > 0
        sides = {"top": visible[0].mean(), "bottom": visible[-1].mean(),
                 "left": visible[:, 0].mean(), "right": visible[:, -1].mean()}
        grow = {side for side, share in sides.items() if share > touch}
        # Lettering that continues past the box's left or right end (a
        # clipped word) shows up as edges just outside it in the raw
        # poster, even when the background clearing erased the letters
        # touching the border. Horizontal only: stacked lines are merged
        # into title groups beforehand, and growing vertically on edges
        # would pull a tagline or neighbouring artwork into the title.
        grow |= _edge_crossings(img, [x, y, w, h]) & {"left", "right"}
        # a side already at the image border can't grow
        if x <= 0: grow.discard("left")
        if y <= 0: grow.discard("top")
        if x + w >= img.width: grow.discard("right")
        if y + h >= img.height: grow.discard("bottom")
        if not grow or attempt == max_steps:
            return rgba, [x, y, w, h]
        dx, dy = w * step, h * step
        if "left" in grow:
            x, w = max(0.0, x - dx), w + min(dx, x)
        if "right" in grow:
            w = min(img.width - x, w + dx)
        if "top" in grow:
            y, h = max(0.0, y - dy), h + min(dy, y)
        if "bottom" in grow:
            h = min(img.height - y, h + dy)
    return rgba, [x, y, w, h]


def _edge_crossings(img: Image.Image, bbox: list, strip: float = 0.04,
                    density: float = 0.02) -> set:
    """Sides of the box beyond which the artwork continues: the strip just
    *outside* each side (share `strip` of the box) holds more than
    `density` Canny edge pixels in the raw poster. A clipped letter or
    figure continues past the box; a smooth background shows almost no
    edges there. (Testing inside the box fails for thick letters, whose
    outlines are sparse, and the background clearing erases any letter
    touching the crop border.)"""
    x, y, w, h = [float(v) for v in bbox]
    gray = np.asarray(img.convert("L"))
    H, W = gray.shape
    sw, sh = max(2, int(w * strip)), max(2, int(h * strip))
    regions = {
        "left":   (int(x) - sw, int(y), int(x), int(y + h)),
        "right":  (int(x + w), int(y), int(x + w) + sw, int(y + h)),
        "top":    (int(x), int(y) - sh, int(x + w), int(y)),
        "bottom": (int(x), int(y + h), int(x + w), int(y + h) + sh),
    }
    out = set()
    for side, (x0, y0, x1, y1) in regions.items():
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        if (cv2.Canny(gray[y0:y1, x0:x1], 80, 200) > 0).mean() > density:
            out.add(side)
    return out


def separation(rgba: Image.Image) -> tuple:
    """
    How cleanly a cut-out separated from its surroundings:
    (share of all pixels cleared, share of the outer ring cleared). An
    element that stood apart from its background clears most of its ring;
    one embedded in busy artwork (or returned unchanged by the safety valve)
    clears little of it.
    """
    alpha = np.asarray(rgba.convert("RGBA"))[:, :, 3]
    h, w = alpha.shape
    ring = max(1, int(min(h, w) * 0.08))
    ring_mask = np.zeros_like(alpha, dtype=bool)
    ring_mask[:ring] = ring_mask[-ring:] = True
    ring_mask[:, :ring] = ring_mask[:, -ring:] = True
    cleared = alpha == 0
    return float(cleared.mean()), float(cleared[ring_mask].mean())


def trim(rgba: Image.Image, margin: int = 2) -> Image.Image:
    """Crops a cut-out to its visible pixels (plus `margin`)."""
    box = rgba.getchannel("A").getbbox()
    if not box:
        return rgba
    x0, y0, x1, y1 = box
    return rgba.crop((max(0, x0 - margin), max(0, y0 - margin),
                      min(rgba.width, x1 + margin), min(rgba.height, y1 + margin)))


def _overlap_ratio(a: list, b: list) -> float:
    """Intersection over the smaller box's area, for [x, y, w, h] boxes."""
    ix = max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    smaller = min(a[2] * a[3], b[2] * b[3])
    return (ix * iy / smaller) if smaller > 0 else 0.0


# ---------------------------------------------------------------------------
# 1. Background
# ---------------------------------------------------------------------------

def _harmonic_fill(image: np.ndarray, mask: np.ndarray, iterations: int = 2500) -> np.ndarray:
    """Replaces the masked pixels by the harmonic (Laplace) interpolation of
    their surroundings: each becomes the average of its four neighbours,
    iterated to convergence with the unmasked pixels held fixed."""
    out = image.astype(np.float32)
    out[mask] = out[~mask].mean(axis=0)
    for _ in range(iterations):
        avg = 0.25 * (np.roll(out, 1, 0) + np.roll(out, -1, 0) +
                      np.roll(out, 1, 1) + np.roll(out, -1, 1))
        out[mask] = avg[mask]
    return out


def text_free_background(image_path: str) -> Image.Image:
    """
    The master layout's background layer with its content removed.

    An event poster's titles, logos and text sit in its central area, and
    YOLO misses many of them on unseen posters (notes §3.21), so instead of
    inpainting only the detected boxes, the whole central area is rebuilt
    from the poster's border by harmonic interpolation. That keeps the
    backdrop's colours and light (sky above grass, magenta rays, dark space)
    with no text left to show through, and without the X-shaped seams
    OpenCV's TELEA inpainting leaves when filling a large area from its
    edges. Built at BACKGROUND_WORK_SIDE px: a smooth field the renderer
    scales to any target format.
    """
    bgr = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if bgr is None:
        raise RuntimeError(f"OpenCV failed to decode image: '{image_path}'")
    h, w = bgr.shape[:2]
    scale = BACKGROUND_WORK_SIDE / max(h, w)
    small = cv2.resize(bgr, (max(8, round(w * scale)), max(8, round(h * scale))),
                       interpolation=cv2.INTER_AREA)
    sh, sw = small.shape[:2]
    mask = np.zeros((sh, sw), dtype=bool)
    mask[int(sh * BACKGROUND_INSET):sh - int(sh * BACKGROUND_INSET),
         int(sw * BACKGROUND_INSET):sw - int(sw * BACKGROUND_INSET)] = True
    filled = _harmonic_fill(small, mask)
    filled = cv2.GaussianBlur(filled, (0, 0), 1.0)
    rgb = cv2.cvtColor(np.clip(filled, 0, 255).astype(np.uint8), cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def cover(img: Image.Image, width: int, height: int) -> Image.Image:
    """Scales `img` to cover a width × height canvas and centre-crops it
    (CSS background-size: cover), with smooth resampling."""
    ratio = max(width / img.width, height / img.height)
    resized = img.resize((max(width, round(img.width * ratio)), max(height, round(img.height * ratio))),
                         Image.BICUBIC)
    left, top = (resized.width - width) // 2, (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


# ---------------------------------------------------------------------------
# 2 & 3. Motifs and wordmark
# ---------------------------------------------------------------------------

def _keypoint_density(rgba: Image.Image, sift) -> float:
    """SIFT keypoints per 1000 visible pixels: how much distinctive visual
    structure the element carries (its stylistic descriptor)."""
    arr = np.asarray(rgba.convert("RGBA"))
    visible = arr[:, :, 3] > 0
    if visible.sum() == 0:
        return 0.0
    gray = cv2.cvtColor(arr[:, :, :3], cv2.COLOR_RGB2GRAY)
    keypoints = sift.detect(gray, visible.astype(np.uint8) * 255)
    return 1000.0 * len(keypoints) / float(visible.sum())


def _merge_text_groups(nodes: list, image_h: float, gap: float = 0.015,
                       min_line_ratio: float = 0.35) -> list:
    """
    Text detections merged into title groups: boxes that overlap vertically
    or sit within `gap` of the image height of each other, share at least
    half of the narrower box's width, and have comparable line heights (the
    shorter at least `min_line_ratio` of the taller) become one box. YOLO
    often splits a stacked wordmark into lines (e.g. SIKLAB / CSPC
    INTRAMURALS and a separate, low-confidence "2025"), and a cut through
    the last line leaves the title art clipped; the height rule keeps a
    small tagline under a big title out of it. Confidence is the group's
    highest.
    """
    groups = [dict(n, bbox=list(n["bbox"]), line_h=float(n["bbox"][3])) for n in nodes]
    merged = True
    while merged:
        merged = False
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                a, b = groups[i]["bbox"], groups[j]["bbox"]
                v_gap = max(a[1], b[1]) - min(a[1] + a[3], b[1] + b[3])
                h_overlap = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
                la, lb = groups[i]["line_h"], groups[j]["line_h"]
                if (v_gap <= gap * image_h and h_overlap >= 0.5 * min(a[2], b[2])
                        and min(la, lb) >= min_line_ratio * max(la, lb)):
                    x0, y0 = min(a[0], b[0]), min(a[1], b[1])
                    x1, y1 = max(a[0] + a[2], b[0] + b[2]), max(a[1] + a[3], b[1] + b[3])
                    groups[i]["bbox"] = [x0, y0, x1 - x0, y1 - y0]
                    groups[i]["line_h"] = max(la, lb)
                    groups[i]["detection_confidence"] = max(groups[i].get("detection_confidence", 0.0),
                                                            groups[j].get("detection_confidence", 0.0))
                    groups.pop(j)
                    merged = True
                    break
            if merged:
                break
    return groups


# YuNet face detector (OpenCV model zoo, MIT licence; OpenCV 5 dropped the
# Haar cascade classifier). Bundled so nothing is downloaded at run time.
_FACE_MODEL = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                           "assets", "models", "face_detection_yunet_2023mar.onnx")
_FACES = None


def _has_face(rgba: Image.Image) -> bool:
    """True when the cut-out shows a human face: photos of real people (a
    poster's photo collage) are content, never decoration."""
    global _FACES
    if not os.path.exists(_FACE_MODEL):
        return False
    if _FACES is None:
        _FACES = cv2.FaceDetectorYN.create(_FACE_MODEL, "", (320, 320), 0.8, 0.3, 50)
    bgr = cv2.cvtColor(np.asarray(rgba.convert("RGB")), cv2.COLOR_RGB2BGR)
    h, w = bgr.shape[:2]
    if min(h, w) < 32:
        return False
    scale = 640.0 / max(h, w) if max(h, w) > 640 else 1.0
    if scale != 1.0:
        bgr = cv2.resize(bgr, (int(w * scale), int(h * scale)))
    _FACES.setInputSize((bgr.shape[1], bgr.shape[0]))
    _, faces = _FACES.detect(bgr)
    return faces is not None and len(faces) > 0


def _usable_motif(rgba: Image.Image) -> bool:
    """A cut-out that works as a stand-alone decoration: not a strip or a
    sliver (aspect 0.3-3.3), mostly solid rather than scattered fragments
    (at least 25% of its trimmed box visible), and no human face."""
    aspect = rgba.width / max(1, rgba.height)
    if not 0.3 <= aspect <= 3.3:
        return False
    if (np.asarray(rgba.convert("RGBA"))[:, :, 3] > 0).mean() < 0.25:
        return False
    return not _has_face(rgba)


def _title_like(n: dict, W: float, H: float) -> bool:
    x, y, w, h = n["bbox"]
    return (n.get("semantic_category") in ("text", "embellishment")
            and n.get("detection_confidence", 0.0) >= WORDMARK_MIN_CONF
            and w * h >= 0.025 * W * H and h >= 0.05 * H and w >= 1.2 * h
            and y + h / 2.0 <= 0.8 * H)


def text_groups(detected_nodes: list, image_w: float, image_h: float) -> list:
    """Stage 0b's text detections merged into groups of stacked lines (see
    _merge_text_groups): conf >= MOTIF_MIN_CONF, or >= WORDMARK_MIN_CONF
    for title-sized text (>= TITLE_MIN_AREA of the poster)."""
    def keep(n):
        conf = n.get("detection_confidence", 0.0)
        big = n["bbox"][2] * n["bbox"][3] >= TITLE_MIN_AREA * image_w * image_h
        return conf >= MOTIF_MIN_CONF or (conf >= WORDMARK_MIN_CONF and big)
    texts = [n for n in detected_nodes or [] if n.get("semantic_category") == "text" and keep(n)]
    return _merge_text_groups(texts, image_h)


def title_group_box(detected_nodes: list, image_w: float, image_h: float):
    """[x, y, w, h] of the master's event title — the largest title-sized
    text group (by area × confidence), whether or not it cuts out cleanly —
    or None. Where the title *sits* is structure (notes §3.26), independent
    of whether its artwork can be reused."""
    embellished = [n for n in detected_nodes or [] if n.get("semantic_category") == "embellishment"]
    cands = [n for n in text_groups(detected_nodes, image_w, image_h) + embellished if _title_like(n, image_w, image_h)]
    if not cands:
        return None
    best = max(cands, key=lambda n: n["bbox"][2] * n["bbox"][3] * n.get("detection_confidence", 0.0))
    return list(best["bbox"])


def _intersection(a: list, b: list) -> float:
    """Overlap area of two [x, y, w, h] boxes."""
    ix = max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    return ix * iy


def extract_markers(image_path: str, detected_nodes: list, logo_boxes: list = (),
                    max_motifs: int = MAX_MOTIFS) -> dict:
    """
    Motif and wordmark candidates from Stage 0b's detections on the master.

    wordmark: the text (or text-like embellishment) detection with the
      largest area × confidence that is title-sized (≥ 2.5% of the poster,
      ≥ 5% of its height, wider than tall, above its footer) and separates
      cleanly (≥ 55% of its outer ring cleared). None if nothing qualifies.
    motifs: illustration or embellishment detections (MOTIF_CLASSES) that
      separate cleanly (≥ 50% of the ring cleared, 10-85% of the crop
      cleared), stay under their class's share of the poster, and aren't a
      logo, the wordmark, or a duplicate of a higher-ranked motif. Ranked
      by class weight × confidence × (0.5 + normalised SIFT keypoint
      density); at most `max_motifs`.

    Returns {"wordmark": {...} or None, "motifs": [...]}, each entry holding
    the cut-out image (RGBA, trimmed) and its source box/confidence.
    """
    img = Image.open(image_path)
    img.load()
    W, H = img.size
    area = float(W * H)
    sift = cv2.SIFT_create()

    def candidate(node):
        rgba, box = grow_cut_out(img, node["bbox"])
        cleared, ring = separation(rgba)
        return {"bbox": box, "confidence": float(node.get("detection_confidence", 0.0)),
                "category": node.get("semantic_category"), "cleared": cleared, "ring_cleared": ring,
                "image": rgba}

    # Wordmark: title-sized text groups (lines merged), or text-like
    # embellishments (a wordmark YOLO classed as decoration)
    wordmark = None
    embellished = [n for n in detected_nodes or [] if n.get("semantic_category") == "embellishment"]
    title_like = [n for n in text_groups(detected_nodes, W, H) + embellished if _title_like(n, W, H)]
    for n in sorted(title_like, key=lambda n: -(n["bbox"][2] * n["bbox"][3]) * n["detection_confidence"]):
        c = candidate(n)
        if c["ring_cleared"] >= 0.55 and 0.10 <= c["cleared"] <= 0.85:
            c["image"] = trim(c["image"])
            wordmark = c
            break

    # Motifs
    taken = [list(b) for b in logo_boxes] + ([wordmark["bbox"]] if wordmark else [])
    motifs = []
    sources = sorted((n for n in detected_nodes or []
                      if n.get("semantic_category") in MOTIF_CLASSES
                      and n.get("detection_confidence", 0.0) >= MOTIF_MIN_CONF),
                     key=lambda n: -MOTIF_CLASSES[n["semantic_category"]]["weight"] * n["detection_confidence"])
    texts = [t["bbox"] for t in detected_nodes or []
             if t.get("semantic_category") == "text" and t.get("detection_confidence", 0.0) >= MOTIF_MIN_CONF]
    for n in sources:
        x, y, w, h = n["bbox"]
        limit = MOTIF_CLASSES[n["semantic_category"]]["max_area"]
        if w * h > limit * area or any(_overlap_ratio(n["bbox"], t) >= 0.3 for t in taken):
            continue
        # Lettering isn't decoration: a detection mostly covered by text
        # detections is a logotype or a stamp with words (e.g. a radio
        # station's name), not a motif.
        if sum(_intersection(n["bbox"], t) for t in texts) >= MOTIF_MAX_TEXT * w * h:
            continue
        # Social-media icons and similar small marks in the footer band
        # are contact details, not decoration (e.g. a Facebook "f").
        if y + h / 2.0 > 0.88 * H and w * h < 0.02 * area:
            continue
        c = candidate(n)
        if c["ring_cleared"] < 0.5 or not 0.10 <= c["cleared"] <= 0.85:
            continue
        c["image"] = trim(c["image"])
        if not _usable_motif(c["image"]):
            continue
        c["density"] = _keypoint_density(c["image"], sift)
        motifs.append(c)
        taken.append(n["bbox"])
    if motifs:
        top = max(m["density"] for m in motifs) or 1.0
        for m in motifs:
            m["score"] = (MOTIF_CLASSES[m["category"]]["weight"] * m["confidence"]
                          * (0.5 + m["density"] / top))
        motifs.sort(key=lambda m: -m["score"])
    return {"wordmark": wordmark, "motifs": motifs[:max_motifs]}


# ---------------------------------------------------------------------------
# Style kit: everything the renderer needs, saved next to the output
# ---------------------------------------------------------------------------

def build_style_kit(image_path: str, detected_nodes: list, output_dir: str, stem: str,
                    logo_boxes: list = (), use_wordmark: bool = True,
                    wordmark_path: str = None, motif_paths: list = None) -> dict:
    """
    Extracts the background, motifs and wordmark and saves each as a PNG in
    `output_dir`. `wordmark_path` / `motif_paths` are human-in-the-loop
    overrides (dashboard uploads or picks); `use_wordmark=False` always
    types the title instead. Returns a JSON-serialisable description:
        {"background": path,
         "motifs":   [{"path", "aspect", "bbox", "confidence", "source"}, ...],
         "wordmark": {"path", "aspect", "bbox", "confidence", "source"} or None}
    """
    os.makedirs(output_dir, exist_ok=True)
    background_path = os.path.join(output_dir, f"{stem}_background.png")
    text_free_background(image_path).save(background_path)

    markers = extract_markers(image_path, detected_nodes, logo_boxes)

    def saved(entry, name, source):
        path = os.path.join(output_dir, f"{stem}_{name}.png")
        entry["image"].save(path)
        return {"path": path, "aspect": entry["image"].width / max(1, entry["image"].height),
                "bbox": entry.get("bbox"), "confidence": entry.get("confidence"), "source": source}

    def from_file(path, source):
        with Image.open(path) as im:
            return {"path": path, "aspect": im.width / max(1, im.height), "bbox": None,
                    "confidence": None, "source": source}

    if motif_paths is not None:
        motifs = [from_file(p, "chosen") for p in motif_paths]
    else:
        motifs = [saved(m, f"motif_{i}", f"Stage 0c: YOLO {m['category']}")
                  for i, m in enumerate(markers["motifs"])]

    wordmark = None
    if wordmark_path:
        wordmark = from_file(wordmark_path, "uploaded")
    elif use_wordmark and markers["wordmark"]:
        wordmark = saved(markers["wordmark"], "wordmark", "Stage 0c: title artwork")

    return {"background": background_path, "motifs": motifs, "wordmark": wordmark}
