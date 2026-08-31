import json
import os

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _lab_centroid_to_hex(lab: list) -> str:
    """
    Converts a CIE L*a*b* centroid (OpenCV convention: L∈[0,255], a/b∈[0,255])
    to an sRGB hex colour string.  Falls back gracefully on numeric errors.
    """
    try:
        import numpy as np
        import cv2
        lab_pixel = np.array([[[float(lab[0]), float(lab[1]), float(lab[2])]]], dtype=np.float32)
        # OpenCV stores L in [0,255]; rescale to standard [0,100] before conversion
        lab_pixel[:, :, 0] *= 100.0 / 255.0
        lab_pixel[:, :, 1] -= 128.0
        lab_pixel[:, :, 2] -= 128.0
        rgb = cv2.cvtColor(lab_pixel, cv2.COLOR_Lab2RGB)
        r, g, b = (int(c * 255) for c in rgb[0, 0])
        r, g, b = max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
        return f"#{r:02X}{g:02X}{b:02X}"
    except Exception:
        return "#888888"


def _palette_from_centroids(centroids: list) -> dict:
    """
    Derives a 3-colour palette (primary, accent, background) from K-Means
    LAB centroids.  If centroids are not provided, falls back to the CSPC
    institutional palette used as the default in the original renderer.
    """
    if not centroids or len(centroids) < 3:
        return {
            "primary":    "#003366",
            "accent":     "#FFCC00",
            "background": "#FFFFFF",
        }
    return {
        "primary":    _lab_centroid_to_hex(centroids[0]),
        "accent":     _lab_centroid_to_hex(centroids[1]),
        "background": _lab_centroid_to_hex(centroids[2]),
    }


# ---------------------------------------------------------------------------
# Default mock data tables
# ---------------------------------------------------------------------------

_DEFAULT_CERT_MOCK = {
    "{{Institution_Logo}}":     "CSPC LOGO",
    "{{Issuing_Organization}}": "CAMARINES SUR POLYTECHNIC COLLEGES",
    "{{Certificate_Title}}":    "CERTIFICATE OF ACHIEVEMENT",
    "{{Presentation_Line}}":    "is proudly presented to",
    "{{Student_Name}}":         "Guiller Angelo Hermoso",
    "{{Citation_Body}}":        (
        "For outstanding academic performance and successful completion "
        "of the automated orchestration framework thesis project."
    ),
    "{{Date_Issued}}":          "August 27, 2026",
    "{{Certificate_ID}}":       "ID: CSPC-2026-001",
    "{{Signature_Blocks}}_0":   "Dean, College of Computer Studies",
    "{{Signature_Blocks}}_1":   "Thesis Adviser",
    "{{Signature_Blocks}}_2":   "College President",
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
# Main renderer class
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
        self.canvas_w = canvas_width
        self.canvas_h = canvas_height
        self.original_filename = original_filename
        self.domain = domain_context

        # 1. Derive palette — from payload centroids if provided, else defaults
        self.palette = _palette_from_centroids(color_centroids)

        self.typography = {
            "font_family": "Montserrat, sans-serif",
            "font_weight": "700",
        }

        # 2. Content mapping — prefer caller-supplied, else domain default
        if mock_data:
            self.mock_data = mock_data
        elif domain_context == "identification_card":
            self.mock_data = dict(_DEFAULT_ID_MOCK)
        else:
            self.mock_data = dict(_DEFAULT_CERT_MOCK)

    # ------------------------------------------------------------------
    # Factory constructor
    # ------------------------------------------------------------------

    @classmethod
    def from_payload(
        cls,
        payload_path: str,
        canvas_width: int = 1200,
        canvas_height: int = 900,
        original_filename: str = "master_template",
        color_centroids: list = None,
    ) -> "AestheticSVGRenderer":
        """
        Factory constructor: reads domain_context and variable_schema from the
        payload file and auto-populates mock_data with placeholder values.
        """
        with open(payload_path, "r") as f:
            payload = json.load(f)

        domain = payload.get("domain_context", "academic_certificate")
        schema = payload.get("variable_schema", {})
        defaults = _DEFAULT_ID_MOCK if domain == "identification_card" else _DEFAULT_CERT_MOCK

        generated_mock = {}
        for var_name, props in schema.items():
            count = props.get("instantiation_count", 1)
            if count > 1:
                for i in range(count):
                    key = f"{var_name}_{i}"
                    generated_mock[key] = defaults.get(
                        key, var_name.strip("{}").replace("_", " ")
                    )
            else:
                generated_mock[var_name] = defaults.get(
                    var_name, var_name.strip("{}").replace("_", " ")
                )

        return cls(
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            original_filename=original_filename,
            color_centroids=color_centroids,
            mock_data=generated_mock,
            domain_context=domain,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _clean_node_id(self, node_id: str) -> str:
        return self.mock_data.get(
            node_id,
            node_id.replace("{", "").replace("}", "").replace("_", " ").strip(),
        )

    def _is_portrait(self) -> bool:
        return self.canvas_h > self.canvas_w

    # ------------------------------------------------------------------
    # SVG element builders
    # ------------------------------------------------------------------

    def _build_background(self) -> str:
        return (
            f'<rect width="{self.canvas_w}" height="{self.canvas_h}" '
            f'fill="{self.palette["background"]}" />'
        )

    def _build_border_elements(self) -> list:
        """Renders a decorative double-rule border framing the canvas."""
        p  = self.palette["primary"]
        a  = self.palette["accent"]
        m1, m2 = 12, 20    # outer / inner margin offsets
        elements = []

        # Outer rule — primary colour
        elements.append(
            f'<rect x="{m1}" y="{m1}" width="{self.canvas_w - 2*m1}" '
            f'height="{self.canvas_h - 2*m1}" fill="none" '
            f'stroke="{p}" stroke-width="3" rx="4" />'
        )
        # Inner rule — accent colour
        elements.append(
            f'<rect x="{m2}" y="{m2}" width="{self.canvas_w - 2*m2}" '
            f'height="{self.canvas_h - 2*m2}" fill="none" '
            f'stroke="{a}" stroke-width="1.5" rx="2" />'
        )
        # Corner accent squares
        size = 8
        corners = [
            (m1, m1),
            (self.canvas_w - m1 - size, m1),
            (m1, self.canvas_h - m1 - size),
            (self.canvas_w - m1 - size, self.canvas_h - m1 - size),
        ]
        for cx, cy in corners:
            elements.append(
                f'<rect x="{cx}" y="{cy}" width="{size}" height="{size}" fill="{a}" />'
            )
        return elements

    def _build_node_element(self, node: dict) -> list:
        """Returns a list of SVG element strings for a single layout node."""
        x, y, w, h  = node["bbox"]
        node_id      = node["node_id"]
        struct_class = node.get("structural_class", "text_node")
        content      = self._clean_node_id(node_id)
        elements     = []
        p  = self.palette["primary"]
        a  = self.palette["accent"]
        ff = self.typography["font_family"]

        if struct_class == "image_node":
            # Accent-filled rectangle + centred label
            elements.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
                f'fill="{a}" rx="8" />'
            )
            elements.append(
                f'<text x="{x + w/2}" y="{y + h/2}" font-family="{ff}" '
                f'font-weight="bold" font-size="16" fill="{p}" '
                f'text-anchor="middle" dominant-baseline="middle">{content}</text>'
            )

        elif struct_class == "text_node":
            is_title  = "Title" in node_id or "Name" in node_id
            font_size = min(h * 0.8, 52) if is_title else min(h * 0.6, 36)
            font_size = max(10, min(56, font_size))   # clamp to [10, 56]
            fw        = "bold" if is_title else "normal"
            elements.append(
                f'<text x="{x + w/2}" y="{y + h/2}" font-family="{ff}" '
                f'font-weight="{fw}" font-size="{font_size:.1f}" fill="{p}" '
                f'text-anchor="middle" dominant-baseline="middle">{content}</text>'
            )

        elif struct_class == "repeating_group":
            # Signature block: horizontal rule + label beneath
            line_y = y + h * 0.6
            elements.append(
                f'<line x1="{x}" y1="{line_y}" x2="{x + w}" y2="{line_y}" '
                f'stroke="{p}" stroke-width="2" />'
            )
            elements.append(
                f'<text x="{x + w/2}" y="{line_y + 20}" font-family="{ff}" '
                f'font-size="14" fill="{p}" text-anchor="middle">{content}</text>'
            )

        return elements

    # ------------------------------------------------------------------
    # Public rendering methods
    # ------------------------------------------------------------------

    def render_layout(
        self,
        json_filepath: str,
        output_dir: str = "data/rendered/",
        with_border: bool = False,
    ) -> str:
        """
        Renders a resolved layout JSON to an SVG file.

        Parameters
        ----------
        json_filepath : str
            Path to the candidate layout JSON (list of resolved nodes).
        output_dir : str
            Destination directory for the SVG file.
        with_border : bool
            If True, adds a decorative double-rule border (certificates).
            Defaults to False (suitable for ID cards).

        Returns
        -------
        str
            Absolute path to the written SVG file, or '' on error.
        """
        os.makedirs(output_dir, exist_ok=True)

        if not os.path.exists(json_filepath):
            print(f"Error: Target layout {json_filepath} not found.")
            return ""

        with open(json_filepath, "r") as f:
            nodes = json.load(f)

        svg_elements = [self._build_background()]

        if with_border:
            svg_elements.extend(self._build_border_elements())

        for node in nodes:
            svg_elements.extend(self._build_node_element(node))

        svg_content = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {self.canvas_w} {self.canvas_h}" '
            f'width="{self.canvas_w}" height="{self.canvas_h}">\n'
            + "\n".join(svg_elements)
            + "\n</svg>"
        )

        output_path = os.path.join(output_dir, f"{self.original_filename}_populated.svg")
        with open(output_path, "w") as f:
            f.write(svg_content)

        print(f" -> Fully Populated Rendering Complete: {output_path}")
        return output_path

    def render_with_border(
        self,
        json_filepath: str,
        output_dir: str = "data/rendered/",
    ) -> str:
        """Convenience wrapper: renders with the decorative border enabled."""
        return self.render_layout(json_filepath, output_dir=output_dir, with_border=True)


# ---------------------------------------------------------------------------
# Standalone execution (backwards compatible)
# ---------------------------------------------------------------------------

def execute_rendering():
    print("Initializing Fully Populated Aesthetic Rendering Pipeline...")

    # Target the optimal, mathematically ranked output
    target_json = "data/processed/Candidate_0_GNN_Baseline.json"

    # Initialize renderer preserving the original canvas filename mapping
    renderer = AestheticSVGRenderer(original_filename="CGL_Master_Canvas")
    renderer.render_with_border(target_json)


if __name__ == "__main__":
    execute_rendering()