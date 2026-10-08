"""
ThemeSync — The 64 rated layouts: p.56's F1 and whether their text fits
========================================================================
The revision list's "Code before Chapter 4" asks for F1 over the rated set
in the results files. This script reads the 64 layouts the Phase 4 experts
rate (16 posters x 2 formats x GNN/baseline) straight from the files the
packets were printed from, data/phase4/samples/<poster>/<format>_<condition>/:

  ThemeSync_*_state_chain.json   the layout's boxes (its current state)
  ThemeSync_*_populated.svg      what was drawn

It only reads. Nothing in data/phase4/ is written, and no sample code is
printed or saved; the key is read only to confirm that each folder's layout
is the one the key records (its winning candidate).

Per layout:
  F1 (p.56)       layout_report.structural_accuracy on the boxes
  reading order   stacked elements keep the Spatial Hierarchy Index's order
                  top to bottom (stress_test.reading_order)
  text fit        every rendered line measured with the bundled Montserrat's
                  glyph metrics (stress_test.text_fit): ink more than 2 px
                  outside its box, and whether that ink lands on another
                  element's box or leaves the canvas
  what shows      ink against ink, independent of the boxes: a line of text
                  over another element's text, over its picture (a logo, the
                  title artwork), or over a motif
  smallest text   in points at print size (event ID A6, 105 mm; certificate
                  279.4 mm, as in stress_test.py)

Usage:
  python src/evaluation/rated_layouts_check.py

Writes results/rated_layouts_check.json.
"""

import base64
import csv
import datetime
import glob
import io
import json
import os
import sys
import xml.etree.ElementTree as ET

_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_EVAL_DIR)
_ROOT = os.path.dirname(_SRC)
for _p in (_EVAL_DIR, _SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import phase4_packet as p4                                     # noqa: E402
import stress_test as st                                       # noqa: E402
from layout_report import structural_accuracy                  # noqa: E402
from schema_validation import content_schema                   # noqa: E402
from PIL import Image                                          # noqa: E402

SAMPLES = os.path.join(p4.OUT_DIR, "samples")
NS = "{http://www.w3.org/2000/svg}"
XLINK = "{http://www.w3.org/1999/xlink}href"


def _drawn_rect(el) -> list:
    """The rectangle an <image> actually covers: its box, or the part a
    'meet' fit fills, from the embedded picture's own size."""
    x, y = float(el.get("x", 0)), float(el.get("y", 0))
    w, h = float(el.get("width")), float(el.get("height"))
    par = el.get("preserveAspectRatio", "xMidYMid meet")
    href = el.get(XLINK) or el.get("href") or ""
    if par == "none" or "slice" in par or not href.startswith("data:"):
        return [x, y, x + w, y + h]
    with Image.open(io.BytesIO(base64.b64decode(href.split(",", 1)[1]))) as img:
        iw, ih = img.size
    s = min(w / iw, h / ih)
    dw, dh = iw * s, ih * s
    ax = {"xMin": 0.0, "xMid": 0.5, "xMax": 1.0}.get(par[:4], 0.5)
    ay = {"YMin": 0.0, "YMid": 0.5, "YMax": 1.0}.get(par[4:8], 0.5)
    left, top = x + (w - dw) * ax, y + (h - dh) * ay
    return [left, top, left + dw, top + dh]


def pictures(svg_path: str) -> dict:
    """{node_id: [(kind, drawn rect)]} for every picture in a node's group:
    logos, the title artwork, motifs."""
    out = {}
    for g in ET.parse(svg_path).getroot().iter(f"{NS}g"):
        node_id = g.get("data-node-id")
        if not node_id:
            continue
        kind = "motif" if g.get("data-kind") == "decor" else "picture"
        for el in g.iter(f"{NS}image"):
            out.setdefault(node_id, []).append((kind, _drawn_rect(el)))
    return out


def _hit(a: list, b: list) -> bool:
    return min(a[2], b[2]) - max(a[0], b[0]) > 1 and min(a[3], b[3]) - max(a[1], b[1]) > 1


def ink_clashes(extents: dict, pics: dict) -> dict:
    """Text ink over another element's text, picture or motif."""
    boxes = {n: [[l["left"], l["top"], l["right"], l["bottom"]] for l in lines] for n, lines in extents.items()}
    text_over_text, text_over_picture, text_over_motif = set(), set(), set()
    ids = sorted(boxes)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if any(_hit(p, q) for p in boxes[a] for q in boxes[b]):
                text_over_text.add(f"{a.strip('{}')} / {b.strip('{}')}")
        for owner, items in pics.items():
            if owner == a:
                continue
            for kind, rect in items:
                if any(_hit(p, rect) for p in boxes[a]):
                    (text_over_motif if kind == "motif" else text_over_picture).add(
                        f"{a.strip('{}')} over {owner.strip('{}')}")
    return {"text_over_text": sorted(text_over_text), "text_over_picture": sorted(text_over_picture),
            "text_over_motif": sorted(text_over_motif)}


def check(poster: str, fmt: str, cond: str, metrics: st.FontMetrics, key: dict) -> dict:
    stem = os.path.splitext(poster)[0]
    folder = os.path.join(SAMPLES, stem, f"{fmt}_{cond}")
    svg = glob.glob(os.path.join(folder, "ThemeSync_*_populated.svg"))
    chain = glob.glob(os.path.join(folder, "ThemeSync_*_state_chain.json"))
    if len(svg) != 1 or len(chain) != 1:
        return {"poster": poster, "format": fmt, "condition": cond, "error": "missing SVG or state chain"}
    with open(chain[0], encoding="utf-8") as f:
        state = json.load(f)["state_chain"][-1]
    with open(os.path.join(_ROOT, p4.FORMATS[fmt]), encoding="utf-8") as f:
        meta = json.load(f)
    nodes = state["nodes"]
    root = ET.parse(svg[0]).getroot()
    canvas = (float(root.get("width")), float(root.get("height")))
    # Every element the payload mandates (repeating groups as {{Name}}_0...)
    mandated = content_schema(meta)["required"]
    acc = structural_accuracy(nodes, canvas[0], canvas[1], mandated)
    extents = st.text_extents(svg[0], metrics)
    px_per_pt = canvas[0] / st.FORMATS[fmt]["print_mm"] * st.PT_MM
    fit = st.text_fit(nodes, extents, canvas, px_per_pt)
    clashes = ink_clashes(extents[0], pictures(svg[0]))
    order = st.reading_order(nodes)
    rows = {r["node_id"]: r for r in fit["nodes"]}
    return {
        "poster": poster, "format": fmt, "condition": cond,
        "state": state["state_id"], "candidate": state.get("candidate_id"),
        "matches_key": key.get((poster, fmt, cond)) == state.get("candidate_id") if key else None,
        "canvas": list(canvas),
        "f1": acc["f1"], "tp": acc["tp"], "fp": acc["fp"], "fn": acc["fn"],
        "fp_fn_reasons": [f"{r['name']}: {'; '.join(r['reasons'])}" for r in acc["nodes"] if r["result"] != "TP"],
        "reading_order_violations": order,
        "text_fits": fit["fits"],
        "text_overflowing": {n.strip("{}"): {"px": rows[n]["overflow_px"], "side": rows[n]["worst_side"],
                                             "over": [o.strip("{}") for o in rows[n]["overwrites"]],
                                             "off_canvas": rows[n]["off_canvas"]}
                             for n in fit["overflowing"]},
        **clashes,
        "min_size_pt": fit["min_size_pt"],
        "small_text": [n.strip("{}") for n in fit["small_text"]],
        "text_sizes_pt": {r["node_id"].strip("{}"): r["min_size_pt"] for r in fit["nodes"]},
    }


def summarise(rows: list) -> dict:
    out = {}
    for fmt in p4.FORMATS:
        for cond in p4.CONDITIONS:
            sel = [r for r in rows if r["format"] == fmt and r["condition"] == cond and "error" not in r]
            out[f"{fmt} {cond}"] = {
                "layouts": len(sel),
                "f1_all_1": all(r["f1"] == 1.0 for r in sel),
                "f1_min": min((r["f1"] for r in sel), default=None),
                "reading_order_kept": sum(not r["reading_order_violations"] for r in sel),
                "text_fits": sum(r["text_fits"] for r in sel),
                "text_off_canvas": [r["poster"] for r in sel
                                    if any(v["off_canvas"] for v in r["text_overflowing"].values())],
                "text_overflowing": {r["poster"]: r["text_overflowing"] for r in sel if r["text_overflowing"]},
                "text_over_text": {r["poster"]: r["text_over_text"] for r in sel if r["text_over_text"]},
                "text_over_picture": {r["poster"]: r["text_over_picture"] for r in sel if r["text_over_picture"]},
                "text_over_motif": {r["poster"]: r["text_over_motif"] for r in sel if r["text_over_motif"]},
                "smallest_text_pt": min((r["min_size_pt"] for r in sel if r["min_size_pt"]), default=None),
            }
    return out


def main():
    rows_in = sorted([r for r in p4.read_manifest(p4.POSTERS_DIR) if r.get("poster_file")],
                     key=lambda r: r["poster_file"])
    key = {}
    if os.path.exists(p4.KEY_PATH):
        with open(p4.KEY_PATH, newline="", encoding="utf-8") as f:
            key = {(r["poster_file"], r["format"], r["condition"]): r["winner_candidate"]
                   for r in csv.DictReader(f)}
    metrics = st.FontMetrics()
    rows = []
    for row in rows_in:
        for fmt in p4.FORMATS:
            for cond in p4.CONDITIONS:
                r = check(row["poster_file"], fmt, cond, metrics, key)
                rows.append(r)
                if "error" in r:
                    print(f"  {row['poster_file'][:26]:<26} {fmt:<11} {cond:<8} {r['error']}")
                    continue
                flags = ([f"F1 {r['f1']}"] if r["f1"] < 1 else []) + \
                        ([f"order: {', '.join(r['reading_order_violations'])}"] if r["reading_order_violations"] else []) + \
                        [f"{n} {v['px']} px {v['side']}" + (" OFF CANVAS" if v["off_canvas"] else "")
                         + (f" over {', '.join(v['over'])}" if v["over"] else "")
                         for n, v in r["text_overflowing"].items()] + \
                        [f"ink: {c}" for c in r["text_over_text"] + r["text_over_picture"]]
                print(f"  {row['poster_file'][:26]:<26} {fmt:<11} {cond:<8} F1 {r['f1']:.2f}  "
                      f"min {r['min_size_pt']} pt  key {'ok' if r['matches_key'] else r['matches_key']}  "
                      f"{'; '.join(flags) or 'clean'}", flush=True)

    report = {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "source": "data/phase4/samples/<poster>/<format>_<condition>/ (the files the packets were printed "
                  "from); read only",
        "settings": {"fit_tolerance_px": st.FIT_TOL, "small_text_below_pt": st.MIN_PT,
                     "print_width_mm": {f: c["print_mm"] for f, c in st.FORMATS.items()},
                     "measurement": "as in stress_test.py; pictures by the area a 'meet' fit fills"},
        "layouts": len(rows),
        "all_match_key": all(r.get("matches_key") for r in rows) if key else None,
        "summary": summarise(rows),
        "rows": rows,
    }
    out = os.path.join(_ROOT, "results", "rated_layouts_check.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("\nSummary:")
    print(json.dumps(report["summary"], indent=1, ensure_ascii=False))
    print(f"\n-> {os.path.relpath(out, _ROOT)}")


if __name__ == "__main__":
    main()
