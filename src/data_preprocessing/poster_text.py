"""
ThemeSync — text from the master layout for the content payload (notes §3.55)
==============================================================================
Reads the words on a master poster so Step 1 can suggest them for the
target's content fields.

  1. ocr_lines: each text box Stage 0b detected is cropped, cleaned for OCR
     (grayscale, light text on dark turned dark on light, small crops
     enlarged) and read by Tesseract line by line. Lines that are mostly
     symbols (stylised title artwork reads as noise) are dropped.
  2. suggest_fields: a field is filled only when a line clearly fits it:
       the organisation header  lines naming an institution (College,
                                University, Council...) in the top half;
       the event details        a line with a date, with a venue line
                                (Auditorium, Gymnasium, Zoom...) next to it;
       the certificate's date   the date alone.
     Titles are left out: stylised title artwork doesn't read reliably.

On the 16 Phase 4 posters, Tesseract read the role boxes the structure
mapping uses (header, title, details) at 0.21-0.32 similarity to the text
typed from the posters, so suggestions come from these rules instead, and
the designer checks them: every suggested field is marked, and every line
read is listed to pick from.

Tesseract's English model ships in assets/tessdata (the Windows install had
none, so OCR had returned nothing there; layout_extractor uses it too).
"""

import os
import re

import numpy as np
from PIL import Image, ImageOps

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TESSDATA = os.path.join(_ROOT, "assets", "tessdata")
if os.path.exists(os.path.join(TESSDATA, "eng.traineddata")):
    os.environ["TESSDATA_PREFIX"] = TESSDATA

import pytesseract  # noqa: E402

MONTHS = ("january|february|march|april|may|june|july|august|september|october|november|december|"
          "jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec")
DATE = re.compile(rf"\b(?:(?:{MONTHS})\.?\s+\d{{1,2}}(?:\s*[-–]\s*\d{{1,2}})?(?:,?\s*\d{{4}})?"
                  rf"|\d{{1,2}}\s+(?:{MONTHS})\.?(?:\s+\d{{4}})?"
                  rf"|\d{{1,2}}[./-]\d{{1,2}}[./-]\d{{2,4}})\b", re.IGNORECASE)
INSTITUTION = re.compile(r"\b(college|colleges|university|council|school|institute|society|department|office|"
                         r"academy|center|centre|inc|organization|organisation|club|association|federation)\b",
                         re.IGNORECASE)
VENUE = re.compile(r"\b(auditorium|gym|gymnasium|hall|quadrangle|grounds?|forum|zoom|room|court|field|stadium|"
                   r"campus|plaza|theater|theatre|chapel|library|lobby|covered court|via|online|google meet)\b",
                   re.IGNORECASE)


SHORT_WORDS = {"of", "and", "the", "in", "on", "at", "for", "to", "a", "an", "&", "by", "inc", "inc.", "st", "st.",
               "dr", "dr.", "sr", "sr.", "jr", "jr.", "fm", "am", "pm", "ph"}


def _clean(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip(" |_-—~•·*'\"`\\/")


def _wordlike(token: str) -> bool:
    raw = token.strip(",.:;()!?'\"")
    if re.fullmatch(r"[A-Z]{2,6}", raw):          # an acronym: CSPC, CTC, USANT
        return True
    t = raw.lower()
    return (len(t) >= 3 and t.isalpha() and re.search(r"[aeiouy]", t) is not None) or t in SHORT_WORDS \
        or bool(re.fullmatch(r"[\d.,:/-]+(st|nd|rd|th|am|pm)?", t)) or bool(re.fullmatch(r"[a-z]+['’]s", t))


def _readable(line: str) -> bool:
    """Mostly ordinary characters, and at least three in four tokens real
    words, numbers or dates (stylised artwork reads as short fragments)."""
    if len(line) < 3:
        return False
    if sum(c.isalnum() or c in " ,.:;-–&'’()/#@!?" for c in line) / len(line) < 0.85:
        return False
    tokens = line.split()
    return sum(_wordlike(t) for t in tokens) >= 0.75 * len(tokens) or bool(DATE.search(line))


def prepare_for_ocr(crop: Image.Image) -> Image.Image:
    g = ImageOps.grayscale(crop)
    if np.asarray(g).mean() < 128:                 # light text on a dark ground
        g = ImageOps.invert(g)
    if g.height < 120:
        g = g.resize((g.width * 2, g.height * 2), Image.LANCZOS)
    return g


def ocr_lines(image_path: str, detected_nodes: list) -> list:
    """[{"text", "bbox", "cy"}] of every readable line in the poster's
    detected text boxes, top to bottom (cy: the box's centre, a fraction of
    the height). Stage 0b's OCR text is used when it has some; otherwise
    each box is read here."""
    img = Image.open(image_path)
    W, H = img.size
    reuse = any(n.get("ocr_text") for n in detected_nodes)
    if not reuse:
        img = img.convert("RGB")
    out, seen = [], set()
    boxes = sorted((n for n in detected_nodes if n.get("structural_class") == "text_node"),
                   key=lambda n: (n["bbox"][1], n["bbox"][0]))
    for n in boxes:
        x, y, w, h = n["bbox"]
        if w * h > 0.25 * W * H:                   # a box over the whole artwork, not a text line
            continue
        if reuse:
            text = n.get("ocr_text") or ""
        else:
            pad = max(4, int(0.08 * h))
            crop = img.crop((max(0, x - pad), max(0, y - pad), min(W, x + w + pad), min(H, y + h + pad)))
            try:
                text = pytesseract.image_to_string(prepare_for_ocr(crop), config="--psm 6")
            except pytesseract.TesseractError:
                return out
        for line in text.splitlines():
            line = _clean(line)
            key = line.lower()
            if _readable(line) and key not in seen:
                seen.add(key)
                out.append({"text": line, "bbox": [x, y, w, h], "cy": (y + h / 2.0) / H})
    return out


def _title_case(text: str) -> str:
    """ALL-CAPS poster text in title case; mixed case stays as written."""
    if text.upper() != text:
        return text
    small = {"of", "and", "the", "in", "on", "at", "for", "to", "a", "an", "&"}

    def word(i, w):
        if re.fullmatch(r"[A-Z]{2,6}", w) and not re.search(r"[AEIOU]", w):
            return w                                # an acronym: CTC, CSPC, DZCC
        w = w.lower()
        return w if i and w in small else w[:1].upper() + w[1:]

    return " ".join(word(i, w) for i, w in enumerate(text.split()))


def suggest_fields(lines: list, domain: str, limits: dict) -> dict:
    """{content key: text} for the fields a line clearly fits; `limits` maps
    content keys to max_characters (a suggestion over it is dropped)."""
    out = {}
    top = [l for l in lines if l["cy"] < 0.5]
    header = [l["text"] for l in top if INSTITUTION.search(l["text"]) and not DATE.search(l["text"])
              and len(l["text"].split()) >= 2][:2]
    dated = next((i for i, l in enumerate(lines) if DATE.search(l["text"])), None)
    details = None
    date_only = None
    if dated is not None:
        line = lines[dated]["text"]
        date_only = DATE.search(line).group(0)
        venue = next((l["text"] for l in lines[max(0, dated - 1):dated + 3]
                      if l is not lines[dated] and VENUE.search(l["text"])), None)
        if venue and VENUE.search(line) is None:
            details = f"{_title_case(date_only)} · {_title_case(venue)}"
        else:
            details = _title_case(line)

    def put(key_part: str, value: str):
        key = next((k for k in limits if key_part in k), None)
        if key and value and len(value) <= (limits.get(key) or 10 ** 6):
            out[key] = value

    if domain == "identification_card":
        put("Organization_Header", "\n".join(_title_case(h) for h in header))
        put("Event_Details", details)
    else:
        put("Issuing_Organization", _title_case(header[0]) if header else None)
        put("Date_Issued", _title_case(date_only) if date_only else None)
    return out
