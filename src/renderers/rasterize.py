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
installed; no admin rights are needed. On Windows, where Cairo doesn't
use fontconfig, the families Windows lacks are registered for the session
instead (`_register_windows_fonts`).

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
import time
from concurrent.futures import ThreadPoolExecutor
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


def _register_windows_fonts() -> list:
    """Windows: Cairo 1.18 finds fonts through DirectWrite, which reads only
    the fonts Windows knows about, not fontconfig's directories. Each bundled
    family that isn't installed is added for the signed-in session with
    AddFontResourceExW (not FR_PRIVATE: DirectWrite ignores private fonts).
    Nothing is copied or written to the registry, no admin rights are
    needed, and it lasts until sign-out. An installed family, such as a
    Montserrat installed by the user, is left alone so its rendering doesn't
    change. Must run before Cairo first draws text. Returns the families
    added (notes §3.53)."""
    import ctypes
    import winreg

    installed = []
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts") as key:
                for i in range(winreg.QueryInfoKey(key)[1]):
                    installed.append(winreg.EnumValue(key, i)[0].replace(" ", "").lower())
        except OSError:
            pass
    gdi = ctypes.WinDLL("gdi32")
    added = []
    for folder in sorted(os.listdir(FONT_DIR)):
        path = os.path.join(FONT_DIR, folder)
        if not os.path.isdir(path) or any(name.startswith(folder.lower()) for name in installed):
            continue
        faces = [f for f in sorted(os.listdir(path)) if f.lower().endswith(".ttf")]
        if sum(gdi.AddFontResourceExW(os.path.join(path, f), 0, 0) for f in faces):
            added.append(folder)
    return added


WINDOWS_FONTS = _register_windows_fonts() if os.name == "nt" and os.path.isdir(FONT_DIR) else []
# DirectWrite takes in newly added fonts a moment later, and Cairo keeps the
# font list it first reads; rendering at once drew plain Tinos with its
# italic face. So the first render waits until this time (seconds after
# start-up, so the dashboard never notices).
_FONTS_READY_AT = time.monotonic() + 2.0 if WINDOWS_FONTS else 0.0

import cairosvg  # noqa: E402 — must come after FONTCONFIG_FILE is set

# Every Cairo call runs on this one long-lived thread. On Windows, the Cairo
# DLL that Tesseract ships segfaults when a second thread renders after the
# first, and Streamlit runs each rerun of a page on a new thread, so the
# dashboard crashed on its second render (notes §3.36). One worker thread
# also keeps concurrent dashboard sessions from rendering at the same time.
# The output is unchanged; only the calling thread differs.
_CAIRO = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cairo")


def on_cairo_thread(fn, *args, **kwargs):
    """Runs a cairosvg call on the Cairo thread and returns its result."""
    wait = _FONTS_READY_AT - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    return _CAIRO.submit(fn, *args, **kwargs).result()


def svg_to_png(svg_path: str, png_path: str = None, scale: float = 1.0) -> str:
    """Rasterizes an SVG to PNG (same stem by default); returns the PNG path."""
    png_path = png_path or os.path.splitext(svg_path)[0] + ".png"
    on_cairo_thread(cairosvg.svg2png, url=svg_path, write_to=png_path, scale=scale)
    return png_path


def svg_to_pdf(svg_path: str, pdf_path: str = None) -> str:
    """Converts an SVG to a vector PDF (same stem by default); returns the path."""
    pdf_path = pdf_path or os.path.splitext(svg_path)[0] + ".pdf"
    on_cairo_thread(cairosvg.svg2pdf, url=svg_path, write_to=pdf_path)
    return pdf_path
