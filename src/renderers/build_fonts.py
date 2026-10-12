"""
Builds the font families the dashboard offers besides Montserrat, into
assets/fonts/<family>/ (notes §3.53).

Every family comes from Google Fonts' own repository
(github.com/google/fonts, SIL Open Font License; each folder keeps its
OFL.txt). Families published only as variable fonts are cut into static
faces with fontTools' instancer, because Cairo's text API picks a face by
family, weight and slant. Every face is subset to Latin script (Basic Latin
to Latin Extended-B, Latin Extended Additional, punctuation and currency),
which keeps the repo small and still covers names such as "Peña" or
"Nguyễn".

The output is committed, so neither the server nor the Windows checkout
needs internet access; re-run this only to change the families:

    python src/renderers/build_fonts.py
"""
import io
import os
import urllib.request

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONT_DIR = os.path.join(ROOT, "assets", "fonts")
BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl"

UNICODES = ("U+0020-024F,U+0300-036F,U+1E00-1EFF,U+2000-206F,U+20A0-20CF,U+2100-214F,"
            "U+2190-21FF,U+2212,U+2215,U+25CF,U+FB01-FB02")

# The styles a face is cut at: name → (weight, italic). The renderer asks
# for the user's heading weight (100-900), 400, 700 and 900, and italic 400.
STYLES = {"Regular": (400, False), "Italic": (400, True), "SemiBold": (600, False), "Bold": (700, False),
          "BoldItalic": (700, True), "ExtraBold": (800, False), "Black": (900, False)}

# folder → (family, repository folder, source files). A static source is
# {style: file}; a variable one is (roman file, italic file, other axes).
FAMILIES = {
    "lato": ("Lato", "lato", {s: f"Lato-{s}.ttf" for s in STYLES}),
    "tinos": ("Tinos", "tinos", {s: f"Tinos-{s}.ttf" for s in ("Regular", "Italic", "Bold", "BoldItalic")}),
    "opensans": ("Open Sans", "opensans",
                 ("OpenSans[wdth,wght].ttf", "OpenSans-Italic[wdth,wght].ttf", {"wdth": 100})),
    "playfairdisplay": ("Playfair Display", "playfairdisplay",
                        ("PlayfairDisplay[wght].ttf", "PlayfairDisplay-Italic[wght].ttf", {})),
    "merriweather": ("Merriweather", "merriweather",
                     ("Merriweather[opsz,wdth,wght].ttf", "Merriweather-Italic[opsz,wdth,wght].ttf",
                      {"opsz": 18, "wdth": 100})),
}


def _fetch(repo_dir: str, name: str) -> bytes:
    url = f"{BASE}/{repo_dir}/{urllib.request.quote(name)}"
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def _subset(font: TTFont) -> TTFont:
    options = subset.Options()
    # The features running text needs (kerning, ligatures, accents), not
    # the alternates (small caps, old-style figures...) that bloat a subset.
    options.layout_features = ["kern", "liga", "clig", "calt", "ccmp", "locl", "mark", "mkmk", "rlig"]
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    options.notdef_outline = True
    options.hinting = False
    options.glyph_names = False
    sub = subset.Subsetter(options)
    sub.populate(unicodes=subset.parse_unicodes(UNICODES))
    sub.subset(font)
    return font


def _name_static(font: TTFont, family: str, style: str, weight: int, italic: bool) -> None:
    """Names a cut face the way static Google Fonts name theirs: the four
    basic styles share the family; the others are their own legacy family
    ("Open Sans SemiBold") inside the typographic family ("Open Sans")."""
    ribbi = style in ("Regular", "Italic", "Bold", "BoldItalic")
    legacy_style = {"Regular": "Regular", "Italic": "Italic", "Bold": "Bold", "BoldItalic": "Bold Italic"}
    name = font["name"]
    for nid in (16, 17, 21, 22, 25):
        name.removeNames(nameID=nid)
    full = f"{family} {style}" if style != "Regular" else f"{family} Regular"
    legacy_family = family if ribbi else f"{family} {style}"
    name.setName(legacy_family, 1, 3, 1, 0x409)
    name.setName(legacy_style[style] if ribbi else "Regular", 2, 3, 1, 0x409)
    name.setName(full, 4, 3, 1, 0x409)
    name.setName(f"{family.replace(' ', '')}-{style}", 6, 3, 1, 0x409)
    name.setName(f"{family};{style}", 3, 3, 1, 0x409)
    if not ribbi:
        name.setName(family, 16, 3, 1, 0x409)
        name.setName(style, 17, 3, 1, 0x409)
    name.names = [n for n in name.names if n.platformID == 3]      # one platform, no stale Mac names
    os2 = font["OS/2"]
    os2.usWeightClass = weight
    sel = os2.fsSelection & ~0b1100001                             # clear ITALIC, BOLD, REGULAR
    sel |= (0b1 if italic else 0) | (0b100000 if style in ("Bold", "BoldItalic") else 0)
    if style == "Regular":
        sel |= 0b1000000
    os2.fsSelection = sel
    font["head"].macStyle = (1 if style in ("Bold", "BoldItalic") else 0) | (2 if italic else 0)
    if "STAT" in font:
        del font["STAT"]


def build() -> None:
    for folder, (family, repo_dir, source) in FAMILIES.items():
        out_dir = os.path.join(FONT_DIR, folder)
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "OFL.txt"), "wb") as f:
            try:
                f.write(_fetch(repo_dir, "OFL.txt"))
            except OSError:
                # Tinos's folder has no OFL.txt; its METADATA.pb gives the
                # licence as "OFL", so the OFL 1.1 text goes with a header.
                text = _fetch("lato", "OFL.txt")
                body = text[text.index(b"This Font Software is licensed"):]
                f.write(f"{family} (designer: Steve Matteson), from github.com/google/fonts/tree/main/ofl/"
                        f"{repo_dir}; METADATA.pb: license \"OFL\".\n\n".encode() + body)
        if isinstance(source, dict):                                   # static faces
            for style, file in source.items():
                font = _subset(TTFont(io.BytesIO(_fetch(repo_dir, file))))
                font.save(os.path.join(out_dir, f"{family.replace(' ', '')}-{style}.ttf"))
                print(f"  {family} {style}")
            continue
        roman_file, italic_file, axes = source
        roman = _fetch(repo_dir, roman_file)
        italic = _fetch(repo_dir, italic_file)
        for style, (weight, is_italic) in STYLES.items():
            vf = TTFont(io.BytesIO(italic if is_italic else roman))
            lo, hi = next((a.minValue, a.maxValue) for a in vf["fvar"].axes if a.axisTag == "wght")
            if not lo <= weight <= hi or (is_italic and style not in ("Italic", "BoldItalic")):
                continue
            location = {**axes, "wght": weight}
            font = instancer.instantiateVariableFont(vf, location)
            _name_static(font, family, style, weight, is_italic)
            _subset(font).save(os.path.join(out_dir, f"{family.replace(' ', '')}-{style}.ttf"))
            print(f"  {family} {style}")


if __name__ == "__main__":
    build()
