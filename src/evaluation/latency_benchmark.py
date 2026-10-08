"""
ThemeSync — Latency of the designer's edits (p.62; revision item M26)
======================================================================
p.62 of Manu 0910.1: algorithmic latency "was measured in milliseconds to
mathematically demonstrate that constraint recalculations and state
synchronizations executed within the strict time thresholds—specifically
the 0.1-second limit for perceived instantaneous response and the 1.0-second
limit for uninterrupted task flow" (Nielsen).

This script opens real editing sessions, the way the dashboard opens them,
and plays a fixed, seeded script of terminal events on each (p.41's
event-driven post-interaction solver: only finished actions count). It
times every event two ways:

  solver      the Cassowary re-solve alone (constraint recalculation), as
              the session records it in each move/resize/lock event
  full edit   the whole state synchronization, as the session records it
              (session.event_ms): re-solve, re-score (Formula 3.11),
              re-render the SVG, append the state and save the JSON chain

and breaks the full edit into its parts (solve, score, render, save). It
does not include Streamlit's rerun or the browser repainting the canvas.

Sessions: the 16 Phase 4 posters x 2 formats, GNN on, opened as the packet
opened them (the manifest's content, logos and overrides), plus the
synthetic theme on both formats. Everything is written under
data/rendered/latency/ (git-ignored); nothing in data/phase4/, data/raw/
or the pipeline changes.

Events per session (40, shuffled with a per-session seed):
  14 moves (on-drop)          a random element to a random spot on the canvas
   8 resizes                  a random element scaled by 0.8-1.2
   6 lock toggles             lock an element where it is, or release it
   4 text edits               one character added to, or removed from, a field
   2 typography changes       the base size up or down by 2 px
   2 undo, 2 redo             as Ctrl+Z / Ctrl+Shift+Z
   1 candidate                a Recommendation Engine thumbnail clicked
   1 restore                  an earlier state from the State Timeline

Usage:
  python src/evaluation/latency_benchmark.py
  python src/evaluation/latency_benchmark.py --limit 4 --events 20

Writes results/latency_benchmark.json.
"""

import argparse
import contextlib
import datetime
import functools
import io
import json
import os
import platform
import random
import statistics
import sys
import time

_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_EVAL_DIR)
_ROOT = os.path.dirname(_SRC)
for _p in (_EVAL_DIR, _SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import phase4_packet as p4                 # noqa: E402 — imports rasterize (fonts) first
import pipeline                            # noqa: E402

RUNS_DIR = os.path.join(_ROOT, "data", "rendered", "latency")
INSTANT_MS, FLOW_MS = 100.0, 1000.0        # Nielsen's 0.1 s and 1.0 s
SCRIPT = (["on-drop"] * 14 + ["on-resize-complete"] * 8 + ["lock-toggle"] * 6 + ["text-edit"] * 4
          + ["typography"] * 2 + ["undo"] * 2 + ["redo"] * 2 + ["candidate"] + ["restore"])
SYNTHETIC = {"certificate": os.path.join(_ROOT, "data", "raw", "sample_content.json"),
             "event_id": os.path.join(_ROOT, "data", "raw", "sample_content_id.json")}


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def sessions(limit: int = None) -> list:
    """(label, format, kwargs for OrchestrationSession) per session."""
    rows = sorted([r for r in p4.read_manifest(p4.POSTERS_DIR) if r.get("poster_file")],
                  key=lambda r: r["poster_file"])[:limit]
    out = []
    for i, row in enumerate(rows):
        stem = os.path.splitext(row["poster_file"])[0]
        content = p4.content_for(row, i)
        for fmt, payload in p4.FORMATS.items():
            out.append((stem, fmt, dict(
                payload_path=payload, template_image=os.path.join(p4.POSTERS_DIR, row["poster_file"]),
                content_data=content[fmt], use_gnn=True, output_dir=os.path.join(RUNS_DIR, stem, fmt),
                logo_images=p4.logo_paths(row, p4.POSTERS_DIR), use_wordmark=p4.use_title_artwork(row),
                motif_paths=None if p4.use_motifs(row) else [])))
    for fmt, payload in p4.FORMATS.items():
        with open(SYNTHETIC[fmt], encoding="utf-8") as f:
            content = json.load(f)
        out.append(("synthetic", fmt, dict(payload_path=payload, content_data=content, use_gnn=True,
                                           output_dir=os.path.join(RUNS_DIR, "synthetic", fmt))))
    return out


def _timer(parts: dict, name: str, fn):
    """Wraps a session method so each call adds its time to parts[name]."""
    @functools.wraps(fn)
    def timed(*args, **kwargs):
        t0 = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            parts[name] = parts.get(name, 0.0) + (time.perf_counter() - t0) * 1000
    return timed


# ---------------------------------------------------------------------------
# The events
# ---------------------------------------------------------------------------

def _elements(session) -> list:
    return [n for n in session.chain.current["nodes"] if n.get("structural_class") != "decor"]


def _clamp_box(x, y, w, h, cw, ch) -> list:
    w, h = min(w, cw), min(h, ch)
    return [min(max(0.0, x), cw - w), min(max(0.0, y), ch - h), w, h]


def play(session, kind: str, rng: random.Random) -> tuple:
    """Performs one event; returns (kind actually played, new state)."""
    cw, ch = session.canvas_w, session.canvas_h
    if kind == "undo" and not session.can_undo:
        kind = "on-drop"
    if kind == "redo" and not session.can_redo:
        kind = "on-drop"
    if kind == "on-drop":
        node = rng.choice(_elements(session))
        _, _, w, h = node["bbox"]
        box = _clamp_box(rng.uniform(0, cw - w), rng.uniform(0, ch - h), w, h, cw, ch)
        return kind, session.apply_event("on-drop", node["node_id"], box)
    if kind == "on-resize-complete":
        node = rng.choice(_elements(session))
        x, y, w, h = node["bbox"]
        s = rng.uniform(0.8, 1.2)
        box = _clamp_box(x, y, max(8.0, w * s), max(8.0, h * s), cw, ch)
        return kind, session.apply_event("on-resize-complete", node["node_id"], box)
    if kind == "lock-toggle":
        node = rng.choice(_elements(session))
        return kind, session.apply_event("lock-toggle", node["node_id"],
                                         hard=node.get("constraint_type") != "Hard")
    if kind == "text-edit":
        texts, limits = session.canvas_text(), session.text_limits()
        key = rng.choice(sorted(texts))
        text = texts[key]
        new = text + "!" if len(text) < limits.get(key, 10 ** 6) else text[:-1]
        return kind, session.edit_text(key, new)
    if kind == "typography":
        size = session.typography["base_size"]
        return kind, session.set_typography({"base_size": size + (2 if rng.random() < 0.5 else -2)})
    if kind == "undo":
        return kind, session.undo()
    if kind == "redo":
        return kind, session.redo()
    if kind == "candidate":
        return kind, session.select_candidate(rng.choice(session.candidates)["candidate_id"])
    if kind == "restore":
        return kind, session.restore_state(rng.randrange(len(session.chain.states)))
    raise ValueError(kind)


def run_session(label: str, fmt: str, kwargs: dict, n_events: int) -> dict:
    session = pipeline.OrchestrationSession(**kwargs)
    t0 = time.perf_counter()
    with contextlib.redirect_stdout(io.StringIO()):
        session.run()
    open_ms = (time.perf_counter() - t0) * 1000

    parts = {}
    session.render = _timer(parts, "render", session.render)
    session.chain.save = _timer(parts, "save", session.chain.save)
    session._fitness = _timer(parts, "score", session._fitness)
    session._resolve = _timer(parts, "solve_and_motifs", session._resolve)

    rng = random.Random(f"{label}/{fmt}")
    script = SCRIPT * (n_events // len(SCRIPT) + 1)
    rng.shuffle(script)
    script = script[:n_events]
    events = []
    for i, wanted in enumerate(script):
        parts.clear()
        with contextlib.redirect_stdout(io.StringIO()):
            kind, state = play(session, wanted, rng)
        recorded = (state.get("event") or {}).get("latency_ms") or {}
        events.append({
            "i": i, "type": kind, "state": state["state_id"],
            "full_ms": session.event_ms[state["state_id"]],
            "solver_ms": recorded.get("solve"),
            "parts_ms": {k: round(v, 2) for k, v in parts.items()},
            "chain_states": len(session.chain.states),
        })
    return {"session": label, "format": fmt, "canvas": [session.canvas_w, session.canvas_h],
            "open_ms": round(open_ms, 1), "events": events}


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

def pct(values: list, q: float) -> float:
    """The q-th percentile (nearest rank)."""
    v = sorted(values)
    return v[min(len(v) - 1, max(0, int(round(q / 100.0 * len(v) + 0.5)) - 1))]


def stats(values: list) -> dict:
    values = [v for v in values if v is not None]
    if not values:
        return {"n": 0}
    return {"n": len(values), "median_ms": round(statistics.median(values), 2),
            "p95_ms": round(pct(values, 95), 2), "max_ms": round(max(values), 2),
            "within_0.1s": round(sum(v <= INSTANT_MS for v in values) / len(values), 4),
            "within_1.0s": round(sum(v <= FLOW_MS for v in values) / len(values), 4)}


def summarise(runs: list) -> dict:
    events = [e for r in runs for e in r["events"]]
    out = {"sessions": len(runs), "events": len(events),
           "solver": stats([e["solver_ms"] for e in events]),
           "full_edit": stats([e["full_ms"] for e in events]),
           "full_edit_by_type": {}, "full_edit_by_format": {}, "parts_median_ms": {},
           "opening_a_layout": stats([r["open_ms"] for r in runs])}
    for kind in dict.fromkeys(e["type"] for e in events):
        out["full_edit_by_type"][kind] = stats([e["full_ms"] for e in events if e["type"] == kind])
    for fmt in dict.fromkeys(r["format"] for r in runs):
        sel = [e for r in runs if r["format"] == fmt for e in r["events"]]
        out["full_edit_by_format"][fmt] = {"solver": stats([e["solver_ms"] for e in sel]),
                                           "full_edit": stats([e["full_ms"] for e in sel])}
    for part in ("solve_and_motifs", "score", "render", "save"):
        vals = [e["parts_ms"].get(part) for e in events if part in e["parts_ms"]]
        out["parts_median_ms"][part] = round(statistics.median(vals), 2) if vals else None
    # The chain is saved whole on every edit: does a longer chain slow it?
    first = [e["full_ms"] for r in runs for e in r["events"][:10]]
    last = [e["full_ms"] for r in runs for e in r["events"][-10:]]
    out["chain_growth"] = {"median_first_10_ms": round(statistics.median(first), 2),
                           "median_last_10_ms": round(statistics.median(last), 2)}
    synthetic = [r for r in runs if r["session"] == "synthetic"]
    if synthetic:
        out["synthetic_theme_full_edit"] = stats([e["full_ms"] for r in synthetic for e in r["events"]])
    return out


def main():
    parser = argparse.ArgumentParser(description="Latency of the designer's edits (p.62)")
    parser.add_argument("--limit", type=int, default=None, help="only the first N Phase 4 posters")
    parser.add_argument("--events", type=int, default=len(SCRIPT), help="events per session")
    parser.add_argument("--out", default=os.path.join(_ROOT, "results", "latency_benchmark.json"))
    args = parser.parse_args()

    import torch
    runs = []
    todo = sessions(args.limit)
    for k, (label, fmt, kwargs) in enumerate(todo, start=1):
        r = run_session(label, fmt, kwargs, args.events)
        runs.append(r)
        full = [e["full_ms"] for e in r["events"]]
        solve = [e["solver_ms"] for e in r["events"] if e["solver_ms"] is not None]
        print(f"  [{k:>2}/{len(todo)}] {label[:24]:<24} {fmt:<11} open {r['open_ms']:>7.0f} ms | "
              f"edit median {statistics.median(full):6.1f} ms, max {max(full):6.1f} | "
              f"solver median {statistics.median(solve):5.2f} ms", flush=True)

    report = {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "settings": {
            "sessions": "16 Phase 4 posters x 2 formats (GNN, opened as the packet opened them) "
                        "+ the synthetic theme x 2 formats",
            "events_per_session": args.events,
            "script": {k: SCRIPT.count(k) for k in dict.fromkeys(SCRIPT)},
            "solver": "the Cassowary re-solve (latency_ms.solve of each move/resize/lock event)",
            "full_edit": "session.event_ms: re-solve, re-score, re-render the SVG, append and save "
                         "the state chain; excludes Streamlit's rerun and the browser's repaint",
            "thresholds_ms": {"instantaneous": INSTANT_MS, "uninterrupted_flow": FLOW_MS},
            "percentile": "nearest rank",
        },
        "environment": {"python": platform.python_version(), "torch": torch.__version__,
                        "os": platform.platform(), "cpu": platform.processor(),
                        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"},
        "summary": summarise(runs),
        "runs": runs,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("\nSummary:")
    print(json.dumps({k: v for k, v in report["summary"].items() if k != "full_edit_by_type"}, indent=2))
    print(json.dumps(report["summary"]["full_edit_by_type"], indent=1))
    print(f"\n-> {os.path.relpath(args.out, _ROOT)}")


if __name__ == "__main__":
    main()
