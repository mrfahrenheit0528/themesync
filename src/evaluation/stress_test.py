"""
ThemeSync — Stress test of the synthetic administrative templates (p.55)
=========================================================================
p.55 of Manu 0910.1: synthetic payloads "containing extreme spatial
variables—such as unusually long string values for student names or maximum
instantiation limits for repeating_groups (e.g., signature blocks)" were
injected to validate "the solver's capacity to execute dynamic aspect ratio
transformations, correctly enforce the mathematical spatial_hierarchy
weights, and dynamically resize text elements without violating predefined
bounding box limits or overwriting surrounding structural nodes".

This script runs that test on both formats (the 4:3 certificate and the A6
event ID) with the synthetic theme (no master layout), through the same
OrchestrationSession the dashboard uses, with the GNN on. It only reads the
system: every run writes into its own folder under data/rendered/stress_test/
(git-ignored), and nothing under data/phase4/, data/raw/ or the pipeline
changes. A failure is a finding to report, not something to tune away.

Cases, per format:
  reference      the format's sample content
  all at f×max   every text field at f = 25/50/75/100% of its max_characters,
                 as real words and as one unbroken token
  one at max     each text field alone at its max_characters (real words, and
                 one unbroken token)
  breaking point for a field that fails alone at its max: the shortest
                 length that fails, found by bisection
  one over       each text field at max_characters + 1: the schema
                 validation must reject it (checked without running)
  signatures     the certificate's signature blocks from 1 to --max_signatures

Measures, per run (the active canvas, i.e. the system's output):
  F1 (p.62)      layout_report.structural_accuracy on the output, and how
                 many of the six candidates have an FP or FN
  reading order  stacked elements keep the Spatial Hierarchy Index's order
                 top to bottom; repeating groups sit below them
  text fits      every rendered line of text measured in the SVG with the
                 bundled Montserrat's real glyph metrics (the face Cairo
                 prints with and the face the browser shows, whichever is
                 wider): ink outside its node's box by more than 2 px is an
                 overflow; overflow over another element's box overwrites it
  smallest text  the smallest font size reached, in px and in points at the
                 format's print size (certificate: 279.4 mm wide, US Letter
                 landscape, which fits 4:3; event ID: 105 mm, A6, p.55);
                 under 6 pt is flagged as hard to read in print

Usage:
  python src/evaluation/stress_test.py
  python src/evaluation/stress_test.py --max_signatures 12 --png

Writes results/stress_test.json.
"""

import argparse
import contextlib
import copy
import datetime
import functools
import io
import json
import os
import platform
import sys
import xml.etree.ElementTree as ET

_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_EVAL_DIR)
_ROOT = os.path.dirname(_SRC)
for _p in (_EVAL_DIR, _SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pipeline                                            # noqa: E402 — puts models/solvers/renderers on the path
from layout_report import structural_accuracy              # noqa: E402
from schema_validation import validate_content             # noqa: E402

RAW = os.path.join(_ROOT, "data", "raw")
FORMATS = {
    "certificate": {"payload": os.path.join(RAW, "academic_payload.json"),
                    "sample": os.path.join(RAW, "sample_content.json"), "print_mm": 279.4},
    "event_id":    {"payload": os.path.join(RAW, "id_payload.json"),
                    "sample": os.path.join(RAW, "sample_content_id.json"), "print_mm": 105.0},
}
RUNS_DIR = os.path.join(_ROOT, "data", "rendered", "stress_test")
FRACTIONS = (0.25, 0.5, 0.75, 1.0)
FIT_TOL = 2.0          # px of ink outside the box tolerated (rounding, anti-aliasing)
MIN_PT = 6.0           # under this, text is flagged as hard to read in print
PT_MM = 25.4 / 72.0

WORDS = ("Camarines Sur Polytechnic Colleges Department of Information Technology Leadership "
         "Development Excellence Outstanding Participation Recognition Academic International "
         "Conference Celebration Foundation Organization Association").split()
NAMES = ("Maria Angela Santos Dela Cruz Juan Miguel Reyes Kristine Joy Bautista Christopher "
         "Alexander Villanueva Fernandez Montemayor Concepcion Evangelista Bartolome Magdalena").split()
TOKEN = "Pneumonoultramicroscopicsilicovolcanoconiosis"
SIGNATORIES = [("Dr. Juan dela Cruz", "College President"), ("Prof. Ana Reyes", "Dean, CCS"),
               ("Engr. Rico Santos", "Thesis Adviser"), ("Dr. Kristine Joy Bautista", "Vice President"),
               ("Prof. Miguel Villanueva", "Department Chair"), ("Dr. Angela Fernandez", "Registrar"),
               ("Engr. Christopher Montemayor", "Program Head"), ("Prof. Magdalena Evangelista", "OSA Director"),
               ("Dr. Alexander Concepcion", "Research Director"), ("Prof. Bartolome Cruz", "Class Adviser"),
               ("Dr. Joy Santos-Reyes", "Guidance Head"), ("Engr. Miguel Bautista", "IT Coordinator")]


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

def words_of(n: int, vocab: tuple) -> str:
    """Real words, exactly n characters (the last word cut to fit)."""
    out, i = "", 0
    while len(out) < n:
        out += ("" if not out else " ") + vocab[i % len(vocab)]
        i += 1
    out = out[:n]
    return out[:-1] + "x" if out.endswith(" ") else out


def unbroken(n: int) -> str:
    """One token with no spaces, exactly n characters."""
    return (TOKEN * (n // len(TOKEN) + 1))[:n]


def text_fields(meta: dict) -> dict:
    """{key: max_characters} for every text field with a limit."""
    return {k: v["max_characters"] for k, v in meta["variable_schema"].items()
            if v.get("structural_class") == "text_node" and v.get("max_characters")}


def filler(key: str, n: int, kind: str) -> str:
    if kind == "unbroken":
        return unbroken(n)
    return words_of(n, NAMES if "Name" in key else WORDS)


def signature_payload(meta: dict, k: int, folder: str) -> tuple:
    """A copy of the certificate payload with k signature blocks (written in
    the run's own folder), and content for them."""
    meta = copy.deepcopy(meta)
    meta["variable_schema"]["{{Signature_Blocks}}"]["instantiation_count"] = k
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "payload.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    keys = [f"{{{{Signature_Blocks}}}}_{i}" for i in range(k)] if k > 1 else ["{{Signature_Blocks}}"]
    return path, {key: f"{name}\n{title}" for key, (name, title) in
                  zip(keys, (SIGNATORIES * 2)[:k])}


# ---------------------------------------------------------------------------
# Measuring the rendered text with the bundled font
# ---------------------------------------------------------------------------

class FontMetrics:
    """Advance widths and ink bounds from the bundled Montserrat faces."""
    FACES = ("Regular", "Italic", "SemiBold", "Bold", "BoldItalic", "Black")

    def __init__(self):
        from fontTools.ttLib import TTFont
        self.fonts = {}
        for face in self.FACES:
            path = os.path.join(_ROOT, "assets", "fonts", "montserrat", f"Montserrat-{face}.ttf")
            if os.path.exists(path):
                self.fonts[face] = TTFont(path)

    @functools.lru_cache(maxsize=None)
    def _glyph(self, face: str, ch: str) -> tuple:
        from fontTools.pens.boundsPen import BoundsPen
        font = self.fonts[face]
        name = font.getBestCmap().get(ord(ch), ".notdef")
        advance = font["hmtx"][name][0]
        pen = BoundsPen(font.getGlyphSet())
        font.getGlyphSet()[name].draw(pen)
        y_min, y_max = (pen.bounds[1], pen.bounds[3]) if pen.bounds else (0, 0)
        return advance, y_min, y_max

    def measure(self, face: str, text: str, size: float, spacing: float) -> tuple:
        """(width, ink top above the baseline, ink bottom below it) in px."""
        upm = self.fonts[face]["head"].unitsPerEm
        adv, lo, hi = 0.0, 0.0, 0.0
        for ch in text:
            a, y0, y1 = self._glyph(face, ch)
            adv += a
            lo, hi = min(lo, y0), max(hi, y1)
        return adv * size / upm + spacing * max(len(text) - 1, 0), hi * size / upm, -lo * size / upm

    def central_offset(self, size: float) -> float:
        """Baseline below an SVG 'central' alignment point (em-box centre)."""
        hhea = self.fonts["Regular"]["hhea"]
        upm = self.fonts["Regular"]["head"].unitsPerEm
        return (hhea.ascent + hhea.descent) / 2.0 * size / upm

    @staticmethod
    def faces_for(weight: str, style: str) -> tuple:
        """The face Cairo prints with (normal/bold only) and the one the
        browser shows (true weight)."""
        w = {"bold": 700, "normal": 400}.get(str(weight).lower())
        w = w if w is not None else int(float(weight))
        italic = style == "italic"
        if w < 600:
            return ("Italic",) if italic else ("Regular",)
        if italic:
            return ("BoldItalic",)
        return tuple(dict.fromkeys(("Bold", {600: "SemiBold", 900: "Black"}.get(w, "Bold"))))


def text_extents(svg_path: str, metrics: FontMetrics) -> tuple:
    """({node_id: [line extents]}, {node_id: [shape boxes]}) for every text
    line in the SVG (shadow copies skipped) and every shape drawn for the
    text (the event ID's name pill and role band, which may run edge to
    edge)."""
    ns = "{http://www.w3.org/2000/svg}"
    root = ET.parse(svg_path).getroot()
    out, shapes = {}, {}
    for g in root.iter(f"{ns}g"):
        node_id = g.get("data-node-id")
        if not node_id or g.get("data-kind") in ("image_node", "decor"):
            continue
        for r in g.iter(f"{ns}rect"):
            x, y = float(r.get("x", 0)), float(r.get("y", 0))
            shapes.setdefault(node_id, []).append([x, y, float(r.get("width")), float(r.get("height"))])
        for t in g.iter(f"{ns}text"):
            if t.get("fill-opacity") or not (t.text or "").strip():
                continue
            size = float(t.get("font-size"))
            spacing = float(t.get("letter-spacing") or 0.0)
            faces = metrics.faces_for(t.get("font-weight", "normal"), t.get("font-style", "normal"))
            dims = [metrics.measure(f, t.text, size, spacing) for f in faces]
            width, above, below = (max(d[0] for d in dims), max(d[1] for d in dims), max(d[2] for d in dims))
            x, y = float(t.get("x")), float(t.get("y"))
            if t.get("dominant-baseline") == "central":
                y += metrics.central_offset(size)
            anchor = t.get("text-anchor", "start")
            left = x - (width / 2.0 if anchor == "middle" else width if anchor == "end" else 0.0)
            out.setdefault(node_id, []).append({"text": t.text, "size": size, "left": left, "right": left + width,
                                                "top": y - above, "bottom": y + below})
    return out, shapes


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def _area(a: list, b: list) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 1 and h > 1 else 0.0


def text_fit(nodes: list, extents: tuple, canvas: tuple, px_per_pt: float) -> dict:
    """Per text node: overflow beyond its box (or the shape drawn for it),
    whether the overflow lands on another element, and its smallest font
    size."""
    extents, shapes = extents
    boxes = {n["node_id"]: n["bbox"] for n in nodes if n.get("structural_class") != "decor"}
    rows = []
    for node_id, lines in extents.items():
        if node_id not in boxes:
            continue
        x, y, w, h = boxes[node_id]
        for sx, sy, sw, sh in shapes.get(node_id, []):
            x2, y2 = max(x + w, sx + sw), max(y + h, sy + sh)
            x, y = min(x, sx), min(y, sy)
            w, h = x2 - x, y2 - y
        ink = [min(l["left"] for l in lines), min(l["top"] for l in lines),
               max(l["right"] for l in lines), max(l["bottom"] for l in lines)]
        over = {"left": x - ink[0], "right": ink[2] - (x + w), "top": y - ink[1], "bottom": ink[3] - (y + h)}
        worst = max(over.values())
        hits = [o for o, (ox, oy, ow, oh) in boxes.items()
                if o != node_id and worst > FIT_TOL and _area(ink, [ox, oy, ox + ow, oy + oh])]
        size = min(l["size"] for l in lines)
        rows.append({"node_id": node_id, "lines": len(lines), "min_size_px": round(size, 1),
                     "min_size_pt": round(size / px_per_pt, 1),
                     "overflow_px": round(max(0.0, worst), 1),
                     "worst_side": max(over, key=over.get) if worst > FIT_TOL else None,
                     "overwrites": hits,
                     "off_canvas": ink[0] < -FIT_TOL or ink[1] < -FIT_TOL or ink[2] > canvas[0] + FIT_TOL
                     or ink[3] > canvas[1] + FIT_TOL})
    return {"nodes": rows,
            "fits": all(r["overflow_px"] <= FIT_TOL for r in rows),
            "overflowing": [r["node_id"] for r in rows if r["overflow_px"] > FIT_TOL],
            "overwriting": sorted({r["node_id"] for r in rows if r["overwrites"]}),
            "min_size_px": min((r["min_size_px"] for r in rows), default=None),
            "min_size_pt": min((r["min_size_pt"] for r in rows), default=None),
            "small_text": [r["node_id"] for r in rows if r["min_size_pt"] < MIN_PT]}


def reading_order(nodes: list) -> list:
    """Violations of the Spatial Hierarchy Index's top-to-bottom order."""
    stack = sorted((n for n in nodes if n.get("structural_class") not in ("decor", "repeating_group")),
                   key=lambda n: n["spatial_hierarchy"])
    bad = []
    for prev, cur in zip(stack, stack[1:]):
        # two nodes on one line (cassowary_engine's `row`) read left to right
        if (cur.get("row") or {}).get("with") == prev["node_id"]:
            continue
        if cur["bbox"][1] < prev["bbox"][1] - 1.0:
            bad.append(f"{cur['node_id']} above {prev['node_id']}")
    if stack:
        floor = max(n["bbox"][1] + n["bbox"][3] for n in stack)
        bad += [f"{n['node_id']} above the stack's foot" for n in nodes
                if n.get("structural_class") == "repeating_group" and n["bbox"][1] < floor - 1.0]
    return bad


# ---------------------------------------------------------------------------
# One run
# ---------------------------------------------------------------------------

def run_case(fmt: str, case: str, content: dict, payload: str, folder: str, metrics: FontMetrics,
             png: bool) -> dict:
    cfg = FORMATS[fmt]
    session = pipeline.OrchestrationSession(payload, content_data=content, output_dir=folder)
    with contextlib.redirect_stdout(io.StringIO()):
        summary = session.run()
    nodes = session.chain.current["nodes"]
    mandated = [n["node_id"] for n in session.base_nodes]
    acc = structural_accuracy(nodes, session.canvas_w, session.canvas_h, mandated)
    cand_bad = [c["candidate_id"] for c in session.candidates
                if structural_accuracy(c["nodes"], session.canvas_w, session.canvas_h, mandated)["f1"] < 1.0]
    px_per_pt = session.canvas_w / cfg["print_mm"] * PT_MM
    fit = text_fit(nodes, text_extents(session.rendered_path, metrics), (session.canvas_w, session.canvas_h),
                   px_per_pt)
    order = reading_order(nodes)
    if png:
        import rasterize
        rasterize.svg_to_png(session.rendered_path, os.path.join(folder, "output.png"))
    problems = ([f"F1 {acc['f1']:.2f} ({', '.join(r['name'] + ': ' + '; '.join(r['reasons']) for r in acc['nodes'] if r['result'] != 'TP')})"]
                if acc["f1"] < 1.0 else [])
    problems += [f"reading order: {v}" for v in order]
    problems += [f"text overflows: {n} by {r['overflow_px']} px ({r['worst_side']})"
                 + (f", over {', '.join(r['overwrites'])}" if r["overwrites"] else "")
                 for n in fit["overflowing"] for r in fit["nodes"] if r["node_id"] == n]
    return {
        "format": fmt, "case": case, "folder": os.path.relpath(folder, _ROOT),
        "output_candidate": session.candidates[0]["candidate_id"],
        "f1": acc["f1"], "tp": acc["tp"], "fp": acc["fp"], "fn": acc["fn"],
        "candidates_with_fp_or_fn": cand_bad,
        "reading_order_violations": order,
        "text": fit,
        "latency_ms": summary.get("total_ms"),
        "passes": acc["f1"] == 1.0 and not order and fit["fits"],
        "problems": problems,
    }


def run_format(fmt: str, metrics: FontMetrics, max_signatures: int, png: bool) -> dict:
    cfg = FORMATS[fmt]
    with open(cfg["payload"], encoding="utf-8") as f:
        meta = json.load(f)
    with open(cfg["sample"], encoding="utf-8") as f:
        sample = json.load(f)
    fields = text_fields(meta)
    base = os.path.join(RUNS_DIR, fmt)
    runs = []

    def go(case: str, content: dict, payload: str = cfg["payload"], keep: bool = True) -> dict:
        folder = os.path.join(base, case.replace(" ", "_").replace("%", "pct").replace("×", "x"))
        r = run_case(fmt, case, content, payload, folder, metrics, png)
        if keep:
            runs.append(r)
        flag = "pass" if r["passes"] else "FAIL: " + "; ".join(r["problems"][:2])
        print(f"  {fmt:<12} {case:<44} F1 {r['f1']:.2f}  min {r['text']['min_size_px']} px "
              f"({r['text']['min_size_pt']} pt)  {flag}", flush=True)
        return r

    go("reference", dict(sample))
    for kind in ("words", "unbroken"):
        for frac in FRACTIONS:
            content = dict(sample)
            content.update({k: filler(k, max(1, round(frac * m)), kind) for k, m in fields.items()})
            go(f"all at {int(frac * 100)}% {kind}", content)
    breaking = []
    for kind in ("words", "unbroken"):
        for key, m in fields.items():
            content = dict(sample)
            content[key] = filler(key, m, kind)
            if go(f"one at max {kind} {key.strip('{}')}", content)["passes"]:
                continue
            # The shortest failing length, by bisection from one character
            lo, hi, last = 1, m, None
            while hi - lo > 1:
                mid = (lo + hi) // 2
                content[key] = filler(key, mid, kind)
                r = go(f"breaking {kind} {key.strip('{}')} {mid}", content, keep=False)
                if r["passes"]:
                    lo = mid
                else:
                    hi, last = mid, r
            breaking.append({"field": key.strip("{}"), "kind": kind, "max_characters": m,
                             "longest_passing": lo, "shortest_failing": hi,
                             "problems": (last or runs[-1])["problems"]})

    # One character over: the schema must reject it (no run)
    rejections = []
    for key, m in fields.items():
        content = dict(sample)
        content[key] = filler(key, m + 1, "words")
        check = validate_content(content, meta)
        rejections.append({"field": key, "length": m + 1, "max_characters": m, "rejected": not check["valid"],
                           "error": check["errors"][0] if check["errors"] else None})

    signatures = []
    if "{{Signature_Blocks}}" in meta["variable_schema"]:
        plain = {k: v for k, v in sample.items() if not k.startswith("{{Signature_Blocks}}")}
        for k in range(1, max_signatures + 1):
            folder = os.path.join(base, f"signatures_{k}")
            payload, sig = signature_payload(meta, k, folder)
            go(f"signatures {k}", {**plain, **sig}, payload)
            signatures.append(runs[-1])

    return {"fields": {k.strip("{}"): m for k, m in fields.items()}, "runs": runs,
            "breaking_points": breaking, "over_max_rejected": rejections, "signatures": signatures}


def field_sizes(runs: list) -> dict:
    """Per text node: its size in the reference run and the smallest it
    reached in any run."""
    ref = {n["node_id"]: n for n in runs[0]["text"]["nodes"]}
    out = {}
    for node_id, a in ref.items():
        if node_id.startswith("{{Signature_Blocks}}"):
            continue
        rows = [(n["min_size_px"], n["min_size_pt"], r["case"]) for r in runs for n in r["text"]["nodes"]
                if n["node_id"] == node_id]
        px, pt, case = min(rows)
        out[node_id.strip("{}")] = {"reference_px": a["min_size_px"], "reference_pt": a["min_size_pt"],
                                    "smallest_px": px, "smallest_pt": pt, "smallest_in": case}
    return out


def first_failure(runs: list, prefix: str) -> dict:
    for r in runs:
        if r["case"].startswith(prefix) and not r["passes"]:
            return {"case": r["case"], "problems": r["problems"]}
    return None


def main():
    parser = argparse.ArgumentParser(description="Stress test of the synthetic administrative templates (p.55)")
    parser.add_argument("--max_signatures", type=int, default=10)
    parser.add_argument("--png", action="store_true", help="also rasterize each output to output.png")
    parser.add_argument("--out", default=os.path.join(_ROOT, "results", "stress_test.json"))
    args = parser.parse_args()

    import torch
    metrics = FontMetrics()
    report = {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "settings": {
            "theme": "synthetic (no master layout); GNN on; default typography (Montserrat 700, 48 px base)",
            "fractions_of_max_characters": list(FRACTIONS),
            "text_kinds": {"words": "real words", "unbroken": f"one token with no spaces ({TOKEN}…)"},
            "fit_tolerance_px": FIT_TOL,
            "measurement": "each rendered line measured in the SVG with the bundled Montserrat's glyph "
                           "advances and ink bounds (the wider of Cairo's print face and the browser's face); "
                           "shadow copies skipped",
            "print_width_mm": {f: c["print_mm"] for f, c in FORMATS.items()},
            "small_text_below_pt": MIN_PT,
        },
        "environment": {"python": platform.python_version(), "torch": torch.__version__,
                        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
                        "gnn": os.path.basename(pipeline.DEFAULT_WEIGHTS)},
        "formats": {},
    }
    for fmt in FORMATS:
        report["formats"][fmt] = run_format(fmt, metrics, args.max_signatures, args.png)

    summary = {}
    for fmt, res in report["formats"].items():
        sig_pass = [int(r["case"].split()[-1]) for r in res["signatures"] if r["passes"]]
        summary[fmt] = {
            "runs": len(res["runs"]),
            "passed": sum(r["passes"] for r in res["runs"]),
            "reference_passes": res["runs"][0]["passes"],
            "first_failure_words": first_failure([r for r in res["runs"] if r["case"].endswith("words")],
                                                 "all at"),
            "first_failure_unbroken": first_failure([r for r in res["runs"] if r["case"].endswith("unbroken")],
                                                    "all at"),
            "fields_failing_alone_at_max": [r["case"].replace("one at max ", "") for r in res["runs"]
                                            if r["case"].startswith("one at max") and not r["passes"]],
            "breaking_points": [{k: b[k] for k in ("field", "kind", "max_characters", "shortest_failing")}
                                for b in res["breaking_points"]],
            "over_max_all_rejected": all(x["rejected"] for x in res["over_max_rejected"]),
            "signatures_largest_count_passing_from_1":
                next((k - 1 for k in range(1, len(res["signatures"]) + 2) if k not in sig_pass), None)
                if res["signatures"] else None,
            "signatures_clean_candidates": {r["case"].split()[-1]: 6 - len(r["candidates_with_fp_or_fn"])
                                            for r in res["signatures"]},
            "smallest_text_pt": min((r["text"]["min_size_pt"] for r in res["runs"]
                                     if r["text"]["min_size_pt"] is not None), default=None),
            "field_sizes": field_sizes(res["runs"]),
        }
    report["summary"] = summary
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("\nSummary:")
    print(json.dumps(summary, indent=2))
    print(f"\n-> {os.path.relpath(args.out, _ROOT)}")


if __name__ == "__main__":
    main()
