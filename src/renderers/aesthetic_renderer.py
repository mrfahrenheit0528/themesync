import json
import os
import textwrap

# ---------------------------------------------------------------------------
# Colour & Luminance helpers
# ---------------------------------------------------------------------------

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


def _palette_from_centroids(centroids: list) -> dict:
    """
    Derives a high-contrast 3-colour palette (primary, accent, background).
    Ensures background is clean and text has strong visual contrast.
    """
    if not centroids or len(centroids) < 3:
        return {
            "primary":    "#003366",   # Deep Navy
            "accent":     "#D4AF37",   # Metallic Gold
            "background": "#FDFFFF",   # Crisp Ivory White
            "card_bg":    "#FFFFFF",
            "muted":      "#5A6A80"
        }
        
    c1 = _lab_centroid_to_hex(centroids[0])
    c2 = _lab_centroid_to_hex(centroids[1])
    c3 = _lab_centroid_to_hex(centroids[2])
    
    return {
        "primary":    c1,
        "accent":     c2,
        "background": "#FCFDFE",
        "card_bg":    "#FFFFFF",
        "muted":      "#64748B"
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
    ):
        self.canvas_w = float(canvas_width)
        self.canvas_h = float(canvas_height)
        self.original_filename = original_filename
        self.domain = domain_context

        # Palette and fonts
        self.palette = _palette_from_centroids(color_centroids)
        self.font_family = "Montserrat, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"

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

    def _render_logo_badge(self, x, y, w, h, content) -> list:
        """Renders an institutional seal badge with emblem geometry."""
        p = self.palette["primary"]
        a = self.palette["accent"]
        cx = x + (w / 2.0)
        cy = y + (h / 2.0)
        r = min(w, h) * 0.42
        
        elements = [
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{self.palette["card_bg"]}" stroke="{a}" stroke-width="2.5" />',
            f'<circle cx="{cx}" cy="{cy}" r="{r - 4}" fill="none" stroke="{p}" stroke-width="1" stroke-dasharray="3,3" />',
            f'<text x="{cx}" y="{cy}" font-family="{self.font_family}" font-weight="bold" font-size="{r*0.4:.1f}" fill="{p}" text-anchor="middle" dominant-baseline="central" letter-spacing="1.5">{content}</text>'
        ]
        return elements

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
                svg_elements.extend(self._render_logo_badge(x, y, w, h, content))
            elif struct_class == "repeating_group":
                svg_elements.extend(self._render_signature_block(x, y, w, h, content))
            else:
                svg_elements.extend(self._render_text_node(x, y, w, h, node_id, content))

        svg_content = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
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