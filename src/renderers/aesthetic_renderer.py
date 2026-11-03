import base64
import colorsys
import functools
import io
import json
import os
import re
import textwrap
from xml.sax.saxutils import escape

from PIL import Image

# ---------------------------------------------------------------------------
# Colour & Luminance helpers
# ---------------------------------------------------------------------------

def _fit_font_size(text: str, max_width: float, max_size: float,
                   letter_spacing: float = 0.0, min_size: float = 6.0,
                   em_per_glyph: float = 0.62) -> float:
    """Largest font size (<= max_size) whose estimated rendered width fits
    max_width. `em_per_glyph` is the average glyph advance: ~0.62em suits
    regular/bold sans text; heavy (800-900) capitals need ~0.75em — checked
    against Cairo renders with the DejaVu Sans fallback, the widest of the
    fonts these stacks resolve to."""
    n = max(len(text), 1)
    fitted = (max_width - letter_spacing * (n - 1)) / (em_per_glyph * n)
    return max(min_size, min(max_size, fitted))


def _balanced_two_lines(text: str) -> list:
    """Splits text at the word boundary that makes its two lines closest in
    length (e.g. "TECH SUMMIT / 2026" rather than a 3-line textwrap), so a
    title never exceeds two lines. Single words stay on one line."""
    words = text.split()
    if len(words) < 2:
        return [text]
    best = min(range(1, len(words)),
               key=lambda i: max(len(" ".join(words[:i])), len(" ".join(words[i:]))))
    return [" ".join(words[:best]), " ".join(words[best:])]


def file_key(path: str) -> tuple:
    """A file's identity for the caches below: its path, size and
    modification time, so a file rewritten in place (a later session's logo
    crop at the same path) is read again."""
    st = os.stat(path)
    return (os.path.abspath(path), st.st_size, st.st_mtime_ns)


def _load_image(path: str, max_side: int = 512) -> tuple:
    """Loads an image file (PNG/JPG/WebP...) and returns (base64 PNG data URI,
    width/height), downscaled so the SVG stays small. (None, None) if
    unreadable. Cached per file and size: every canvas edit builds a new
    renderer with the same logos and artwork (notes §3.47)."""
    try:
        key = file_key(path)
    except OSError as e:
        print(f"  ⚠  Could not load logo image '{path}': {e} — using drawn badge")
        return None, None
    return _load_image_cached(key, max_side)


@functools.lru_cache(maxsize=64)
def _load_image_cached(key: tuple, max_side: int) -> tuple:
    path = key[0]
    try:
        with Image.open(path) as img:
            img = img.convert("RGBA")
            img.thumbnail((max_side, max_side))
            aspect = img.width / img.height if img.height else 1.0
            buf = io.BytesIO()
            img.save(buf, format="PNG")
    except (OSError, ValueError) as e:
        print(f"  ⚠  Could not load logo image '{path}': {e} — using drawn badge")
        return None, None
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii"), aspect


def _lab_centroid_to_hex(lab: list) -> str:
    """
    Converts a CIE L*a*b* centroid (OpenCV convention: L∈[0,255], a/b∈[0,255])
    to an sRGB hex colour string.
    """
    try:
        import numpy as np
        import cv2
        lab_pixel = np.array([[[float(lab[0]), float(lab[1]), float(lab[2])]]], dtype=np.float32)
        lab_pixel[:, :, 0] *= 100.0 / 255.0
        lab_pixel[:, :, 1] -= 128.0
        lab_pixel[:, :, 2] -= 128.0
        rgb = cv2.cvtColor(lab_pixel, cv2.COLOR_Lab2RGB)
        r, g, b = (int(c * 255) for c in rgb[0, 0])
        r, g, b = max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
        return f"#{r:02X}{g:02X}{b:02X}"
    except Exception:
        return "#1A202C"


def _hex_to_rgb01(hexcode: str) -> tuple:
    hexcode = hexcode.lstrip("#")
    return tuple(int(hexcode[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _rgb01_to_hex(rgb: tuple) -> str:
    r, g, b = (max(0.0, min(1.0, c)) for c in rgb)
    return f"#{int(round(r * 255)):02X}{int(round(g * 255)):02X}{int(round(b * 255)):02X}"


def _lighten(hexcode: str, amount: float) -> str:
    """Blends a colour toward white by `amount` (0 = unchanged, 1 = white)."""
    r, g, b = _hex_to_rgb01(hexcode)
    return _rgb01_to_hex((r + (1.0 - r) * amount, g + (1.0 - g) * amount, b + (1.0 - b) * amount))


def _relative_luminance(hexcode: str) -> float:
    """WCAG 2.1 relative luminance of an sRGB colour."""
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in _hex_to_rgb01(hexcode))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(hex_a: str, hex_b: str) -> float:
    la, lb = sorted((_relative_luminance(hex_a), _relative_luminance(hex_b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _ensure_contrast(fg_hex: str, bg_hex: str, minimum: float) -> str:
    """
    Darkens (on a light background) or lightens (on a dark one) `fg_hex` in
    small steps, keeping its hue, until it reaches `minimum` contrast
    against `bg_hex` — WCAG 2.1 SC 1.4.3 asks 4.5:1 for body text. Colours
    already legible are returned unchanged.
    """
    if _contrast_ratio(fg_hex, bg_hex) >= minimum:
        return fg_hex
    toward_black = _relative_luminance(bg_hex) >= 0.18
    r, g, b = _hex_to_rgb01(fg_hex)
    for step in range(1, 21):
        t = step / 20.0
        cand = _rgb01_to_hex((r * (1 - t), g * (1 - t), b * (1 - t)) if toward_black
                             else (r + (1 - r) * t, g + (1 - g) * t, b + (1 - b) * t))
        if _contrast_ratio(cand, bg_hex) >= minimum:
            return cand
    return "#000000" if toward_black else "#FFFFFF"


def _muted_variant(base_hex: str, background_is_light: bool) -> str:
    """
    Derives a legible secondary/caption colour from the extracted primary
    colour (same hue, desaturated), instead of a fixed slate grey that has
    no relationship to the source image.
    """
    r, g, b = _hex_to_rgb01(base_hex)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    target_l = 0.42 if background_is_light else 0.72
    r2, g2, b2 = colorsys.hls_to_rgb(h, target_l, min(s, 0.35))
    return _rgb01_to_hex((r2, g2, b2))


def _accent_from_hue(base_hex: str) -> str:
    """
    Derives a punchier, same-hue accent tint from a base colour. Used when
    K-Means (via the Elbow Method) finds only 2 clusters, leaving no 3rd
    centroid to draw a distinct accent from.
    """
    r, g, b = _hex_to_rgb01(base_hex)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    r2, g2, b2 = colorsys.hls_to_rgb(h, 0.58, max(s, 0.45))
    return _rgb01_to_hex((r2, g2, b2))


def _chroma(lab: list) -> float:
    """OpenCV LAB a*/b* are stored centred at 128; distance from that centre
    is a proxy for how saturated/colourful (vs. neutral grey) a centroid is."""
    a, b = float(lab[1]) - 128.0, float(lab[2]) - 128.0
    return (a * a + b * b) ** 0.5


def _palette_from_centroids(centroids: list) -> dict:
    """
    Derives a role-based colour palette (primary, accent, background) plus
    a derived muted tone from the master layout's K-Means centroids.

    The Elbow Method (VisionExtractor._select_optimal_k_centroids) means the
    centroid count varies per image — k in [2, 6] — rather than always
    being exactly 3, so this assigns roles by perceptual lightness/chroma
    instead of assuming a fixed-length list:
      - darkest centroid                      -> primary
      - lightest centroid                     -> background
      - most chromatic of the remaining ones  -> accent
      - only 2 centroids (no 3rd to draw an accent from) -> accent is a
        punchier same-hue tint of primary instead

    Previously this only ever used exactly 2 of a *fixed* 3 centroids — a
    3rd was computed and silently discarded — and background/muted were
    hardcoded regardless of the source image, so a master layout's own
    background/border colours never actually reached the rendered output.
    """
    if not centroids or len(centroids) < 2:
        return {
            "primary":    "#003366",   # Deep Navy
            "accent":     "#D4AF37",   # Metallic Gold
            "background": "#FDFFFF",   # Crisp Ivory White
            "card_bg":    "#FFFFFF",
            "muted":      "#5A6A80",
            "panel":      "#FFFFFF",
            "band":       "#8A6D12",
            "card_dark":  "#101624",
        }

    entries = sorted(
        ((float(c[0]), _chroma(c), _lab_centroid_to_hex(c)) for c in centroids),
        key=lambda e: e[0],
    )  # (lightness, chroma, hex), ascending lightness

    _,          _, primary_hex    = entries[0]    # darkest
    lightest_l, _, background_hex = entries[-1]   # lightest
    middle_entries = entries[1:-1]

    if middle_entries:
        _, _, accent_hex = max(middle_entries, key=lambda e: e[1])  # most chromatic
    else:
        accent_hex = _accent_from_hue(primary_hex)

    # Guard against illegible canvases: if even the lightest extracted
    # centroid is still fairly dark (e.g. a bold, saturated poster with no
    # light region), lighten it toward white rather than rendering text on
    # a dark, low-contrast background.
    if lightest_l < 170:
        background_hex = _lighten(background_hex, amount=0.6)

    # Legibility guard, the mirror of the background guard above: a poster
    # whose darkest centroid is still mid-tone (e.g. a pastel design) would
    # otherwise give washed-out text. Primary text gets 4.5:1 against both
    # the background and the white card/pill it also sits on; muted captions
    # get 4.5:1 against the background too (WCAG 2.1 SC 1.4.3).
    primary_hex = _ensure_contrast(primary_hex, background_hex, 4.5)
    primary_hex = _ensure_contrast(primary_hex, "#FFFFFF", 4.5)
    muted_hex = _ensure_contrast(
        _muted_variant(primary_hex, background_is_light=lightest_l >= 128), background_hex, 4.5)

    # The most saturated centroid overall, when it is genuinely colourful,
    # makes a stronger accent (bands, rules, pill outlines) than a
    # mid-lightness one: vivid posters otherwise came out grey or beige.
    most_chromatic = max(entries, key=lambda e: e[1])
    if most_chromatic[1] >= 25.0:
        accent_hex = most_chromatic[2]

    return {
        "primary":    primary_hex,
        "accent":     accent_hex,
        "background": background_hex,
        "card_bg":    "#FFFFFF",
        "muted":      muted_hex,
        # Certificate panel: near-white carrying a hint of the poster's hue.
        "panel":      _lighten(background_hex, 0.82),
        # Solid bands (banner, role band): the accent, deepened until white
        # text on it reaches 4.5:1.
        "band":       _ensure_contrast(accent_hex, "#FFFFFF", 4.5),
        # An event-ID card on a dark master: the darkest centroid, deepened.
        "card_dark":  _rgb01_to_hex(tuple(c * 0.55 for c in _hex_to_rgb01(entries[0][2]))),
    }


# ---------------------------------------------------------------------------
# Default Content Tables
# ---------------------------------------------------------------------------

_DEFAULT_CERT_MOCK = {
    "{{Institution_Logo}}":     "CSPC",
    "{{Issuing_Organization}}": "CAMARINES SUR POLYTECHNIC COLLEGES",
    "{{Certificate_Title}}":    "CERTIFICATE OF RECOGNITION",
    "{{Presentation_Line}}":    "is hereby proudly awarded to",
    "{{Student_Name}}":         "Guiller Angelo Hermoso",
    "{{Citation_Body}}":        "For exemplary academic performance and distinguished technical contributions toward the automated layout orchestration framework.",
    "{{Date_Issued}}":          "August 27, 2026",
    "{{Certificate_ID}}":       "ID: CSPC-2026-001",
    "{{Signature_Blocks}}_0":   "Dr. Juan dela Cruz\nCollege President",
    "{{Signature_Blocks}}_1":   "Prof. Ana Reyes\nDean, CCS",
    "{{Signature_Blocks}}_2":   "Engr. Rico Santos\nAdviser",
}

_DEFAULT_ID_MOCK = {
    "{{Organization_Logos}}":  "CSPC",
    "{{Organization_Header}}": "Camarines Sur Polytechnic Colleges\nCollege of Computer Studies",
    "{{Event_Title}}":         "Tech Summit 2026",
    "{{Event_Details}}":       "August 27, 2026 · CSPC Gymnasium",
    "{{Participant_Name}}":    "Guiller",
    "{{Participant_Role}}":    "Organizer",
}


def default_content(domain: str) -> dict:
    """The sample content a format renders with when no payload is given."""
    return dict(_DEFAULT_ID_MOCK if domain == "identification_card" else _DEFAULT_CERT_MOCK)


# ---------------------------------------------------------------------------
# Main Aesthetic SVG Renderer
# ---------------------------------------------------------------------------

# Figure 2's "User Injected" administrative typography (Table 1: brand
# typographic compliance), validated before orchestration by
# typography_schema.validate_typography.
DEFAULT_TYPOGRAPHY = {
    "family": "Montserrat, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "weight": 700,
    "base_size": 48,
}


@functools.lru_cache(maxsize=8)
def _background_uri(key: tuple, width: int, height: int) -> str:
    """The text-free background at half the canvas size, as a JPEG data URI
    (cached per file and size; notes §3.47)."""
    from stylistic_markers import cover

    with Image.open(key[0]) as bg:
        layer = cover(bg.convert("RGB"), width, height)
    buf = io.BytesIO()
    layer.save(buf, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _hex_mean(image, bbox) -> str:
    """Mean colour of the composed background under a box, as hex."""
    x, y, w, h = bbox
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(image.width, int(x + w)), min(image.height, int(y + h))
    if x1 <= x0 or y1 <= y0:
        return "#FFFFFF"
    r, g, b = image.crop((x0, y0, x1, y1)).resize((1, 1), Image.BOX).getpixel((0, 0))[:3]
    return f"#{r:02X}{g:02X}{b:02X}"


class AestheticSVGRenderer:
    def __init__(
        self,
        canvas_width: int = 1200,
        canvas_height: int = 900,
        original_filename: str = "master_template",
        color_centroids: list = None,
        mock_data: dict = None,
        domain_context: str = "academic_certificate",
        font_family: str = None,
        logo_image_path: str = None,
        logo_row_paths: list = None,
        style_kit: dict = None,
        typography: dict = None,
        styles: dict = None,
    ):
        self.canvas_w = float(canvas_width)
        self.canvas_h = float(canvas_height)
        self.original_filename = original_filename
        self.domain = domain_context
        # Real logo artwork — user-uploaded files or Stage 0b crops of the
        # master layout's logos (resolved in pipeline.py). `logo_data_uri`
        # fills a single logo slot (certificate seal); `logo_row` fills a
        # multi-logo strip (event ID). None/empty falls back to a drawn badge.
        self.logo_data_uri = _load_image(logo_image_path)[0] if logo_image_path else None
        self.logo_row = [img for img in (_load_image(p) for p in (logo_row_paths or []))
                         if img[0]]

        # Stage 0c's style kit: text-free master background, motifs, and the
        # event's title artwork (stylistic_markers.build_style_kit). Without
        # one (no master image), outputs fall back to the flat bordered card.
        self.style_kit = style_kit or {}
        wordmark = self.style_kit.get("wordmark")
        self.wordmark_uri = _load_image(wordmark["path"], max_side=1024)[0] if wordmark else None
        self._motif_uris = {}
        self._raster = None       # composed background, set per render
        self._panel = None
        self._layers = None       # the archetype's frame (decor.frame_layers), per render
        self._align = "center"    # the archetype's alignment, per render

        # Palette and typography
        self.palette = _palette_from_centroids(color_centroids)
        # Table 1 (p. 49): administrative typography is a user-injected
        # constraint, not machine-extracted — font family, weight and the
        # baseline size the type scale is built on.
        self.typography = dict(DEFAULT_TYPOGRAPHY)
        self.typography.update({k: v for k, v in (typography or {}).items() if v})
        if font_family:
            self.typography["family"] = font_family
        self.font_family = self.typography["family"]
        self.heading_weight = str(int(self.typography["weight"]))
        self.base_size = float(self.typography["base_size"])

        # Content mapping
        self.mock_data = mock_data or default_content(domain_context)

        # The designer's per-element styles from Step 2 (node id → {fill,
        # bold, italic, align, opacity, flip, image}); applied after a node
        # is drawn, so an unstyled node renders as before (notes §3.53).
        self.styles = styles or {}
        self.style_contrast = {}   # node id → its styled text colour's contrast, per render
        self.bg_boxes = {}         # background item → its box, per render (notes §3.64)
        self.text_sizes = {}       # text node → the largest font size it was drawn at (§3.65)

    def _clean_node_id(self, node_id: str) -> str:
        return self.mock_data.get(
            node_id,
            node_id.replace("{", "").replace("}", "").replace("_", " ").strip(),
        )

    def _wrap_text_lines(self, text: str, max_chars: int) -> list:
        max_chars = max(8, int(max_chars))
        if "\n" in text:
            lines = []
            for rl in text.split("\n"):
                wrapped = textwrap.wrap(rl, width=max_chars)
                lines.extend(wrapped if wrapped else [""])
            return lines
        return textwrap.wrap(text, width=max_chars) if len(text) > max_chars else [text]

    def _fit_wrapped(self, text: str, w: float, h: float, size: float,
                     min_size: float = 10.0, em: float = 0.58, line: float = 1.35) -> tuple:
        """Largest size <= `size` at which `text`, wrapped to width `w`,
        fits `h` — so long citations shrink instead of spilling out of
        their box."""
        while True:
            lines = self._wrap_text_lines(text, w / (size * em))
            if len(lines) * size * line <= h or size <= min_size:
                return lines, size
            size = max(min_size, size * 0.92)

    # ------------------------------------------------------------------
    # Background layer
    # ------------------------------------------------------------------

    def _build_border_elements(self) -> list:
        """The flat bordered card used when no master image is available:
        palette background, double border, corner accents."""
        p = self.palette["primary"]
        a = self.palette["accent"]
        m1, m2 = 18.0, 26.0
        elements = [
            f'<rect width="{self.canvas_w}" height="{self.canvas_h}" fill="{self.palette["background"]}" />',
            f'<rect x="{m1}" y="{m1}" width="{self.canvas_w - 2*m1}" height="{self.canvas_h - 2*m1}" fill="none" stroke="{p}" stroke-width="2.5" rx="3" />',
            f'<rect x="{m2}" y="{m2}" width="{self.canvas_w - 2*m2}" height="{self.canvas_h - 2*m2}" fill="none" stroke="{a}" stroke-width="1.2" rx="2" />',
        ]
        corner_sz = 10.0
        for cx, cy in [(m1, m1), (self.canvas_w - m1 - corner_sz, m1),
                       (m1, self.canvas_h - m1 - corner_sz),
                       (self.canvas_w - m1 - corner_sz, self.canvas_h - m1 - corner_sz)]:
            elements.append(f'<rect x="{cx}" y="{cy}" width="{corner_sz}" height="{corner_sz}" fill="{a}" />')
        return elements

    def _background_elements(self, decor_nodes: list, content_nodes: list = (),
                             archetype: dict = None) -> list:
        """
        The master's text-free background scaled to cover the canvas and the
        archetype's frame (decor.frame_layers): the certificate panel with
        its double border, a split layout's art column, a header banner, an
        event-ID card. Also composes the same stack as a raster (plus motifs)
        for choosing legible text colours.
        """
        archetype = archetype or {}
        self._align = archetype.get("align", "center")
        background = self.style_kit.get("background")
        if not background:
            self._raster, self._panel, self._layers = None, None, None
            return self._build_border_elements()

        from decor import (PANEL_OPACITY, WATERMARK_OPACITY, art_image_box, background_is_dark,
                           compose_background, frame_layers, watermark_box)
        from stylistic_markers import cover

        W, H = self.canvas_w, self.canvas_h
        layers = frame_layers(self.domain, archetype.get("frame", "panel"), W, H, list(content_nodes),
                              self.palette, dark=background_is_dark(background))
        # The designer's background edits (notes §3.64): each item of the
        # background layer can be moved, resized, replaced, faded or hidden
        # without touching the content
        edits = {k: v for k, v in self.styles.items() if k.startswith("bg_")}
        e = lambda k: edits.get(k) or {}
        if layers["panel"] and e("bg_panel").get("box"):
            layers["panel"] = [float(v) for v in e("bg_panel")["box"]]
        self._layers, self._panel = layers, layers["panel"]
        panel_hex = self.palette["panel"]
        wordmark = self.style_kit.get("wordmark")
        art = wordmark or (self.style_kit.get("motifs") or [None])[0]
        self._raster = compose_background(background, int(W), int(H), decor_nodes,
                                          panel_rgb=tuple(int(panel_hex[i:i + 2], 16) for i in (1, 3, 5)),
                                          layers=layers, watermark=wordmark, art=art, edits=edits)
        self.bg_boxes = {}

        def item(key, box, drawn, own_opacity=False):
            """One background item, wrapped for the canvas (data-kind
            "background"), with the designer's flip and, unless the drawing
            carries it itself, opacity."""
            self.bg_boxes[key] = [round(float(v), 1) for v in box]
            if e(key).get("hidden"):
                return []
            x, _, w, _ = (float(v) for v in box)
            wrap = [f'transform="translate({2 * x + w:.1f},0) scale(-1,1)"'] if e(key).get("flip") else []
            if not own_opacity and e(key).get("opacity") is not None:
                wrap.append(f'opacity="{float(e(key)["opacity"]):.2f}"')
            inner = [f'<g {" ".join(wrap)}>'] + drawn + ["</g>"] if wrap else drawn
            return [f'<g data-node-id="{key}" data-kind="background">'] + inner + ["</g>"]

        backdrop = e("bg_backdrop")
        uri = _background_uri(file_key(backdrop.get("image") or background), max(1, int(W // 2)), max(1, int(H // 2)))
        elements = [f'<rect width="{W}" height="{H}" fill="#FFFFFF" />'] + item("bg_backdrop", [0, 0, W, H], [
            f'<image x="0" y="0" width="{W}" height="{H}" preserveAspectRatio="none" xlink:href="{uri}" />'])
        p, a = self.palette["primary"], self.palette["accent"]
        if self._panel and layers["panel_style"] == "panel":
            x, y, w, h = self._panel
            elements += item("bg_panel", self._panel, [
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="14" '
                f'fill="{panel_hex}" fill-opacity="{PANEL_OPACITY}" />',
                f'<rect x="{x + 10:.1f}" y="{y + 10:.1f}" width="{w - 20:.1f}" height="{h - 20:.1f}" '
                f'rx="8" fill="none" stroke="{p}" stroke-width="2" />',
                f'<rect x="{x + 17:.1f}" y="{y + 17:.1f}" width="{w - 34:.1f}" height="{h - 34:.1f}" '
                f'rx="5" fill="none" stroke="{a}" stroke-width="1.2" />',
            ])
        elif self._panel:  # event-ID card
            x, y, w, h = self._panel
            elements += item("bg_panel", self._panel, [
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="22" '
                f'fill="{layers["panel_fill"]}" fill-opacity="{layers["panel_opacity"]}" '
                f'stroke="{a}" stroke-width="2" />'])
        for o in layers["overlays"]:
            x, y, w, h = o["box"]
            elements.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                            f'rx="{o.get("rx", 0)}" fill="{o["fill"]}" fill-opacity="{o["opacity"]}" />')
        if layers["watermark"] and self._panel and wordmark and self.wordmark_uri:
            # The event's title artwork, faint, behind the certificate text.
            mark = e("bg_watermark")
            wx, wy, ww, wh = mark.get("box") or watermark_box(self._panel, wordmark["aspect"])
            uri = _load_image(mark["image"], max_side=1024)[0] if mark.get("image") else self.wordmark_uri
            elements += item("bg_watermark", [wx, wy, ww, wh], own_opacity=True, drawn=[
                f'<image x="{wx:.1f}" y="{wy:.1f}" width="{ww:.1f}" height="{wh:.1f}" '
                f'preserveAspectRatio="xMidYMid meet" opacity="{float(mark.get("opacity", WATERMARK_OPACITY)):.2f}" '
                f'xlink:href="{uri}" />'])
        if layers["art_box"] and art:
            # A split layout's art column shows the title artwork (or the top
            # motif) at full strength on the master's own background.
            column = e("bg_art")
            uri = (_load_image(column["image"], max_side=1024)[0] if column.get("image")
                   else self.wordmark_uri if art is wordmark else _load_image(art["path"], max_side=1024)[0])
            if uri:
                ax, ay, aw, ah = column.get("box") or art_image_box(layers["art_box"], art["aspect"])
                elements += item("bg_art", [ax, ay, aw, ah], own_opacity=True, drawn=[
                    f'<image x="{ax:.1f}" y="{ay:.1f}" width="{aw:.1f}" height="{ah:.1f}" '
                    f'preserveAspectRatio="xMidYMid meet" opacity="{float(column.get("opacity", 1.0)):.2f}" '
                    f'xlink:href="{uri}" />'])
        return elements

    def _render_decor(self, node: dict) -> list:
        """A motif from the master layout, mirrored when placed on the right
        so pairs face inward."""
        path = node.get("motif_path")
        if path not in self._motif_uris:
            self._motif_uris[path] = _load_image(path, max_side=512)[0] if path else None
        uri = self._motif_uris[path]
        if not uri:
            return []
        x, y, w, h = node["bbox"]
        image = (f'<image x="0" y="0" width="{w:.1f}" height="{h:.1f}" '
                 f'preserveAspectRatio="xMidYMid meet" xlink:href="{uri}" />')
        if node.get("flip"):
            return [f'<g transform="translate({x + w:.1f},{y:.1f}) scale(-1,1)">{image}</g>']
        return [f'<g transform="translate({x:.1f},{y:.1f})">{image}</g>']

    def _text_fill(self, bbox: list, preferred: str) -> tuple:
        """
        (fill colour, needs shadow) for text over the composed background:
        the palette colour when it reaches 4.5:1 against what's actually
        under the text (WCAG 2.1 SC 1.4.3), else white with a soft shadow on
        darker art, else the palette colour pushed to 4.5:1.
        """
        if self._raster is None:
            return preferred, False
        under = _hex_mean(self._raster, bbox)
        if _contrast_ratio(preferred, under) >= 4.5:
            return preferred, False
        if _contrast_ratio("#FFFFFF", under) >= 2.2:
            return "#FFFFFF", True
        return _ensure_contrast(preferred, under, 4.5), False

    def _text_elements(self, box: list, lines: list, size: float,
                       weight: str, fill: str, shadow: bool, spacing: str = "0",
                       style: str = "normal", line: float = 1.35) -> list:
        """Lines of text vertically centred in the node's box — centred on
        it, or flush with its left edge in a left-aligned archetype — with an
        offset dark copy underneath when `shadow` (a text shadow every SVG
        renderer, Cairo included, draws the same way)."""
        x, top, w, h = box
        if self._align == "left":
            tx, anchor = x, "start"
        else:
            tx, anchor = x + w / 2.0, "middle"
        line_h = size * line
        start = top + (h - len(lines) * line_h) / 2.0 + size * 0.85
        out = []
        for i, text in enumerate(lines):
            y = start + i * line_h
            attrs = (f'font-family="{self.font_family}" font-size="{size:.1f}" font-weight="{weight}" '
                     f'font-style="{style}" letter-spacing="{spacing}" text-anchor="{anchor}"')
            if shadow:
                out.append(f'<text x="{tx + size * 0.05:.1f}" y="{y + size * 0.07:.1f}" {attrs} '
                           f'fill="#000000" fill-opacity="0.45">{escape(text)}</text>')
            out.append(f'<text x="{tx:.1f}" y="{y:.1f}" {attrs} fill="{fill}">{escape(text)}</text>')
        return out

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    def _render_logo(self, x, y, w, h, content) -> list:
        """Places the real logo artwork, fitted inside the node's bbox without
        distortion; falls back to the drawn seal badge when none is available."""
        if not self.logo_data_uri:
            return self._render_logo_badge(x, y, w, h, content)
        align = "xMinYMid" if self._align == "left" else "xMidYMid"
        return [
            f'<image x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'preserveAspectRatio="{align} meet" xlink:href="{self.logo_data_uri}" />'
        ]

    def _render_logo_row(self, x, y, w, h, content) -> list:
        """Lays the organisation logos out side by side, left to right, at a
        shared height, centred in the node's bbox — the logo cluster every
        one of the 18 sample event IDs carries along its top."""
        row = self.logo_row or ([(self.logo_data_uri, 1.0)] if self.logo_data_uri else [])
        if not row:
            return self._render_logo_badge(x, y, w, h, content)
        gap = h * 0.25
        natural_w = sum(h * aspect for _, aspect in row) + gap * (len(row) - 1)
        scale = min(1.0, w / natural_w) if natural_w > 0 else 1.0
        logo_h = h * scale
        cursor = x if self._align == "left" else x + (w - natural_w * scale) / 2.0
        top = y + (h - logo_h) / 2.0
        elements = []
        for uri, aspect in row:
            logo_w = logo_h * aspect
            elements.append(
                f'<image x="{cursor:.1f}" y="{top:.1f}" width="{logo_w:.1f}" height="{logo_h:.1f}" '
                f'preserveAspectRatio="xMidYMid meet" xlink:href="{uri}" />'
            )
            cursor += logo_w + gap * scale
        return elements

    def _render_name_pill(self, x, y, w, h, content) -> list:
        """Event-ID participant name: bold caps on a light rounded pill, the
        most common name treatment in the sample IDs."""
        p = self.palette["primary"]
        a = self.palette["accent"]
        text = content.upper()
        font_size = _fit_font_size(text, max_width=w * 0.86, max_size=h * 0.56, letter_spacing=2.0,
                                   em_per_glyph=0.75)
        return [
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{h / 2.0:.1f}" '
            f'fill="{self.palette["card_bg"]}" stroke="{a}" stroke-width="2.5" />',
            f'<text x="{x + w / 2.0:.1f}" y="{y + h / 2.0:.1f}" font-family="{self.font_family}" '
            f'font-size="{font_size:.1f}" font-weight="900" letter-spacing="2.0" fill="{p}" '
            f'text-anchor="middle" dominant-baseline="central">{escape(text)}</text>',
        ]

    def _render_role_band(self, x, y, w, h, content) -> list:
        """Event-ID role (ORGANIZER, PARTICIPANT...): light caps on a solid
        band in the poster's accent colour, deepened until white text on it
        reaches 4.5:1 — like the sample IDs' footer bands."""
        text = content.upper()
        band = self.palette["band"]
        rx = 6
        if self._layers and self._layers.get("role_band") == "full":
            x, w, rx = 0.0, self.canvas_w, 0  # edge to edge, like the samples' footer bands
        font_size = _fit_font_size(text, max_width=w * 0.86, max_size=h * 0.5, letter_spacing=4.0,
                                   em_per_glyph=0.72)
        return [
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{band}" />',
            f'<text x="{x + w / 2.0:.1f}" y="{y + h / 2.0:.1f}" font-family="{self.font_family}" '
            f'font-size="{font_size:.1f}" font-weight="bold" letter-spacing="4.0" '
            f'fill="#FFFFFF" text-anchor="middle" dominant-baseline="central">{escape(text)}</text>',
        ]

    def _render_logo_badge(self, x, y, w, h, content) -> list:
        """Renders an institutional seal badge with emblem geometry."""
        p = self.palette["primary"]
        a = self.palette["accent"]
        cx = x + (w / 2.0)
        cy = y + (h / 2.0)
        r = min(w, h) * 0.42
        font_size = _fit_font_size(content, max_width=r * 1.5, max_size=r * 0.4, letter_spacing=1.5)
        return [
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{self.palette["card_bg"]}" stroke="{a}" stroke-width="2.5" />',
            f'<circle cx="{cx}" cy="{cy}" r="{r - 4}" fill="none" stroke="{p}" stroke-width="1" stroke-dasharray="3,3" />',
            f'<text x="{cx}" y="{cy}" font-family="{self.font_family}" font-weight="bold" font-size="{font_size:.1f}" fill="{p}" text-anchor="middle" dominant-baseline="central" letter-spacing="1.5">{escape(content)}</text>'
        ]

    def _render_image_node(self, x, y, w, h, node_id, content) -> list:
        """Dispatches an image node to the renderer for its role, by schema name."""
        name = node_id.lower()
        if "logos" in name:
            return self._render_logo_row(x, y, w, h, content)
        if "logo" in name:
            return self._render_logo(x, y, w, h, content)
        return self._render_logo_badge(x, y, w, h, content)

    def _render_text_node(self, x, y, w, h, node_id, content) -> list:
        """
        Renders a text node. Sizes follow a type scale on the user-injected
        base size B (Figure 2), each capped by what fits the node's box:
        certificate title 1.1 B, recipient name 1.0 B, organisation,
        presentation line and citation 0.36 B, date/ID 0.3 B; event-ID
        header 0.34 B, details 0.38 B, title up to 1.8 B.
        """
        B = self.base_size
        p = self.palette["primary"]
        muted = self.palette["muted"]
        bbox = [x, y, w, h]

        # Event-ID nodes with their own shape treatment
        if "Participant_Name" in node_id:
            return self._render_name_pill(x, y, w, h, content)
        if "Participant_Role" in node_id:
            return self._render_role_band(x, y, w, h, content)

        if "Event_Title" in node_id:
            if self.wordmark_uri:
                # The event's own title artwork, cut from the master layout.
                return [f'<image x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                        f'preserveAspectRatio="xMidYMid meet" xlink:href="{self.wordmark_uri}" />']
            text = content.upper()
            lines = [text] if len(text) <= 12 else _balanced_two_lines(text)
            size = _fit_font_size(max(lines, key=len), max_width=w * 0.95,
                                  max_size=min(h / (len(lines) * 1.35), 1.8 * B),
                                  letter_spacing=1.0, em_per_glyph=0.75)
            fill, shadow = self._text_fill(bbox, p)
            return self._text_elements(bbox, lines, size, "900", fill, shadow, spacing="1.0")

        if "Organization_Header" in node_id:
            lines = self._wrap_text_lines(content.upper(), max_chars=60)
            size = max(9.0, min(0.34 * B, h / (len(lines) * 1.35)))
            fill, shadow = self._text_fill(bbox, muted)
            return self._text_elements(bbox, lines, size, "600", fill, shadow, spacing="1.5")

        if "Event_Details" in node_id:
            lines, size = self._fit_wrapped(content, w, h, max(11.0, min(0.38 * B, h * 0.42)))
            fill, shadow = self._text_fill(bbox, muted)
            return self._text_elements(bbox, lines, size, "600", fill, shadow, spacing="0.8")

        if "Organization" in node_id or "Issuing" in node_id:
            lines, size = self._fit_wrapped(content.upper(), w, h,
                                            max(12.0, min(0.36 * B, h * 0.5)), em=0.66)
            fill, shadow = self._text_fill(bbox, muted)
            return self._text_elements(bbox, lines, size, "600", fill, shadow, spacing="2.0")

        if "Title" in node_id and "Certificate" in node_id:
            size = _fit_font_size(content, max_width=w * 0.95,
                                  max_size=max(20.0, min(1.1 * B, h * 0.62)), letter_spacing=1.0)
            fill, shadow = self._text_fill(bbox, p)
            return self._text_elements(bbox, [content], size, self.heading_weight, fill, shadow,
                                       spacing="1.0")

        if "Presentation" in node_id:
            lines, size = self._fit_wrapped(content, w, h, max(12.0, min(0.36 * B, h * 0.5)))
            fill, shadow = self._text_fill(bbox, muted)
            return self._text_elements(bbox, lines, size, "normal", fill, shadow,
                                       spacing="0.5", style="italic")

        if "Student_Name" in node_id or "Name" in node_id:
            size = _fit_font_size(content, max_width=w * 0.95,
                                  max_size=max(20.0, min(1.0 * B, h * 0.62)), letter_spacing=0.8,
                                  em_per_glyph=0.66)
            fill, shadow = self._text_fill(bbox, p)
            return self._text_elements(bbox, [content], size, self.heading_weight, fill, shadow,
                                       spacing="0.8")

        if "Citation" in node_id:
            lines, size = self._fit_wrapped(content, w, h, max(12.0, 0.36 * B), min_size=10.0, em=0.55)
            fill, shadow = self._text_fill(bbox, _ensure_contrast("#334155", self.palette["panel"], 4.5))
            return self._text_elements(bbox, lines, size, "normal", fill, shadow, spacing="0.2")

        # Date, certificate ID, etc.
        lines, size = self._fit_wrapped(content, w, h, max(11.0, min(0.3 * B, h * 0.5)))
        fill, shadow = self._text_fill(bbox, muted)
        return self._text_elements(bbox, lines, size, "normal", fill, shadow, spacing="0.5")

    def _render_signature_block(self, x, y, w, h, content) -> list:
        """Renders a signature line with signatory name and title on separate lines."""
        B = self.base_size
        fill, shadow = self._text_fill([x, y, w, h], self.palette["primary"])
        cx = x + (w / 2.0)
        line_y = y + (h * 0.45)
        parts = content.split("\n")
        name = parts[0].strip() if parts else content
        title = parts[1].strip() if len(parts) > 1 else ""
        name_size = max(11.0, min(0.28 * B, h * 0.3))
        elements = [
            f'<line x1="{x + 10}" y1="{line_y:.1f}" x2="{x + w - 10}" y2="{line_y:.1f}" '
            f'stroke="{fill}" stroke-width="1.2" opacity="0.85" />',
            f'<text x="{cx:.1f}" y="{line_y + name_size * 1.35:.1f}" font-family="{self.font_family}" '
            f'font-size="{name_size:.1f}" font-weight="bold" fill="{fill}" text-anchor="middle">{escape(name)}</text>',
        ]
        if title:
            muted, _ = self._text_fill([x, y, w, h], self.palette["muted"])
            elements.append(
                f'<text x="{cx:.1f}" y="{line_y + name_size * 2.5:.1f}" font-family="{self.font_family}" '
                f'font-size="{name_size * 0.88:.1f}" font-weight="normal" fill="{muted}" '
                f'text-anchor="middle">{escape(title)}</text>'
            )
        return elements

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # The designer's styles (Step 2's Style tools)
    # ------------------------------------------------------------------

    def _apply_style(self, node: dict, elements: list) -> list:
        """A node's drawn elements with the designer's style: a replacement
        picture; font, weight, colour, italic and alignment on its text (the
        shadow copies keep their colour); opacity and a horizontal flip on
        the group. A node without a style comes back unchanged."""
        style = self.styles.get(node["node_id"])
        if not style:
            return elements
        x, y, w, h = (float(v) for v in node["bbox"])
        if style.get("image"):
            uri = _load_image(style["image"], max_side=1024)[0]
            if uri:
                elements = [f'<image x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                            f'preserveAspectRatio="xMidYMid meet" xlink:href="{uri}" />']
        if any(k in style for k in ("fill", "bold", "italic", "align", "font", "weight")):
            shaped = any(e.startswith("<rect") for e in elements)          # a pill or band behind the text
            elements = [self._style_text(e, style, x, w, shaped) if e.startswith("<text") else e
                        for e in elements]
            if style.get("fill"):
                nid = node["node_id"]
                under = (self.palette["card_bg"] if "Participant_Name" in nid
                         else self.palette["band"] if "Participant_Role" in nid
                         else _hex_mean(self._raster, [x, y, w, h]) if self._raster is not None
                         else self.palette["background"])
                self.style_contrast[nid] = round(_contrast_ratio(style["fill"], under), 2)
        wrap = []
        if style.get("flip"):
            wrap.append(f'transform="translate({2 * x + w:.1f},0) scale(-1,1)"')
        if style.get("opacity") is not None and float(style["opacity"]) < 1:
            wrap.append(f'opacity="{float(style["opacity"]):.2f}"')
        return [f'<g {" ".join(wrap)}>'] + elements + ["</g>"] if wrap else elements

    _ATTR = re.compile(r'\s([a-z-]+)="([^"]*)"')
    _ANCHOR = {"left": "start", "center": "middle", "right": "end"}

    def _style_text(self, element: str, style: dict, x: float, w: float, shaped: bool) -> str:
        head, rest = element.split(">", 1)
        attrs = dict(self._ATTR.findall(head))
        shadow = attrs.get("fill") == "#000000" and attrs.get("fill-opacity") == "0.45"
        if style.get("fill") and not shadow:
            attrs["fill"] = style["fill"]
        if style.get("font"):
            attrs["font-family"] = style["font"].replace('"', "'")
        if style.get("weight"):
            attrs["font-weight"] = str(int(style["weight"]))
        elif "bold" in style:
            attrs["font-weight"] = "700" if style["bold"] else "400"
        if "italic" in style:
            attrs["font-style"] = "italic" if style["italic"] else "normal"
        anchor = self._ANCHOR.get(style.get("align"))
        if anchor:
            pad = 0.06 * w if shaped else 0.0
            at = {"start": x + pad, "middle": x + w / 2.0, "end": x + w - pad}
            old = attrs.get("text-anchor", "start")
            old_at = {"start": x if not shaped else x + pad, "middle": x + w / 2.0, "end": x + w}[old]
            attrs["x"] = f"{float(attrs['x']) + at[anchor] - old_at:.1f}"
            attrs["text-anchor"] = anchor
        return "<text " + " ".join(f'{k}="{v}"' for k, v in attrs.items()) + ">" + rest

    def render_nodes(self, nodes: list, output_path: str, with_border: bool = True,
                     archetype: dict = None) -> str:
        """
        Renders a solved layout to an SVG file: background layer and the
        archetype's frame, motifs (decor nodes), then every content node.
        Each node's elements are wrapped in <g data-node-id="..."> so the
        Figure 3 canvas can select and move them. Returns the output path.
        """
        decor = [n for n in nodes if n.get("structural_class") == "decor"]
        content_nodes = [n for n in nodes if n.get("structural_class") != "decor"]

        if self.style_kit.get("background") or with_border:
            svg_elements = self._background_elements(decor, content_nodes, archetype)
        else:
            self._raster, self._layers = None, None
            self._align = (archetype or {}).get("align", "center")
            svg_elements = [f'<rect width="{self.canvas_w}" height="{self.canvas_h}" '
                            f'fill="{self.palette["background"]}" />']

        def group(node, elements):
            kind = node.get("structural_class", "text_node")
            return ([f'<g data-node-id="{escape(node["node_id"])}" data-kind="{kind}">'] + elements + ['</g>']
                    if elements else [])

        for node in decor:
            svg_elements.extend(group(node, self._apply_style(node, self._render_decor(node))))

        base = self.base_size
        for node in content_nodes:
            # a text the designer resized scales its type with the box (§3.62)
            self.base_size = base * float(node.get("text_scale") or 1.0)
            x, y, w, h = node['bbox']
            node_id = node['node_id']
            struct_class = node.get('structural_class', 'text_node')
            content = self._clean_node_id(node_id)
            if struct_class == "image_node":
                elements = self._render_image_node(x, y, w, h, node_id, content)
            elif struct_class == "repeating_group":
                elements = self._render_signature_block(x, y, w, h, content)
            else:
                elements = self._render_text_node(x, y, w, h, node_id, content)
            sizes = [float(v) for e in elements for v in re.findall(r'font-size="([\d.]+)"', e)]
            if sizes and struct_class != "image_node":
                self.text_sizes[node_id] = round(max(sizes), 1)
            svg_elements.extend(group(node, self._apply_style(node, elements)))
        self.base_size = base

        svg_content = (
            f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'viewBox="0 0 {int(self.canvas_w)} {int(self.canvas_h)}" '
            f'width="{int(self.canvas_w)}" height="{int(self.canvas_h)}">\n'
            + "\n".join(svg_elements)
            + "\n</svg>"
        )
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(svg_content)
        return output_path

    def render_layout(
        self,
        json_filepath: str,
        output_dir: str = "data/rendered/",
        with_border: bool = True,
    ) -> str:
        os.makedirs(output_dir, exist_ok=True)
        if not os.path.exists(json_filepath):
            print(f"Error: Layout file not found: {json_filepath}")
            return ""
        with open(json_filepath, "r") as f:
            nodes = json.load(f)
        output_path = os.path.join(output_dir, f"{self.original_filename}_populated.svg")
        self.render_nodes(nodes, output_path, with_border=with_border)
        print(f" -> Fully Populated Rendering Complete: {output_path}")
        return output_path

    def render_with_border(self, json_filepath: str, output_dir: str = "data/rendered/") -> str:
        return self.render_layout(json_filepath, output_dir=output_dir, with_border=True)
