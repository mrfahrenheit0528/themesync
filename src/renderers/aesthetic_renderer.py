import base64
import colorsys
import hashlib
import io
import json
import os
import textwrap
from xml.sax.saxutils import escape

from PIL import Image

# ---------------------------------------------------------------------------
# Colour & Luminance helpers
# ---------------------------------------------------------------------------

def _fit_font_size(text: str, max_width: float, max_size: float,
                   letter_spacing: float = 0.0, min_size: float = 6.0) -> float:
    """Largest font size (<= max_size) whose estimated rendered width fits
    max_width. Uses ~0.62em per glyph — a conservative average for the bold
    sans stacks this renderer uses — plus the letter-spacing between glyphs."""
    n = max(len(text), 1)
    fitted = (max_width - letter_spacing * (n - 1)) / (0.62 * n)
    return max(min_size, min(max_size, fitted))


def _image_to_data_uri(path: str, max_side: int = 512) -> str:
    """Loads an image file (PNG/JPG/WebP...) and returns it as a base64 PNG
    data URI, downscaled so the SVG stays small. Returns None if unreadable."""
    try:
        with Image.open(path) as img:
            img = img.convert("RGBA")
            img.thumbnail((max_side, max_side))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
    except (OSError, ValueError) as e:
        print(f"  ⚠  Could not load logo image '{path}': {e} — using drawn badge")
        return None
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


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
            "muted":      "#5A6A80"
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

    return {
        "primary":    primary_hex,
        "accent":     accent_hex,
        "background": background_hex,
        "card_bg":    "#FFFFFF",
        "muted":      _muted_variant(primary_hex, background_is_light=lightest_l >= 128),
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
    "{{Institution_Logo}}":    "CSPC",
    "{{ID_Photo}}":            "PHOTO",
    "{{Student_Name}}":        "Guiller Angelo Hermoso",
    "{{Department_Title}}":    "Bachelor of Science in Computer Science",
    "{{Student_ID_Number}}":   "2021-00001",
    "{{Barcode_Block}}":       "||||| ||| ||||| || |||||",
}


# ---------------------------------------------------------------------------
# Main Aesthetic SVG Renderer
# ---------------------------------------------------------------------------

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
    ):
        self.canvas_w = float(canvas_width)
        self.canvas_h = float(canvas_height)
        self.original_filename = original_filename
        self.domain = domain_context
        # Real logo artwork for the logo node — either a user-uploaded file or
        # the Stage 0b crop of the master layout's detected logo (resolved in
        # pipeline.py). None falls back to the drawn seal badge.
        self.logo_data_uri = _image_to_data_uri(logo_image_path) if logo_image_path else None

        # Palette and fonts
        self.palette = _palette_from_centroids(color_centroids)
        # Table 1 (p. 49): administrative_typography (font_family) is a
        # user-injected constraint, not machine-extracted — caller (e.g. the
        # dashboard's "User Injected" panel) may override the default stack.
        self.font_family = font_family or \
            "Montserrat, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"

        # Content mapping
        if mock_data:
            self.mock_data = mock_data
        elif domain_context == "identification_card":
            self.mock_data = dict(_DEFAULT_ID_MOCK)
        else:
            self.mock_data = dict(_DEFAULT_CERT_MOCK)

    def _clean_node_id(self, node_id: str) -> str:
        return self.mock_data.get(
            node_id,
            node_id.replace("{", "").replace("}", "").replace("_", " ").strip(),
        )

    def _wrap_text_lines(self, text: str, max_chars: int) -> list:
        if "\n" in text:
            raw_lines = text.split("\n")
            lines = []
            for rl in raw_lines:
                wrapped = textwrap.wrap(rl, width=max_chars)
                lines.extend(wrapped if wrapped else [""])
            return lines
        return textwrap.wrap(text, width=max_chars) if len(text) > max_chars else [text]

    def _build_border_elements(self) -> list:
        """Renders a double border with corner rosettes and subtle inner margin."""
        p = self.palette["primary"]
        a = self.palette["accent"]
        m1, m2 = 18.0, 26.0
        
        elements = [
            f'<rect width="{self.canvas_w}" height="{self.canvas_h}" fill="{self.palette["background"]}" />',
            # Outer primary border
            f'<rect x="{m1}" y="{m1}" width="{self.canvas_w - 2*m1}" height="{self.canvas_h - 2*m1}" fill="none" stroke="{p}" stroke-width="2.5" rx="3" />',
            # Inner accent pinstripe
            f'<rect x="{m2}" y="{m2}" width="{self.canvas_w - 2*m2}" height="{self.canvas_h - 2*m2}" fill="none" stroke="{a}" stroke-width="1.2" rx="2" />',
        ]
        
        # Corner accent flourishes
        corner_sz = 10.0
        corners = [
            (m1, m1),
            (self.canvas_w - m1 - corner_sz, m1),
            (m1, self.canvas_h - m1 - corner_sz),
            (self.canvas_w - m1 - corner_sz, self.canvas_h - m1 - corner_sz),
        ]
        for cx, cy in corners:
            elements.append(f'<rect x="{cx}" y="{cy}" width="{corner_sz}" height="{corner_sz}" fill="{a}" />')
            
        return elements

    def _render_logo(self, x, y, w, h, content) -> list:
        """Places the real logo artwork, fitted inside the node's bbox without
        distortion; falls back to the drawn seal badge when none is available."""
        if not self.logo_data_uri:
            return self._render_logo_badge(x, y, w, h, content)
        return [
            f'<image x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'preserveAspectRatio="xMidYMid meet" xlink:href="{self.logo_data_uri}" />'
        ]

    def _render_logo_badge(self, x, y, w, h, content) -> list:
        """Renders an institutional seal badge with emblem geometry."""
        p = self.palette["primary"]
        a = self.palette["accent"]
        cx = x + (w / 2.0)
        cy = y + (h / 2.0)
        r = min(w, h) * 0.42
        # Keep the label inside the inner ring: shrink the font until the
        # estimated text width fits ~1.5r (was a fixed r*0.4, which let
        # longer labels like "CSPC LOGO" spill past the circle).
        font_size = _fit_font_size(content, max_width=r * 1.5, max_size=r * 0.4, letter_spacing=1.5)

        elements = [
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{self.palette["card_bg"]}" stroke="{a}" stroke-width="2.5" />',
            f'<circle cx="{cx}" cy="{cy}" r="{r - 4}" fill="none" stroke="{p}" stroke-width="1" stroke-dasharray="3,3" />',
            f'<text x="{cx}" y="{cy}" font-family="{self.font_family}" font-weight="bold" font-size="{font_size:.1f}" fill="{p}" text-anchor="middle" dominant-baseline="central" letter-spacing="1.5">{escape(content)}</text>'
        ]
        return elements

    def _render_photo_frame(self, x, y, w, h) -> list:
        """Renders a square 2x2 ID-photo slot with a neutral person silhouette
        (no real faces in generated samples)."""
        a = self.palette["accent"]
        muted = self.palette["muted"]
        side = min(w, h)
        fx = x + (w - side) / 2.0
        fy = y + (h - side) / 2.0
        cx = fx + side / 2.0
        head_r = side * 0.18
        head_cy = fy + side * 0.40
        sh_top = fy + side * 0.62
        sh_w = side * 0.34
        figure = _lighten(muted, 0.35)
        # Plain shapes only (no clipPath/<g> inheritance) so the silhouette
        # also renders in minimal SVG rasterizers, not just browsers; the
        # shoulders already sit inside the frame, so no clipping is needed.
        return [
            f'<rect x="{fx:.1f}" y="{fy:.1f}" width="{side:.1f}" height="{side:.1f}" rx="4" fill="{_lighten(muted, 0.82)}" />',
            f'<circle cx="{cx:.1f}" cy="{head_cy:.1f}" r="{head_r:.1f}" fill="{figure}" />',
            f'<path d="M {cx - sh_w:.1f} {fy + side:.1f} '
            f'Q {cx - sh_w:.1f} {sh_top:.1f} {cx:.1f} {sh_top:.1f} '
            f'Q {cx + sh_w:.1f} {sh_top:.1f} {cx + sh_w:.1f} {fy + side:.1f} Z" fill="{figure}" />',
            f'<rect x="{fx:.1f}" y="{fy:.1f}" width="{side:.1f}" height="{side:.1f}" rx="4" fill="none" stroke="{a}" stroke-width="2.5" />',
        ]

    def _render_barcode(self, x, y, w, h, content) -> list:
        """Renders a barcode strip with its human-readable value underneath,
        both inside the node's bbox. Bar widths are derived deterministically
        from the value — a visual stand-in, not a scannable symbology."""
        p = self.palette["primary"]
        bar_h = h * 0.68
        text_h = h - bar_h
        # Start/stop guards around data bars/gaps of 1-3 units, with ~2px per
        # unit so the strip reads as a real barcode at any node width.
        guard = [2, 1, 2]
        budget = max(20, int(w * 0.9 / 2.0)) - 2 * sum(guard)
        digest, seed = b"", content.encode()
        while len(digest) < budget:
            seed = hashlib.sha256(seed).digest()
            digest += seed
        data, total = [], 0
        for b in digest:
            bw = 1 + (b % 3)
            if total + bw > budget:
                break
            data.append(bw)
            total += bw
        if len(data) % 2 == 0:  # odd count so the data run starts and ends on a bar
            data.append(1)
        pattern = guard + [1] + data + [1] + guard  # [1] = separating gaps
        unit = w * 0.9 / sum(pattern)
        elements = []
        cursor = x + w * 0.05
        for i, bw in enumerate(pattern):
            if i % 2 == 0:  # even index = bar, odd = gap
                elements.append(
                    f'<rect x="{cursor:.2f}" y="{y:.1f}" width="{bw * unit:.2f}" height="{bar_h:.1f}" fill="{p}" />'
                )
            cursor += bw * unit
        font_size = _fit_font_size(content, max_width=w * 0.9, max_size=text_h * 0.75, letter_spacing=2.0)
        elements.append(
            f'<text x="{x + w / 2.0:.1f}" y="{y + bar_h + text_h * 0.8:.1f}" font-family="{self.font_family}" '
            f'font-size="{font_size:.1f}" letter-spacing="2.0" fill="{p}" text-anchor="middle">{escape(content)}</text>'
        )
        return elements

    def _render_image_node(self, x, y, w, h, node_id, content) -> list:
        """Dispatches an image node to the renderer for its role, by schema name."""
        name = node_id.lower()
        if "logo" in name:
            return self._render_logo(x, y, w, h, content)
        if "photo" in name:
            return self._render_photo_frame(x, y, w, h)
        if "barcode" in name:
            return self._render_barcode(x, y, w, h, content)
        return self._render_logo_badge(x, y, w, h, content)

    def _render_text_node(self, x, y, w, h, node_id, content) -> list:
        """Renders a text node with proportional typography and multi-line wrapping."""
        p = self.palette["primary"]
        cx = x + (w / 2.0)
        elements = []

        # Determine typography style based on hierarchy
        if "Organization" in node_id or "Issuing" in node_id:
            font_size = max(13.0, min(18.0, h * 0.4))
            font_weight = "600"
            letter_spacing = "2.0"
            lines = self._wrap_text_lines(content.upper(), max_chars=int(w / (font_size * 0.65)))
            fill = self.palette["muted"]
            font_style = "normal"
        elif "Title" in node_id and "Certificate" in node_id:
            font_size = max(24.0, min(42.0, h * 0.55))
            font_weight = "bold"
            letter_spacing = "1.0"
            lines = self._wrap_text_lines(content, max_chars=int(w / (font_size * 0.6)))
            fill = p
            font_style = "normal"
        elif "Presentation" in node_id:
            font_size = max(13.0, min(16.0, h * 0.35))
            font_weight = "normal"
            letter_spacing = "0.5"
            lines = self._wrap_text_lines(content, max_chars=int(w / (font_size * 0.6)))
            fill = self.palette["muted"]
            font_style = "italic"
        elif "Student_Name" in node_id or "Name" in node_id:
            font_size = max(22.0, min(36.0, h * 0.5))
            font_weight = "bold"
            letter_spacing = "0.8"
            lines = self._wrap_text_lines(content, max_chars=int(w / (font_size * 0.65)))
            fill = p
            font_style = "normal"
        elif "Citation" in node_id:
            font_size = max(12.0, min(15.0, h * 0.3))
            font_weight = "normal"
            letter_spacing = "0.2"
            max_c = max(35, int(w / (font_size * 0.55)))
            lines = self._wrap_text_lines(content, max_chars=max_c)
            fill = "#334155"
            font_style = "normal"
        else: # Date, ID, etc.
            font_size = max(11.0, min(14.0, h * 0.35))
            font_weight = "normal"
            letter_spacing = "0.5"
            lines = self._wrap_text_lines(content, max_chars=int(w / (font_size * 0.6)))
            fill = self.palette["muted"]
            font_style = "normal"

        line_height = font_size * 1.35
        total_block_h = len(lines) * line_height
        start_y = y + (h - total_block_h) / 2.0 + (font_size * 0.85)

        for idx, line in enumerate(lines):
            line_y = start_y + (idx * line_height)
            elements.append(
                f'<text x="{cx}" y="{line_y:.1f}" font-family="{self.font_family}" '
                f'font-size="{font_size:.1f}" font-weight="{font_weight}" '
                f'font-style="{font_style}" letter-spacing="{letter_spacing}" '
                f'fill="{fill}" text-anchor="middle">{line}</text>'
            )

        return elements

    def _render_signature_block(self, x, y, w, h, content) -> list:
        """Renders an elegant signature line with signatory name and title on separate lines."""
        p = self.palette["primary"]
        cx = x + (w / 2.0)
        line_y = y + (h * 0.45)
        elements = []

        # Horizontal signature rule
        elements.append(
            f'<line x1="{x + 10}" y1="{line_y:.1f}" x2="{x + w - 10}" y2="{line_y:.1f}" '
            f'stroke="{p}" stroke-width="1.2" opacity="0.85" />'
        )

        parts = content.split("\n")
        name = parts[0].strip() if len(parts) > 0 else content
        title = parts[1].strip() if len(parts) > 1 else ""

        # Signatory Name (Bold)
        elements.append(
            f'<text x="{cx}" y="{line_y + 18:.1f}" font-family="{self.font_family}" '
            f'font-size="13" font-weight="bold" fill="{p}" text-anchor="middle">{name}</text>'
        )

        # Signatory Title (Regular)
        if title:
            elements.append(
                f'<text x="{cx}" y="{line_y + 32:.1f}" font-family="{self.font_family}" '
                f'font-size="11.5" font-weight="normal" fill="{self.palette["muted"]}" text-anchor="middle">{title}</text>'
            )

        return elements

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

        svg_elements = []

        if with_border:
            svg_elements.extend(self._build_border_elements())
        else:
            svg_elements.append(f'<rect width="{self.canvas_w}" height="{self.canvas_h}" fill="{self.palette["background"]}" />')

        # Render each semantic node
        for node in nodes:
            x, y, w, h = node['bbox']
            node_id = node['node_id']
            struct_class = node.get('structural_class', 'text_node')
            content = self._clean_node_id(node_id)

            if struct_class == "image_node":
                svg_elements.extend(self._render_image_node(x, y, w, h, node_id, content))
            elif struct_class == "repeating_group":
                svg_elements.extend(self._render_signature_block(x, y, w, h, content))
            else:
                svg_elements.extend(self._render_text_node(x, y, w, h, node_id, content))

        svg_content = (
            f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'viewBox="0 0 {int(self.canvas_w)} {int(self.canvas_h)}" '
            f'width="{int(self.canvas_w)}" height="{int(self.canvas_h)}">\n'
            + "\n".join(svg_elements)
            + "\n</svg>"
        )

        output_path = os.path.join(output_dir, f"{self.original_filename}_populated.svg")
        with open(output_path, "w") as f:
            f.write(svg_content)

        print(f" -> Fully Populated Rendering Complete: {output_path}")
        return output_path

    def render_with_border(self, json_filepath: str, output_dir: str = "data/rendered/") -> str:
        return self.render_layout(json_filepath, output_dir=output_dir, with_border=True)