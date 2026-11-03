"""
ThemeSync — Active Canvas editor (Figure 3's central canvas)
=============================================================
The active canvas edited in place, like a design tool:

  click              select a node (the right-hand panel follows)
  drag               move it                          → on-drop
  handles            resize it (Shift keeps the ratio) → on-resize-complete
  double-click       edit its words (Enter saves)     → text-edit
  arrow keys         nudge 1 px (Shift: 10 px), sent as one on-drop
  L                  lock where it is / release       → lock-toggle
  drop a picture     a file, or an Images sidebar tile → add-picture
  Ctrl+Z, Ctrl+Shift+Z   undo, redo

The canvas is the page itself: the selected node's controls (undo, redo,
edit text, lock) live in Step 2's right-hand panel (views/orchestration.py),
which sends "edit" here as a command (request_edit) and applies the rest
through the session. The toolbar markup stays, hidden, for the keyboard
shortcuts; the live X/Y/W/H readout shows on the canvas while dragging, and
messages float at its foot.

Chapter 3, p.42: the solver runs only on discrete terminal events. While the
pointer moves, the browser only previews (the node's SVG group is translated
or scaled; nothing is sent). Releasing sends one event, which the
OrchestrationSession applies: the node becomes Hard, Cassowary re-flows the
Soft nodes around it, the state is appended to the chain, and the canvas
re-renders. Moves snap to the candidate's structural grid (Formula 3.13),
the canvas centre and the other nodes' edges (hold Alt to move freely).

Transport: a rendered SVG embeds its images as data: URIs (~1 MB). Each
image goes to the browser once per session and is cached there, so reruns
carry only the SVG's markup. The bundled Montserrat goes once too, as
@font-face rules cut down to Latin text, so the canvas shows the same
typeface as the exported PNG/PDF.
"""

import base64
import functools
import hashlib
import os
import re
import tempfile

import streamlit as st

import components as ui
from candidate_generator import solver_for, variations_for

KEY = "active_canvas"
_HERE = os.path.dirname(os.path.abspath(__file__))
_SENT = "_canvas_assets_sent"      # asset hashes this browser session already has
_FONTS_SENT = "_canvas_fonts_sent"
_ACK = "_canvas_ack"               # nonce of the last event handled
_ERROR = "_canvas_error"
_WARN = "_canvas_warning"
_COMMAND = "_canvas_command"       # a one-off command for the browser (e.g. open the text editor)

HTML = """
<div class="ts-root" tabindex="0" aria-label="Active canvas editor">
  <div class="ts-toolbar">
    <button class="ts-btn ts-iconbtn" data-act="undo" title="Undo (Ctrl+Z)" aria-label="Undo"><svg class="ts-ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M12.5 8c-2.65 0-5.05.99-6.9 2.6L2 7v9h9l-3.62-3.62c1.39-1.16 3.16-1.88 5.12-1.88 3.54 0 6.55 2.31 7.6 5.5l2.37-.78C21.08 11.03 17.15 8 12.5 8z"/></svg></button>
    <button class="ts-btn ts-iconbtn" data-act="redo" title="Redo (Ctrl+Shift+Z)" aria-label="Redo"><svg class="ts-ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M18.4 10.6C16.55 8.99 14.15 8 11.5 8c-4.65 0-8.58 3.03-9.96 7.22L3.9 16c1.05-3.19 4.05-5.5 7.6-5.5 1.95 0 3.73.72 5.12 1.88L13 16h9V7l-3.6 3.6z"/></svg></button>
    <span class="ts-divider"></span>
    <span class="ts-sel"></span>
    <span class="ts-chip"></span>
    <span class="ts-spacer"></span>
    <button class="ts-btn" data-act="edit"><svg class="ts-ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg><span class="ts-lbl">Edit text</span></button>
    <button class="ts-btn" data-act="lock"><svg class="ts-ico ico-lock" viewBox="0 0 24 24" aria-hidden="true"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z"/></svg><svg class="ts-ico ico-unlock" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 17c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm6-9h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6h1.9c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm0 12H6V10h12v10z"/></svg><span class="ts-lbl">Lock (Hard)</span></button>
  </div>
  <div class="ts-stage">
    <div class="ts-host"></div>
    <textarea class="ts-editor" spellcheck="true" aria-label="Edit text"></textarea>
    <div class="ts-count"></div>
    <span class="ts-readout"></span>
    <div class="ts-msg"></div>
    <div class="ts-busy"><span>Re-solving the layout&hellip;</span></div>
  </div>
</div>
"""


def _read(name: str) -> str:
    with open(os.path.join(_HERE, name), encoding="utf-8") as f:
        return f.read()


def _component():
    # Registered on every run: re-registering an identical definition is a
    # no-op, and it survives a runtime restart in the same process.
    return st.components.v2.component("themesync_canvas", html=HTML, css=_read("canvas_editor.css"),
                                      js=_read("canvas_editor.js"))


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

LATIN = [*range(0x20, 0x7F), *range(0xA0, 0x250), *range(0x1E00, 0x1F00), *range(0x2000, 0x2070),
         0x20AC, 0x2122]
UNICODE_RANGE = "U+0020-007E, U+00A0-024F, U+1E00-1EFF, U+2000-206F, U+20AC, U+2122"


def _subset(ttf: str, out: str) -> None:
    from fontTools import subset
    from fontTools.ttLib import TTFont

    options = subset.Options()
    options.flavor = "woff"
    options.layout_features = ["*"]
    font = TTFont(ttf)
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=LATIN)
    subsetter.subset(font)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = f"{out}.{os.getpid()}.tmp"
    font.flavor = "woff"
    font.save(tmp)
    os.replace(tmp, out)


@functools.lru_cache(maxsize=8)
def font_css(folder: str = "montserrat") -> str:
    """@font-face rules for one bundled family (assets/fonts/<folder>) as
    data: URIs. Each face is cut down to Latin text as WOFF (~75 KB instead
    of ~450 KB of TTF), made once and kept in the temp directory; without
    fontTools the full TTF is used. The canvas gets a family the first time
    the typography uses it (notes §3.53)."""
    family = next((ui.first_family(stack) for stack, f in ui.FONTS.values() if f == folder), folder)
    cache = os.path.join(tempfile.gettempdir(), "themesync_webfonts")
    rules = []
    for ttf, weight, style in ui.font_faces(folder):
        stem = os.path.splitext(os.path.basename(ttf))[0]
        path = os.path.join(cache, f"{stem}-latin2-{int(os.path.getmtime(ttf))}.woff")
        if not os.path.exists(path):
            try:
                _subset(ttf, path)
            except Exception:           # noqa: BLE001 — fall back to the full font
                path = ttf
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        subsetted = path.endswith(".woff")
        mime, fmt = ("font/woff", "woff") if subsetted else ("font/ttf", "truetype")
        rules.append(f'@font-face {{ font-family: "{family}"; font-weight: {weight}; '
                     f'font-style: {style}; font-display: swap; '
                     f'src: url(data:{mime};base64,{b64}) format("{fmt}");'
                     + (f" unicode-range: {UNICODE_RANGE};" if subsetted else "") + " }")
    return "\n".join(rules) or "/* no bundled fonts */"


# ---------------------------------------------------------------------------
# Data for the browser
# ---------------------------------------------------------------------------

_DATA_URI = re.compile(r'((?:xlink:)?href)="(data:[^"]*)"')


@functools.lru_cache(maxsize=16)
def _split(svg_path: str, mtime_ns: int) -> tuple:
    """The SVG's markup with each data: URI replaced by a ts-asset:<hash>
    token, and those assets as {hash: uri}. Read-only results (cached)."""
    with open(svg_path, encoding="utf-8") as f:
        svg = f.read()
    assets = {}

    def token(m):
        digest = hashlib.sha1(m.group(2).encode("ascii", "replace")).hexdigest()[:16]
        assets[digest] = m.group(2)
        return f'{m.group(1)}="ts-asset:{digest}"'

    return _DATA_URI.sub(token, svg), assets


def _nodes(session, friendly) -> list:
    """Every node on the current canvas, with what the editor needs."""
    text = session.canvas_text()
    limits = session.text_limits()
    schema = session.payload_meta.get("variable_schema", {})
    artwork = bool(session.style_kit.get("wordmark"))
    merged = set((session.merge or {}).get("fields", ()))
    out = []
    for n in session.chain.current["nodes"]:
        nid = n["node_id"]
        kind = n.get("structural_class", "text_node")
        base = nid.rsplit("_", 1)[0] if kind == "repeating_group" else nid
        note = None
        if nid not in text:
            note = ("filled from the CSV for each layout (mail merge)" if nid in merged
                    else "a picture you added" if nid.startswith("Added_Picture")
                    else "a motif from the master layout" if kind == "decor"
                    else "drawn with the event's title artwork from the master layout"
                    if artwork and "Event_Title" in nid
                    else "a logo" if kind == "image_node" else "")
        out.append({
            "id": nid, "label": friendly(n), "kind": kind,
            "bbox": [round(float(v), 1) for v in n["bbox"]],
            "hard": n.get("constraint_type") == "Hard",
            "text": text.get(nid), "maxLength": limits.get(nid), "note": note,
            "lockAspect": kind == "decor" or bool(schema.get(base, {}).get("lock_aspect_ratio")),
        })
    # The background layer's items (notes §3.64), under the content: the
    # master's background itself is chosen from the right-hand panel
    for key, box in getattr(session, "background_boxes", {}).items():
        if key == "bg_backdrop" or (session.styles.get(key) or {}).get("hidden"):
            continue
        out.append({"id": key, "label": BACKGROUND_LABELS[key], "kind": "background", "bbox": box,
                    "hard": False, "text": None, "maxLength": None,
                    "note": "the background layer: move, resize or fade it; the content stays put",
                    "lockAspect": key != "bg_panel"})
    return out


BACKGROUND_LABELS = {"bg_backdrop": "Background image", "bg_panel": "Panel", "bg_watermark": "Title artwork (faint)",
                     "bg_art": "Art column"}


def _grid(session, variation: dict) -> list:
    """Formula 3.13's structural grid for the canvas's candidate: its content
    area's margins, quarters and centre (x, canvas px)."""
    solver = solver_for(variation or variations_for(session.domain)[0], session.canvas_w,
                        session.canvas_h, session.structure_guided)
    left, span = solver.left_bound, solver.right_bound - solver.left_bound
    return [round(left + f * span, 1) for f in (0.0, 0.25, 0.5, 0.75, 1.0)]


def overlaps(nodes: list) -> list:
    """Pairs of content nodes whose boxes overlap: Formula 3.12's collisions,
    which the solver can't undo when both nodes are Hard."""
    content = [n for n in nodes if n.get("structural_class") != "decor"]
    pairs = []
    for i, a in enumerate(content):
        ax, ay, aw, ah = a["bbox"]
        for b in content[i + 1:]:
            bx, by, bw, bh = b["bbox"]
            if min(ax + aw, bx + bw) - max(ax, bx) > 1 and min(ay + ah, by + bh) - max(ay, by) > 1:
                pairs.append((a, b))
    return pairs


# ---------------------------------------------------------------------------
# Events from the browser
# ---------------------------------------------------------------------------

def _on_event(session, key: str, friendly) -> None:
    event = (st.session_state.get(key) or {}).get("event")
    if not isinstance(event, dict):
        return
    st.session_state[_ACK] = event.get("nonce")
    kind, node_id = event.get("type"), event.get("node_id")
    if kind == "need-assets":           # the browser lost its cache: send everything again
        st.session_state.pop(_SENT, None)
        st.session_state.pop(_FONTS_SENT, None)
        return
    if kind == "select":
        if node_id:
            st.session_state["sel_node"] = node_id
        return
    try:
        if node_id in session.BACKGROUND_ITEMS:          # the background layer (notes §3.64)
            if kind in ("on-drop", "on-resize-complete"):
                new = session.set_style(node_id, {"box": [float(v) for v in event["bbox"]]})
            elif kind == "remove":
                new = session.set_style(node_id, {"hidden": True})
                st.session_state.pop("sel_node", None)
                node_id = None
            elif kind == "lock-toggle":
                raise ValueError("The background layer isn't placed by the solver: move it freely.")
            else:
                return
        elif kind in ("on-drop", "on-resize-complete"):
            new = session.apply_event(kind, node_id, bbox=[float(v) for v in event["bbox"]])
        elif kind == "lock-toggle":
            new = session.apply_event(kind, node_id, hard=bool(event.get("hard")))
        elif kind == "text-edit":
            new = session.edit_text(node_id, str(event.get("text", "")))
        elif kind == "remove":
            new = session.remove_element(node_id)
            st.session_state.pop("sel_node", None)
            node_id = None
        elif kind == "add-picture":
            # a picture file dropped on the canvas, or one of the Images
            # sidebar's tiles (dropped, or clicked: no position)
            path = (ui.asset_path(str(event["asset"])) if event.get("asset")
                    else ui.save_data_uri(str(event.get("data", "")), str(event.get("name", ""))))
            if not path or not os.path.exists(path):
                raise ValueError("That picture is no longer available; upload it again.")
            at = event.get("at")
            new = session.add_element("picture", path, at=(float(at[0]), float(at[1])) if at else None)
            node_id = new["event"]["node_id"]
        elif kind == "undo":
            new = session.undo()
        elif kind == "redo":
            new = session.redo()
        else:
            return
    except (KeyError, ValueError, TypeError) as e:
        st.session_state[_ERROR] = str(e.args[0]) if e.args else str(e)
        return
    if node_id:
        st.session_state["sel_node"] = node_id
    st.session_state["flash"] = f"{new['state_id']}: {new['event'].get('summary') or new['label']}"
    clashes = overlaps(new["nodes"])
    if clashes:
        names = "; ".join(f"{friendly(a)} × {friendly(b)}" for a, b in clashes[:2])
        st.session_state[_WARN] = (f"Overlap: {names}. Hard nodes stay exactly where they are put, so the "
                                   "solver can't separate them (collision penalty, Formula 3.12) — move one, "
                                   "or release it with L.")


def request_edit(node_id: str) -> None:
    """Asks the canvas to open its text editor on `node_id` on the next run
    (the right-hand panel's Edit text)."""
    st.session_state[_COMMAND] = {"type": "edit", "node_id": node_id, "nonce": os.urandom(6).hex()}


def active_canvas(session, friendly, key: str = KEY) -> None:
    """Draws the editable active canvas of `session`. friendly(node) → the
    node's display name."""
    state = session.chain.current
    svg_path = session.rendered_path
    mtime_ns = os.stat(svg_path).st_mtime_ns
    markup, assets = _split(svg_path, mtime_ns)
    sent = st.session_state.setdefault(_SENT, set())
    new_assets = {h: uri for h, uri in assets.items() if h not in sent}
    sent.update(new_assets)
    families = {ui.font_folder(session.typography.get("family")) or "montserrat"}
    families |= {ui.font_folder(s["font"]) for s in session.styles.values() if s.get("font")} - {None}
    fonts_sent = st.session_state.setdefault(_FONTS_SENT, set())
    fonts = {f: font_css(f) for f in sorted(families - fonts_sent)} or None
    fonts_sent |= families
    data = {
        "version": f"{state['state_id']}:{mtime_ns}",
        "svg": markup, "assets": new_assets, "fonts": fonts, "fontFamilies": sorted(families),
        "width": session.canvas_w, "height": session.canvas_h,
        "nodes": _nodes(session, friendly),
        "selected": st.session_state.get("sel_node"),
        "grid": _grid(session, state.get("variation")),
        "canUndo": session.can_undo, "canRedo": session.can_redo,
        "ack": st.session_state.get(_ACK),
        "error": st.session_state.pop(_ERROR, None),
        "warning": st.session_state.pop(_WARN, None),
        "command": st.session_state.pop(_COMMAND, None),
    }
    _component()(key=key, data=data, on_event_change=lambda: _on_event(session, key, friendly))
