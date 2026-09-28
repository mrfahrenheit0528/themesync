"""
ThemeSync — SVG Rasterization with Bundled Fonts
=================================================
Turns rendered SVG layouts into PNG/PDF (e.g. for the Phase 4 expert
packet) using Cairo, with the project's own fonts from assets/fonts/.

Why this exists: the renderer's default typeface (Montserrat) isn't
installed on the school HPC server, and installing system fonts there may
not be allowed. Instead the fonts ship inside the repo (SIL Open Font
License, see assets/fonts/montserrat/OFL.txt) and are exposed to *this
process only*, by pointing fontconfig at a generated config file that adds
assets/fonts/ on top of the normal system configuration. Nothing is
installed; no admin rights are needed.

The config is generated at import time with an absolute path because
fontconfig 2.13 (the server's version) ignores relative <dir> entries.
It must be in place before Cairo first touches a font, so import this
module before anything else that renders text through Cairo.

Note: CairoSVG selects fonts through Cairo's basic API, which only
distinguishes normal and bold — SVG weights 600-900 all render with the
Bold face.

Usage:
  from rasterize import svg_to_png, svg_to_pdf
  svg_to_png("data/rendered/ThemeSync_identification-card_populated.svg")
"""

import hashlib
import os
import tempfile
from xml.sax.saxutils import escape

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONT_DIR = os.path.join(_ROOT, "assets", "fonts")


def _project_fontconfig() -> str:
    """Writes (once per project path) a fontconfig file that includes the
    existing configuration plus FONT_DIR, and returns its path."""
    base = os.environ.get("FONTCONFIG_FILE", "/etc/fonts/fonts.conf")
    conf = (
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE fontconfig SYSTEM "fonts.dtd">\n'
        "<fontconfig>\n"
        f'  <include ignore_missing="yes">{escape(base)}</include>\n'
        f"  <dir>{escape(FONT_DIR)}</dir>\n"
        '  <cachedir prefix="xdg">fontconfig</cachedir>\n'
        "</fontconfig>\n"
    )
    key = hashlib.sha1(conf.encode()).hexdigest()[:12]
    path = os.path.join(tempfile.gettempdir(), f"themesync_fonts_{key}.conf")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(conf)
    return path


if os.path.isdir(FONT_DIR) and "themesync_fonts_" not in os.environ.get("FONTCONFIG_FILE", ""):
    os.environ["FONTCONFIG_FILE"] = _project_fontconfig()

import cairosvg  # noqa: E402 — must come after FONTCONFIG_FILE is set


def svg_to_png(svg_path: str, png_path: str = None, scale: float = 1.0) -> str:
    """Rasterizes an SVG to PNG (same stem by default); returns the PNG path."""
    png_path = png_path or os.path.splitext(svg_path)[0] + ".png"
    cairosvg.svg2png(url=svg_path, write_to=png_path, scale=scale)
    return png_path


def svg_to_pdf(svg_path: str, pdf_path: str = None) -> str:
    """Converts an SVG to a vector PDF (same stem by default); returns the path."""
    pdf_path = pdf_path or os.path.splitext(svg_path)[0] + ".pdf"
    cairosvg.svg2pdf(url=svg_path, write_to=pdf_path)
    return pdf_path
