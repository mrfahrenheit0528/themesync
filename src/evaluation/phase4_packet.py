"""
ThemeSync — Phase 4 Rating Packet Generator
============================================
Builds the printed packet the domain expert(s) use to rate ThemeSync's
outputs with the MOS instrument (Chapter 3, pp. 54, 57-58).

Design (agreed with the group, notes §3.20):
  - 15 unseen master layouts (event posters) x 2 formats (certificate,
    event ID) x 2 conditions (GNN-guided, no-GNN baseline) = 60 layouts.
  - Blind: every page shows only a random sample code (e.g. S23). Both
    conditions of a poster get identical content, so only the layout
    differs; pages from the same poster are never adjacent. The answer
    key (phase4_key.csv) stays with the group and is never printed.
  - Each page shows the master layout next to the generated layout (p.54:
    the expert compares outputs "against the original Master Layout"),
    with the three MOS parameters and Table 2's 1-5 scale to circle.
  - One packet per expert: same sample codes, own randomized page order.

Steps:
  # 1. List the collected posters; writes manifest.csv for the group to fill in
  python src/evaluation/phase4_packet.py template

  # 2. Generate every layout (runs the full pipeline 4x per poster)
  python src/evaluation/phase4_packet.py generate --n_posters 15

  # 3. One printable PDF + score-entry CSV per expert
  python src/evaluation/phase4_packet.py packet --expert "Evaluator A" --order_seed 1

  # 4. After rating: type the circled scores into the expert's CSV, then
  python src/evaluation/mos_collector.py --import_scores <csv> --key data/phase4/phase4_key.csv --evaluator "Evaluator A"
"""

import argparse
import base64
import contextlib
import csv
import io
import json
import os
import random
import re
import subprocess
import sys
import textwrap
from xml.sax.saxutils import escape

_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_EVAL_DIR)
_ROOT = os.path.dirname(_SRC)
for _sub in ("renderers", "models", "solvers", "data_preprocessing"):
    _p = os.path.join(_SRC, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import rasterize  # noqa: E402 — first, so Cairo picks up the bundled fonts
from PIL import Image  # noqa: E402

import poster_overlap  # noqa: E402
from mos_collector import DIMENSIONS, RATING_SCALE  # noqa: E402

POSTERS_DIR = os.path.join(_ROOT, "data", "raw", "phase4_posters")
OUT_DIR = os.path.join(_ROOT, "data", "phase4")
KEY_PATH = os.path.join(OUT_DIR, "phase4_key.csv")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")

MANIFEST_FIELDS = ["poster_file", "event_title", "event_date", "event_venue",
                   "organization_header", "logo_files"]

FORMATS = {
    "certificate": os.path.join(_ROOT, "data", "raw", "academic_payload.json"),
    "event_id":    os.path.join(_ROOT, "data", "raw", "id_payload.json"),
}
CONDITIONS = ("gnn", "baseline")

# Sample content only — fictional people, so no real student is named.
NAMES = ["Maria Angela Santos", "Juan Miguel Reyes", "Kristine Joy Bautista",
         "Mark Anthony Villanueva", "Patricia Mae Dela Cruz", "John Paul Mendoza",
         "Angelica Rose Navarro", "Christian Lloyd Ramos", "Bea Nicole Aquino",
         "Carlo Jose Fernandez", "Janelle Marie Castillo", "Paolo Gabriel Torres",
         "Andrea Faith Gonzales", "Kevin Rafael Morales", "Samantha Lei Pascual"]
ROLES = ["Organizer", "Participant", "Delegate", "Facilitator", "Volunteer"]

# Page geometry: A4 landscape, 96 px per inch.
PAGE_W, PAGE_H = 1123, 794
FONT = "Montserrat, 'DejaVu Sans', sans-serif"
INK, MUTED, RULE = "#1d1d1f", "#5f5f66", "#c9c9cf"


# ---------------------------------------------------------------------------
# Unseen-poster check
# ---------------------------------------------------------------------------

def _seen_matches(poster_paths: list) -> dict:
    """Maps each poster to the annotated image it (near-)duplicates, if any."""
    annotated = poster_overlap.annotated_images()
    matches = {}
    for poster in poster_paths:
        match = poster_overlap.find_match(poster, annotated)
        if match:
            matches[poster] = match
    return matches


# ---------------------------------------------------------------------------
# Step 1: manifest template
# ---------------------------------------------------------------------------

def _poster_files(posters_dir: str) -> list:
    return sorted(f for f in os.listdir(posters_dir) if f.lower().endswith(IMAGE_EXTS))


def _read_manifest(posters_dir: str) -> list:
    path = os.path.join(posters_dir, "manifest.csv")
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def cmd_template(args) -> None:
    os.makedirs(args.posters_dir, exist_ok=True)
    files = _poster_files(args.posters_dir)
    rows = {r["poster_file"]: r for r in _read_manifest(args.posters_dir)}
    for f in files:
        rows.setdefault(f, {k: "" for k in MANIFEST_FIELDS} | {"poster_file": f})
    path = os.path.join(args.posters_dir, "manifest.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for f in sorted(rows):
            writer.writerow({k: rows[f].get(k, "") for k in MANIFEST_FIELDS})

    print(f"  {len(files)} poster(s) in {args.posters_dir}")
    print(f"  Manifest → {path}")
    print("  Fill in per poster: event_title (required), event_date, event_venue,")
    print("  organization_header (use ' | ' between lines), logo_files (optional,")
    print("  ';'-separated paths, only to override the logos detected on the poster).")
    seen = _seen_matches([os.path.join(args.posters_dir, f) for f in files])
    for poster, match in seen.items():
        print(f"  ⚠  {os.path.basename(poster)} looks like annotated image {match} — "
              "not unseen; replace it.")


# ---------------------------------------------------------------------------
# Step 2: generate layouts
# ---------------------------------------------------------------------------

def _content_for(row: dict, i: int) -> dict:
    """Per-poster sample content, identical for both conditions."""
    title = row["event_title"].strip()
    date, venue = row.get("event_date", "").strip(), row.get("event_venue", "").strip()
    org_lines = [s.strip() for s in row.get("organization_header", "").split("|") if s.strip()]
    org = org_lines or ["Camarines Sur Polytechnic Colleges"]
    name, role = NAMES[i % len(NAMES)], ROLES[i % len(ROLES)]
    year = (re.findall(r"(20\d\d)", date + " " + title) or ["2026"])[-1]
    with open(os.path.join(_ROOT, "data", "raw", "sample_content.json")) as f:
        signatories = {k: v for k, v in json.load(f).items() if k.startswith("{{Signature_Blocks}}")}

    citation = f"For active participation as {role.lower()} in {title}"
    citation += (f", held on {date}" if date else "") + (f" at {venue}" if venue else "") + "."
    certificate = {
        "{{Institution_Logo}}":     org[0],
        "{{Issuing_Organization}}": org[0],
        "{{Certificate_Title}}":    "Certificate of Participation",
        "{{Presentation_Line}}":    "is proudly presented to",
        "{{Student_Name}}":         name,
        "{{Citation_Body}}":        citation,
        "{{Date_Issued}}":          date,
        "{{Certificate_ID}}":       f"CSPC-{year}-{i + 1:03d}",
        **signatories,
    }
    event_id = {
        "{{Organization_Logos}}":  org[0],
        "{{Organization_Header}}": "\n".join(org[:2]),
        "{{Event_Title}}":         title,
        "{{Event_Details}}":       " · ".join(p for p in (date, venue) if p),
        "{{Participant_Name}}":    name.split()[0],
        "{{Participant_Role}}":    role,
    }
    return {"certificate": certificate, "event_id": event_id}


def cmd_generate(args) -> None:
    import pipeline  # heavy (torch, YOLO); only needed here

    rows = [r for r in _read_manifest(args.posters_dir) if r.get("poster_file")]
    if not rows:
        sys.exit(f"No manifest rows in {args.posters_dir}/manifest.csv — run `template` first.")
    missing = [r["poster_file"] for r in rows if not r.get("event_title", "").strip()]
    if missing:
        sys.exit(f"event_title is empty for: {', '.join(missing)}")
    posters = {r["poster_file"]: os.path.join(args.posters_dir, r["poster_file"]) for r in rows}
    absent = [f for f, p in posters.items() if not os.path.exists(p)]
    if absent:
        sys.exit(f"Poster file(s) not found: {', '.join(absent)}")

    seen = _seen_matches(list(posters.values()))
    if seen and not args.allow_seen:
        for poster, match in seen.items():
            print(f"  ✘  {os.path.basename(poster)} matches annotated image {match}")
        sys.exit("Phase 4 needs unseen posters. Replace these, or pass --allow_seen for a dry run.")

    rows = sorted(rows, key=lambda r: r["poster_file"])
    if args.n_posters and len(rows) > args.n_posters:
        rows = sorted(random.Random(args.select_seed).sample(rows, args.n_posters),
                      key=lambda r: r["poster_file"])
    print(f"  Generating {len(rows)} poster(s) x {len(FORMATS)} formats x {len(CONDITIONS)} conditions "
          f"= {len(rows) * len(FORMATS) * len(CONDITIONS)} layouts\n")

    samples = []
    for i, row in enumerate(rows):
        poster_path = posters[row["poster_file"]]
        stem = os.path.splitext(row["poster_file"])[0]
        content = _content_for(row, i)
        logos = [p.strip() for p in row.get("logo_files", "").split(";") if p.strip()] or None
        outputs = {}
        for fmt, payload in FORMATS.items():
            for cond in CONDITIONS:
                out_dir = os.path.join(args.out_dir, "samples", stem, f"{fmt}_{cond}")
                os.makedirs(out_dir, exist_ok=True)
                content_path = os.path.join(out_dir, "content.json")
                with open(content_path, "w") as f:
                    json.dump(content[fmt], f, indent=2, ensure_ascii=False)
                with open(os.path.join(out_dir, "pipeline.log"), "w") as log, \
                        contextlib.redirect_stdout(log):
                    result = pipeline.run_pipeline(
                        payload_path=payload, template_image=poster_path,
                        content_data_path=content_path, use_gnn=(cond == "gnn"),
                        output_dir=out_dir, logo_images=logos,
                    )
                png = rasterize.svg_to_png(result["rendered_path"], scale=2.0)
                outputs[(fmt, cond)] = result["rendered_path"]
                samples.append({
                    "poster_file": row["poster_file"], "event_title": row["event_title"],
                    "format": fmt, "condition": cond,
                    "svg": os.path.relpath(result["rendered_path"], _ROOT),
                    "png": os.path.relpath(png, _ROOT),
                    "winner_candidate": result["winner"]["candidate_id"],
                    "c_total": result["winner"]["c_total"],
                    "logo_source": result.get("logo_source") or "none",
                })
                print(f"  [{len(samples):>2}] {stem[:28]:<28} {fmt:<11} {cond:<8} "
                      f"C_total={result['winner']['c_total']:.4f}")
        for fmt in FORMATS:
            with open(outputs[(fmt, "gnn")]) as a, open(outputs[(fmt, "baseline")]) as b:
                identical = a.read() == b.read()
            for s in samples[-4:]:
                if s["format"] == fmt:
                    s["identical_to_pair"] = identical

    rng = random.Random(args.key_seed)
    rng.shuffle(samples)
    for n, s in enumerate(samples, start=1):
        s["code"] = f"S{n:02d}"
    samples.sort(key=lambda s: s["code"])
    os.makedirs(args.out_dir, exist_ok=True)
    key_path = os.path.join(args.out_dir, "phase4_key.csv")
    with open(key_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["code"] + [k for k in samples[0] if k != "code"])
        writer.writeheader()
        writer.writerows(samples)
    same = sum(1 for s in samples if s.get("identical_to_pair")) // 2
    print(f"\n  Answer key → {key_path}  (keep private — this un-blinds the packet)")
    if same:
        print(f"  Note: {same} poster/format pair(s) came out identical under GNN and baseline.")


# ---------------------------------------------------------------------------
# Step 3: packet
# ---------------------------------------------------------------------------

def _read_key(path: str) -> list:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _page_order(samples: list, seed: int) -> list:
    """Randomized order in which no two consecutive pages share a poster, so
    a poster's GNN and baseline versions are never seen side by side."""
    rng = random.Random(seed)
    for _ in range(20000):
        order = samples[:]
        rng.shuffle(order)
        if all(a["poster_file"] != b["poster_file"] for a, b in zip(order, order[1:])):
            return order
    # Greedy fallback: always pick from the poster with the most pages left.
    pool, order = samples[:], []
    rng.shuffle(pool)
    while pool:
        counts = {}
        for s in pool:
            counts[s["poster_file"]] = counts.get(s["poster_file"], 0) + 1
        last = order[-1]["poster_file"] if order else None
        choice = max((s for s in pool if s["poster_file"] != last),
                     key=lambda s: counts[s["poster_file"]], default=pool[0])
        pool.remove(choice)
        order.append(choice)
    return order


def _img_data_uri(path: str, max_side: int, fmt: str) -> tuple:
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        img.save(buf, format=fmt, quality=90) if fmt == "JPEG" else img.save(buf, format=fmt)
        size = img.size
    mime = "image/jpeg" if fmt == "JPEG" else "image/png"
    return f"data:{mime};base64," + base64.b64encode(buf.getvalue()).decode("ascii"), size


def _fit(box_x, box_y, box_w, box_h, img_w, img_h) -> tuple:
    scale = min(box_w / img_w, box_h / img_h)
    w, h = img_w * scale, img_h * scale
    return box_x + (box_w - w) / 2, box_y + (box_h - h) / 2, w, h


def _text(x, y, s, size=12, weight="normal", fill=INK, anchor="start", style="normal") -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" '
            f'font-weight="{weight}" font-style="{style}" fill="{fill}" '
            f'text-anchor="{anchor}">{escape(s)}</text>')


def _wrapped(x, y, s, width_chars, size=12, leading=1.45, **kw) -> tuple:
    lines = textwrap.wrap(s, width=width_chars) or [""]
    out = [_text(x, y + i * size * leading, line, size=size, **kw) for i, line in enumerate(lines)]
    return out, y + len(lines) * size * leading


def _svg_page(body: list) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="297mm" height="210mm" viewBox="0 0 {PAGE_W} {PAGE_H}">'
            f'<rect width="{PAGE_W}" height="{PAGE_H}" fill="#ffffff"/>' + "".join(body) + "</svg>")


def _scale_row(x, y, spacing=64) -> list:
    """Five circles (1-5) with their Table 2 rating words underneath."""
    els = []
    for k, (score, rating, _) in enumerate(sorted(RATING_SCALE)):
        cx = x + k * spacing
        els.append(f'<circle cx="{cx:.1f}" cy="{y:.1f}" r="13" fill="none" stroke="{INK}" stroke-width="1.3"/>')
        els.append(_text(cx, y + 4.5, str(score), size=13, weight="bold", anchor="middle"))
        els.append(_text(cx, y + 28, rating, size=8.5, fill=MUTED, anchor="middle"))
    return els


def _instructions_pages(expert: str, n: int) -> list:
    minutes = round(n * 0.9 / 5) * 5
    body = [_text(60, 76, "ThemeSync — Expert Aesthetic Evaluation", size=28, weight="bold"),
            _text(60, 108, f"Rating packet for: {expert}   ·   {n} layouts   ·   about {minutes} minutes",
                  size=14, fill=MUTED)]
    y = 156
    paragraphs = [
        "Each page shows a master layout (an event poster, on the left) next to a certificate or "
        "event ID that was generated from it (on the right). Please rate the generated layout on the "
        "three design parameters below, by circling one score from 1 to 5 for each.",
        "Judge the generated layout only. The master layout is there so you can see which colours, "
        "logos and visual style the generated layout was meant to carry over.",
        "Some pages may look alike. Please rate every page on its own merits, without comparing it "
        "to other pages or going back to change earlier scores.",
        "Names, dates and wording are sample data. Please don't rate the text content itself, only "
        "how it is laid out, styled and branded.",
    ]
    for p in paragraphs:
        els, y = _wrapped(60, y, p, 128, size=14)
        body += els
        y += 10
    y += 8
    body.append(_text(60, y, "The three design parameters", size=16, weight="bold"))
    y += 30
    for _, name, criterion in DIMENSIONS:
        body.append(_text(60, y, name, size=14, weight="bold"))
        els, y = _wrapped(60, y + 21, criterion, 128, size=13, fill=MUTED)
        body += els
        y += 8
    pages = [_svg_page(body)]

    body = [_text(60, 72, "Rating scale (Table 2: Mean Opinion Score Rating Scale)", size=18, weight="bold")]
    y = 118
    body.append(_text(60, y, "Score", size=12, weight="bold"))
    body.append(_text(160, y, "Rating", size=12, weight="bold"))
    body.append(_text(320, y, "Description", size=12, weight="bold"))
    for score, rating, description in RATING_SCALE:
        y += 34
        body.append(f'<line x1="60" y1="{y - 22}" x2="900" y2="{y - 22}" stroke="{RULE}"/>')
        body.append(_text(72, y, str(score), size=13, weight="bold"))
        body.append(_text(160, y, rating, size=12.5))
        body.append(_text(320, y, description, size=12.5))
    y += 60
    body.append(_text(60, y, "Evaluator details", size=14, weight="bold"))
    for label in ("Name", "Professional background / years of industry experience",
                  "Signature", "Date"):
        y += 44
        body.append(_text(60, y, label, size=11.5, fill=MUTED))
        body.append(f'<line x1="430" y1="{y + 2}" x2="1000" y2="{y + 2}" stroke="{INK}" stroke-width="0.8"/>')
    return pages + [_svg_page(body)]


def _sample_page(sample: dict, page_no: int, total: int) -> str:
    """One sample: a small master-layout reference on the left, the generated
    layout as large as the page allows on the right (so certificate body text
    stays legible in print), and the three rating scales side by side below."""
    body = [_text(40, 44, f"Sample {sample['code']}", size=20, weight="bold"),
            _text(PAGE_W - 40, 44, f"page {page_no} of {total}", size=10, fill=MUTED, anchor="end"),
            f'<line x1="40" y1="58" x2="{PAGE_W - 40}" y2="58" stroke="{RULE}"/>']

    top, panel_h = 92, 560
    left = (40, top, 320, panel_h)
    right = (385, top, PAGE_W - 40 - 385, panel_h)
    fmt_label = "Generated certificate" if sample["format"] == "certificate" else "Generated event ID"
    body.append(_text(left[0], top - 12, "Master layout (theme source)", size=11, fill=MUTED))
    body.append(_text(right[0], top - 12, fmt_label + " — please rate this one", size=11, weight="bold"))

    poster_uri, (pw, ph) = _img_data_uri(os.path.join(POSTERS_DIR, sample["poster_file"]), 1400, "JPEG")
    x, y, w, h = _fit(*left, pw, ph)
    body.append(f'<image x="{x:.1f}" y="{top:.1f}" width="{w:.1f}" height="{h:.1f}" xlink:href="{poster_uri}"/>')
    out_uri, (ow, oh) = _img_data_uri(os.path.join(_ROOT, sample["png"]), 2400, "PNG")
    x, y, w, h = _fit(*right, ow, oh)
    body.append(f'<rect x="{x:.1f}" y="{top:.1f}" width="{w:.1f}" height="{h:.1f}" fill="none" stroke="{RULE}"/>')
    body.append(f'<image x="{x:.1f}" y="{top:.1f}" width="{w:.1f}" height="{h:.1f}" xlink:href="{out_uri}"/>')

    y = top + panel_h + 26
    body.append(f'<line x1="40" y1="{y - 12}" x2="{PAGE_W - 40}" y2="{y - 12}" stroke="{RULE}"/>')
    col_w = (PAGE_W - 80) / 3
    for c, (_, name, _) in enumerate(DIMENSIONS):
        cx = 40 + c * col_w
        body.append(_text(cx, y + 8, name, size=11.5, weight="bold"))
        body += _scale_row(cx + 14, y + 34)
    y += 100
    body.append(_text(40, y, "Comments (optional):", size=11, fill=MUTED))
    body.append(f'<line x1="180" y1="{y + 2}" x2="{PAGE_W - 40}" y2="{y + 2}" stroke="{INK}" stroke-width="0.6"/>')
    return _svg_page(body)


def _closing_page(n: int) -> str:
    body = [_text(60, 90, "Thank you.", size=24, weight="bold")]
    y = 140
    for line in [f"Before handing the packet back, please check that each of the {n} sample pages",
                 "has exactly one circled score for each of the three parameters.",
                 "",
                 "Your ratings will be averaged into the Mean Opinion Score reported in the study."]:
        body.append(_text(60, y, line, size=13))
        y += 24
    return _svg_page(body)


def cmd_packet(args) -> None:
    global POSTERS_DIR
    POSTERS_DIR = args.posters_dir
    samples = _read_key(args.key)
    order = _page_order(samples, args.order_seed)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", args.expert).strip("_") or "expert"
    out = os.path.join(args.out_dir, "packets", slug)
    pages_dir = os.path.join(out, "pages")
    os.makedirs(pages_dir, exist_ok=True)

    svgs = _instructions_pages(args.expert, len(order))
    first_sample_page = len(svgs) + 1
    total = len(svgs) + len(order) + 1
    svgs += [_sample_page(s, first_sample_page + i, total) for i, s in enumerate(order)]
    svgs.append(_closing_page(len(order)))

    # Each page is rendered to a 200-dpi JPEG and wrapped as a one-page PDF.
    # A vector PDF straight from Cairo re-stores the posters' JPEG photos as
    # raw pixels (~3.3 MB per page, ~170 MB for a 60-layout packet); JPEG
    # pages keep the whole packet printable at a fraction of that, and
    # 200 dpi is ample for the text and rating circles.
    dpi = 200
    page_px = (round(297 / 25.4 * dpi), round(210 / 25.4 * dpi))
    pdfs = []
    for i, svg in enumerate(svgs, start=1):
        png = rasterize.cairosvg.svg2png(bytestring=svg.encode("utf-8"),
                                         output_width=page_px[0], output_height=page_px[1])
        pdf = os.path.join(pages_dir, f"page_{i:03d}.pdf")
        with Image.open(io.BytesIO(png)) as page:
            page.convert("RGB").save(pdf, "PDF", resolution=dpi, quality=90)
        pdfs.append(pdf)
    packet_pdf = os.path.join(out, f"packet_{slug}.pdf")
    try:
        subprocess.run(["pdfunite", *pdfs, packet_pdf], check=True)
    except (OSError, subprocess.CalledProcessError) as e:
        sys.exit(f"Could not merge pages with pdfunite ({e}); single pages are in {pages_dir}")

    scores_csv = os.path.join(out, f"scores_{slug}.csv")
    with open(scores_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["page", "code"] + [k for k, _, _ in DIMENSIONS] + ["comment"])
        for i, s in enumerate(order):
            writer.writerow([first_sample_page + i, s["code"], "", "", "", ""])
    with open(os.path.join(out, "order.json"), "w") as f:
        json.dump({"expert": args.expert, "order_seed": args.order_seed,
                   "codes": [s["code"] for s in order]}, f, indent=2)

    print(f"  Packet   → {packet_pdf}  ({total} pages)")
    print(f"  Scores   → {scores_csv}  (type the circled scores in here)")
    print("  Print in colour, on the same printer for every expert.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ThemeSync Phase 4 rating packet generator")
    sub = parser.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("template", help="list posters and write manifest.csv to fill in")
    t.add_argument("--posters_dir", default=POSTERS_DIR)

    g = sub.add_parser("generate", help="generate all layouts and the private answer key")
    g.add_argument("--posters_dir", default=POSTERS_DIR)
    g.add_argument("--out_dir", default=OUT_DIR)
    g.add_argument("--n_posters", type=int, default=15)
    g.add_argument("--select_seed", type=int, default=2026, help="picks the posters if more than n")
    g.add_argument("--key_seed", type=int, default=2026, help="assigns the blind sample codes")
    g.add_argument("--allow_seen", action="store_true",
                   help="allow posters that match annotated images (dry runs only)")

    p = sub.add_parser("packet", help="build one expert's printable PDF and score sheet")
    p.add_argument("--expert", required=True)
    p.add_argument("--order_seed", type=int, required=True,
                   help="use a different seed per expert so page orders differ")
    p.add_argument("--key", default=KEY_PATH)
    p.add_argument("--posters_dir", default=POSTERS_DIR)
    p.add_argument("--out_dir", default=OUT_DIR)

    args = parser.parse_args()
    {"template": cmd_template, "generate": cmd_generate, "packet": cmd_packet}[args.cmd](args)


if __name__ == "__main__":
    main()
