"""
ThemeSync — Active Orchestration & Heuristic Scoring Workspace (Figure 3)
==========================================================================
Chapter 3, pp. 53-54: the central canvas shows the design adapted to the
target format, with the Constraint Editor's controls, the JSON state
timeline and the Recommendation Engine around it. Laid out like a design
tool (the user's request, 2026-10-09, notes §3.38), on one screen:

  Centre: the active canvas, edited in place (canvas_editor.py): select,
    drag, resize, double-click to retype, arrow-key nudges, lock/release,
    undo/redo.
  Bottom: the Recommendation Engine as a strip of small thumbnails, like a
    slide sorter, in rank order of the Heuristic Fitness Function (Formula
    3.11). Clicking one opens its details (layout type, the four penalties,
    C_total) and "Use this design".
  Right: the selected element (undo, redo, its name and Soft/Hard status
    with X/Y/W/H, Edit text, Lock/Release, Formula 3.10), the
    schema-validated typography, and, collapsed, the canvas details (state,
    size, Formula 3.11's terms, the master layout, the shortcuts).
  Top bar: Timeline opens the serialized JSON state timeline of the
    Bi-directional State Machine (Formula 3.9), from which any earlier
    canvas can be restored without losing the history.

Every edit is one discrete, terminal event (a drop, a finished resize, a
text edit, a nudge, a lock toggle, undo/redo): the session re-solves the
layout with the adjusted node as a Hard constraint and appends a state;
nothing earlier in the chain changes.

This is Step 2 of the dashboard's workflow: "Evaluate" moves on to Step 3's
report, and "Step 1" (confirmed) closes the layout.
"""

import html
import json
import os
import sys

import streamlit as st
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import components as ui                                       # noqa: E402
import canvas_editor                                          # noqa: E402
import mail_merge                                             # noqa: E402
import rasterize                                              # noqa: E402
from schema_validation import FONT_WEIGHTS                    # noqa: E402

WEIGHT_NAMES = {100: "Thin", 200: "Extra Light", 300: "Light", 400: "Regular", 500: "Medium",
                600: "Semibold", 700: "Bold", 800: "Extra Bold", 900: "Black"}
SHORTCUTS = ("Drag to move · handles resize (Shift keeps proportions) · double-click text to edit · "
             "arrows nudge 1 px (Shift: 10 px) · L locks / releases · Tab cycles · Ctrl+Z / Ctrl+Shift+Z "
             "undo / redo · hold Alt to move without snapping")
PENALTIES = (("Collision", "P_collision", "3.12"), ("Alignment", "P_align", "3.13"),
             ("Whitespace", "P_space", "3.14"), ("Legibility", "P_legibility", "3.15"))


def _friendly(node: dict) -> str:
    if node.get("structural_class") == "decor":
        return f"Motif {int(node['node_id'].rsplit('_', 1)[1]) + 1} ({node.get('slot', 'decor')})"
    return node["node_id"].replace("{", "").replace("}", "").replace("_", " ").strip()


def _pills(m: dict) -> str:
    """Formula 3.11's total and its four penalties, as status pills."""
    return (f'<span class="ts-pill total">C_total {m["Total_Cost"]:.4f}</span>'
            + "".join(f'<span class="ts-pill">{name.lower()} {m[key]:.4f}</span>' for name, key, _ in PENALTIES))


def _section(title: str) -> None:
    st.markdown(f'<div class="ts-section">{title}</div>', unsafe_allow_html=True)


def _flash(new: dict, note: str = "") -> None:
    st.session_state["flash"] = f"{new['state_id']}: {new['event'].get('summary') or new['label']}{note}"
    st.rerun()


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------

@st.dialog("State Timeline (JSON Sync)", width="large")
def _timeline(session) -> None:
    st.caption("The Bi-directional State Machine's chain (Formula 3.9): every terminal event appends a "
               "state. Restoring an earlier canvas appends it again, so no state is ever overwritten.")
    states = session.chain.states
    with st.container(height=min(70 + 46 * len(states), 440), key="ts_timeline"):
        for i, s in reversed(list(enumerate(states))):
            c_total = (s.get("fitness") or {}).get("Total_Cost")
            now = i == len(states) - 1
            row = st.columns([7, 1], vertical_alignment="center")
            row[0].markdown(f'<div class="ts-row{" now" if now else ""}"><code>{s["state_id"]}</code>'
                            f'<span>{html.escape(s["label"])}'
                            + (f" · C={c_total:.4f}" if c_total is not None else "")
                            + ('  <span class="ts-badge on">current</span>' if now else "")
                            + "</span></div>", unsafe_allow_html=True)
            if not now and row[1].button("", icon=":material/history:", key=f"restore_{i}", width="stretch",
                                         help=f"Restore {s['state_id']} as a new state (history kept)"):
                new = session.restore_state(i)
                _flash(new, f" (restored {s['state_id']}; history kept)")
    state = session.chain.current
    left, right = st.columns([1, 1.4])
    left.download_button("Download the state chain", data=session.chain.to_json(), icon=":material/data_object:",
                         file_name=os.path.basename(session.chain_path), mime="application/json",
                         width="stretch")
    with right.expander("Latest event (JSON)", icon=":material/code:"):
        st.json({"state_id": state["state_id"], "event": state["event"],
                 "hard_nodes": state["hard_nodes"], "fitness": state.get("fitness")})


@st.dialog("Recommendation", width="large")
def _candidate(session, cand: dict, rank: int, png: str, active: bool) -> None:
    cid = cand["candidate_id"]
    left, right = st.columns([1.35, 1], gap="medium")
    left.image(png, width="stretch")
    with right:
        badges = f'<span class="ts-badge">#{rank} of {len(session.candidates)}</span>'
        if cand.get("chosen_because"):
            badges += '<span class="ts-badge rec">Recommended</span>'
        if active:
            badges += '<span class="ts-badge on">On the canvas</span>'
        st.markdown(f"### {cid.replace('_', ' ')}\n{badges}", unsafe_allow_html=True)
        st.caption(cand["label"])
        m = cand["metrics"]
        st.markdown(f'<span class="ts-pill total">C_total {cand["c_total"]:.4f}</span>', unsafe_allow_html=True)
        st.markdown("\n".join(f"- {name} (Formula {f}): **{m[key]:.4f}**" for name, key, f in PENALTIES))
        st.caption("Ranked by the Heuristic Fitness Function (Formula 3.11); lower is better."
                   + (f" Recommended: {cand['chosen_because']}." if cand.get("chosen_because") else ""))
        if st.button("In use" if active else "Use this design", key=f"use_{cid}", disabled=active,
                     icon=":material/check:" if active else ":material/swap_horiz:", type="primary",
                     width="stretch"):
            new = session.select_candidate(cid)
            _flash(new, f" ({cid} is now the active canvas)")


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

actions = ui.enter_step(2, ui.design_name(st.session_state.get("orch")))   # no layout: back to Step 1
def _mail_merge_download(session, state: dict) -> None:
    """The Download menu's mail merge: the current layout once per CSV row
    (mail_merge.py), as PNG or PDF files in a ZIP, built on request."""
    merge = session.merge
    if not merge or not merge.get("rows"):
        return
    st.divider()
    st.caption(f"Mail merge: {len(merge['rows'])} layouts from {merge['source']}, with "
               f"{', '.join(merge['labels'].values())} filled in from each row.")
    fmt = st.segmented_control("Format", ["PNG", "PDF"], default="PNG", key="merge_fmt",
                               label_visibility="collapsed") or "PNG"
    stamp = (id(session), state["state_id"], fmt, json.dumps(session.typography, sort_keys=True))
    built = st.session_state.get("merge_zip")
    if not (built and built[0] == stamp and os.path.exists(built[1])):
        if not st.button(f"Build {len(merge['rows'])} layouts ({fmt})", icon=":material/folder_zip:",
                         width="stretch", key="merge_build"):
            return
        bar = st.progress(0.0, text="Rendering…")
        path = mail_merge.zip_layouts(session, fmt.lower(),
                                      progress=lambda done, total: bar.progress(done / total,
                                                                                text=f"{done} of {total}"))
        built = st.session_state["merge_zip"] = (stamp, path)
    st.download_button(f"Download the ZIP ({os.path.getsize(built[1]) / 1e6:.1f} MB)", data=ui.reader(built[1]),
                       file_name=os.path.basename(built[1]), mime="application/zip", type="primary",
                       icon=":material/download:", width="stretch")


session = st.session_state["orch"]
state = session.chain.current
nodes = state["nodes"]
node_by_id = {n["node_id"]: n for n in nodes}
svg = session.rendered_path

# The top bar's actions: the timeline, back (confirmed), download, evaluate.
with actions, st.container(key="s2_actions"):
    tl_col, back_col, down_col, next_col = st.columns([0.9, 0.85, 1.0, 1.25], gap="small")
    if tl_col.button("Timeline", icon=":material/timeline:", width="stretch",
                     help="The State Timeline (JSON Sync): every state of this layout, any of which can be "
                          "restored."):
        _timeline(session)
    with back_col:
        ui.back_to_step_one("back_from_2")
    with down_col.popover("Download", icon=":material/download:", width="stretch"):
        st.caption("The active canvas, rendered with the bundled fonts.")
        st.download_button("SVG", data=ui.reader(svg), file_name=os.path.basename(svg), mime="image/svg+xml",
                           icon=":material/draw:", width="stretch")
        st.download_button("PNG (2×)", data=lambda: open(ui.png_of(svg, 2.0), "rb").read(),
                           file_name=os.path.basename(svg).replace(".svg", ".png"), mime="image/png",
                           icon=":material/image:", width="stretch")
        st.download_button("PDF", data=lambda: open(rasterize.svg_to_pdf(svg), "rb").read(),
                           file_name=os.path.basename(svg).replace(".svg", ".pdf"), mime="application/pdf",
                           icon=":material/picture_as_pdf:", width="stretch")
        _mail_merge_download(session, state)
    if next_col.button("Evaluate", icon=":material/arrow_forward:", type="primary", width="stretch",
                       help="Step 3: the layout's report against Chapter 3's evaluation metrics."):
        ui.go_to_step(3)

# Event outcomes appear as toasts: a message in the page would shift the
# canvas on the next rerun, and Streamlit would remount it (losing focus).
if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"), icon=":material/check_circle:")

canvas_col, panel_col = st.columns([2.55, 1], gap="medium")

# ---------------------------------------------------------------------------
# LEFT — the active canvas, and the Recommendation Engine's strip beneath it
# ---------------------------------------------------------------------------
with canvas_col:
    with st.container(key="ts_workspace"):
        canvas_editor.active_canvas(session, _friendly)

    # The thumbnails are drawn with the canvas's current words and typography,
    # so a text edit, undo or restore that changes either redraws them.
    thumbs_key = (id(session), json.dumps(session.typography, sort_keys=True),
                  json.dumps(session.content(), sort_keys=True))
    cached = st.session_state.get("orch_thumbs")
    if not cached or cached["key"] != thumbs_key or "uris" not in cached:
        with st.spinner("Rendering the candidates..."):
            items = {c["candidate_id"]: ui.png_of(svg_c, 0.35) for c, svg_c in session.render_candidates()}
        uris = {}
        for cid, png in items.items():
            with Image.open(png) as im:
                im = im.convert("RGB")
                im.thumbnail((360, 180))
                uris[cid] = ui.data_uri(im, "JPEG")
        cached = {"key": thumbs_key, "items": items, "uris": uris}
        st.session_state["orch_thumbs"] = cached

    with st.container(horizontal=True, key="reco_strip", vertical_alignment="center", gap="small"):
        st.markdown('<div class="ts-strip-label">Recommendations<small>ranked by Formula 3.11 · '
                    "click for details</small></div>", unsafe_allow_html=True)
        for rank, cand in enumerate(session.candidates, start=1):
            cid = cand["candidate_id"]
            on_canvas = state.get("candidate_id") == cid
            in_use = on_canvas and state["event"].get("type") == "candidate"
            rec = " rec" if cand.get("chosen_because") else ""
            with st.container(key=f"cand_{'on_' if on_canvas else ''}{cid}", width="content", gap=None):
                st.markdown(f'<div class="ts-cand{rec}"><img src="{cached["uris"][cid]}" alt=""><b>{rank}</b></div>',
                            unsafe_allow_html=True)
                if st.button(f"{cid.replace('_', ' ')}: details", key=f"candbtn_{cid}",
                             help=f"#{rank} · {cid.replace('_', ' ')} · C_total {cand['c_total']:.4f}"):
                    _candidate(session, cand, rank, cached["items"][cid], in_use)

# ---------------------------------------------------------------------------
# RIGHT — the selected element, typography, and (collapsed) canvas details
# ---------------------------------------------------------------------------
with panel_col, st.container(key="ts_panel"):
    _section("Selected element")
    sel = st.session_state.get("sel_node")
    node = node_by_id.get(sel)
    with st.container(horizontal=True, key="sel_head", vertical_alignment="center", gap="small"):
        if st.button("", icon=":material/undo:", key="panel_undo", disabled=not session.can_undo,
                     help="Undo (Ctrl+Z)"):
            _flash(session.undo())
        if st.button("", icon=":material/redo:", key="panel_redo", disabled=not session.can_redo,
                     help="Redo (Ctrl+Shift+Z)"):
            _flash(session.redo())
        if node:
            hard = node.get("constraint_type") == "Hard"
            st.markdown(f'<div class="ts-selname"><b>{html.escape(_friendly(node))}</b>'
                        f'<span class="ts-chip {"hard" if hard else "soft"}">'
                        f'{"Hard · manual override" if hard else "Soft · algorithmic"}</span></div>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<div class="ts-selname"><span class="ts-muted">Click an element on the canvas to '
                        "select it.</span></div>", unsafe_allow_html=True)
    if node:
        x0, y0, w0, h0 = node["bbox"]
        st.markdown('<div class="ts-status">' + "".join(
            f'<span class="ts-pill">{k} {round(v)}</span>' for k, v in (("X", x0), ("Y", y0), ("W", w0), ("H", h0)))
            + '<span class="ts-unit">px</span></div>', unsafe_allow_html=True)
        has_text = node["node_id"] in session.canvas_text()
        merged = node["node_id"] in (session.merge or {}).get("fields", ())
        e_col, l_col = st.columns(2, gap="small")
        if e_col.button("Edit text", icon=":material/edit:", width="stretch", disabled=not has_text,
                        help="Edit its words on the canvas (or double-click it)" if has_text
                        else "Filled from the CSV for each layout (mail merge)" if merged
                        else "This element has no text to edit"):
            canvas_editor.request_edit(node["node_id"])
            st.rerun()
        if l_col.button("Release (Soft)" if hard else "Lock (Hard)", width="stretch",
                        icon=":material/lock_open:" if hard else ":material/lock:",
                        help="Hand it back to the algorithm (L)" if hard else "Pin it exactly where it is (L)"):
            _flash(session.apply_event("lock-toggle", node["node_id"], hard=not hard))
    st.caption("A moved or resized element becomes Hard: the solver keeps it exactly there and re-flows "
               "the Soft ones around it (Formula 3.10).")

    _section("Typography")
    t = session.typography
    family = t["family"].split(",")[0].strip("'\" ")
    st.markdown(f"**{family}** · weight {t['weight']} · {t['base_size']:g} px base")
    with st.expander("Administrative typography (schema-validated)", icon=":material/text_fields:"):
        fam = ui.font_picker(f"fam_{state['state_id']}", "Font", t["family"])
        wt = st.selectbox("Font weight", FONT_WEIGHTS, index=FONT_WEIGHTS.index(int(t["weight"])),
                          format_func=lambda v: f"{v} — {WEIGHT_NAMES[v]}", key=f"wt_{state['state_id']}")
        bs = st.number_input("Base size (px)", value=float(t["base_size"]), step=1.0,
                             key=f"bs_{state['state_id']}")
        if st.button("Validate and apply typography"):
            try:
                new = session.set_typography({"family": fam, "weight": int(wt), "base_size": float(bs)})
            except ValueError as e:
                st.error(str(e))
            else:
                st.session_state.pop("orch_thumbs", None)
                _flash(new, " (schema validation passed)")

    with st.expander("Canvas details", icon=":material/info:"):
        fit = state.get("fitness") or {}
        st.markdown(f'<div class="ts-status"><span class="ts-pill"><b>{state["state_id"]}</b> · '
                    f'{html.escape(state["label"])}</span><span class="ts-pill">{session.canvas_w}×'
                    f'{session.canvas_h}px</span>{_pills(fit) if fit else ""}</div>', unsafe_allow_html=True)
        st.caption(SHORTCUTS)
        master = st.session_state.get("orch_master")
        if master and os.path.exists(master):
            with st.popover("Master layout", icon=":material/image:", width="stretch",
                            help="The master layout this design takes its theme from."):
                st.image(master, width="stretch")
