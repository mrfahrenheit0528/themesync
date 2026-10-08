"""
ThemeSync — Active Orchestration & Heuristic Scoring Workspace (Figure 3)
==========================================================================
Chapter 3, pp. 53-54. The central canvas shows the design adapted to the
target format; the right-hand interface has two tabs. It is laid out like
a design tool such as Canva, in ThemeSync's own colours: a navy top bar
with the page's actions, the page on a grey workspace with a status bar,
and a white side panel.

  Constraint Editor
    The selected node's spatial parameters (X, Y, W, H) and schema-validated
    typography; whether it is an algorithmic "Soft" constraint or a
    manually locked "Hard" one (Formula 3.10); and the serialized JSON state
    timeline of the Bi-directional State Machine (Formula 3.9), from which
    any earlier canvas can be restored without losing the history.
  Recommendation Engine
    The parallel layout variations, ranked by the Heuristic Fitness
    Function (Formula 3.11) with their collision, alignment, whitespace and
    legibility penalties; any of them can be made the active canvas.

The canvas itself is editable in place (canvas_editor.py): select, drag,
resize, double-click to retype, arrow-key nudges, lock/release, undo/redo.

Every edit is one discrete, terminal event (a drop, a finished resize, a
text edit, Apply, a nudge, a lock toggle): the session re-solves the layout
with the adjusted node as a Hard constraint and appends a state; nothing
earlier in the chain changes.

This is Step 2 of the dashboard's workflow: "Evaluate this layout" moves
on to Step 3's report, and "Back to Step 1" (confirmed) closes the layout.
"""

import html
import json
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import components as ui                                       # noqa: E402
import canvas_editor                                          # noqa: E402
import rasterize                                              # noqa: E402
from schema_validation import FONT_WEIGHTS                    # noqa: E402

NUDGE = 10.0
WEIGHT_NAMES = {100: "Thin", 200: "Extra Light", 300: "Light", 400: "Regular", 500: "Medium",
                600: "Semibold", 700: "Bold", 800: "Extra Bold", 900: "Black"}


def _friendly(node: dict) -> str:
    if node.get("structural_class") == "decor":
        return f"Motif {int(node['node_id'].rsplit('_', 1)[1]) + 1} ({node.get('slot', 'decor')})"
    return node["node_id"].replace("{", "").replace("}", "").replace("_", " ").strip()


def _metrics_line(m: dict) -> str:
    return (f"C_total **{m['Total_Cost']:.4f}** · collision {m['P_collision']:.4f} · "
            f"alignment {m['P_align']:.4f} · whitespace {m['P_space']:.4f} · "
            f"legibility {m['P_legibility']:.4f}")


def _pills(m: dict) -> str:
    """Formula 3.11's total and its four penalties, as status-bar pills."""
    return (f'<span class="ts-pill total">C_total {m["Total_Cost"]:.4f}</span>'
            + "".join(f'<span class="ts-pill">{name} {m[key]:.4f}</span>'
                      for name, key in (("collision", "P_collision"), ("alignment", "P_align"),
                                        ("whitespace", "P_space"), ("legibility", "P_legibility"))))


def _section(title: str) -> None:
    st.markdown(f'<div class="ts-section">{title}</div>', unsafe_allow_html=True)


actions = ui.enter_step(2, ui.design_name(st.session_state.get("orch")))   # no layout: back to Step 1
session = st.session_state["orch"]
state = session.chain.current
nodes = state["nodes"]
node_by_id = {n["node_id"]: n for n in nodes}
state_key = state["state_id"]
svg = session.rendered_path

# The top bar's actions: back (confirmed), download, evaluate.
with actions:
    back_col, down_col, next_col = st.columns([1, 1.15, 1.25], gap="small")
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
    if next_col.button("Evaluate", icon=":material/arrow_forward:", type="primary", width="stretch",
                       help="Step 3: the layout's report against Chapter 3's evaluation metrics."):
        ui.go_to_step(3)

# Event outcomes appear as toasts: a message in the page would shift the
# canvas on the next rerun, and Streamlit would remount it (losing focus).
if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"), icon=":material/check_circle:")

canvas_col, panel_col = st.columns([1.6, 1], gap="medium")

# ---------------------------------------------------------------------------
# RIGHT — Constraint Editor | Recommendation Engine (p.53's right-hand tabs)
# ---------------------------------------------------------------------------
with panel_col, st.container(key="ts_panel"):
    tab_editor, tab_reco = st.tabs([":material/tune: Constraint Editor",
                                    ":material/auto_awesome: Recommendation Engine"])

    with tab_editor:
        ids = list(node_by_id)
        default = st.session_state.get("sel_node")
        selected = st.selectbox("Selected Node", ids, index=ids.index(default) if default in ids else 0,
                                format_func=lambda i: _friendly(node_by_id[i]))
        st.session_state["sel_node"] = selected
        node = node_by_id[selected]
        x0, y0, w0, h0 = node["bbox"]
        k = f"{state_key}_{selected}"

        _section("Spatial parameters")
        c1, c2 = st.columns(2)
        x = c1.number_input("X (px)", value=float(x0), step=1.0, key=f"x_{k}")
        y = c2.number_input("Y (px)", value=float(y0), step=1.0, key=f"y_{k}")
        c3, c4 = st.columns(2)
        w = c3.number_input("W (px)", value=float(w0), min_value=4.0, step=1.0, key=f"w_{k}")
        h = c4.number_input("H (px)", value=float(h0), min_value=4.0, step=1.0, key=f"h_{k}")

        _section("Constraint status")
        hard_now = node.get("constraint_type") == "Hard"
        status = st.segmented_control(
            f"Constraint Status (“{_friendly(node)}”)", ["Soft (Algorithmic Logic)", "Hard (Manual Override)"],
            default="Hard (Manual Override)" if hard_now else "Soft (Algorithmic Logic)",
            key=f"ct_{k}", label_visibility="collapsed", width="stretch")
        want_hard = (status or "").startswith("Hard") if status else hard_now

        def _apply(event_type: str, bbox=None, hard=None, note=""):
            try:
                new = session.apply_event(event_type, selected, bbox=bbox, hard=hard)
            except (KeyError, ValueError) as e:
                st.error(str(e))
                return
            st.session_state["flash"] = f"{new['state_id']}: {new['event']['summary']}{note}"
            st.rerun()

        b1, b2, b3, b4, b5 = st.columns([1, 1, 1, 1, 1.7], gap="small")
        if b1.button(":material/arrow_back:", help=f"Nudge left {NUDGE:g}px (on-drop)", width="stretch"):
            _apply("on-drop", [x0 - NUDGE, y0, w0, h0])
        if b2.button(":material/arrow_upward:", help=f"Nudge up {NUDGE:g}px (on-drop)", width="stretch"):
            _apply("on-drop", [x0, y0 - NUDGE, w0, h0])
        if b3.button(":material/arrow_downward:", help=f"Nudge down {NUDGE:g}px (on-drop)",
                     width="stretch"):
            _apply("on-drop", [x0, y0 + NUDGE, w0, h0])
        if b4.button(":material/arrow_forward:", help=f"Nudge right {NUDGE:g}px (on-drop)",
                     width="stretch"):
            _apply("on-drop", [x0 + NUDGE, y0, w0, h0])
        if b5.button("Apply", icon=":material/check:", type="primary", width="stretch",
                     help="Commit the parameters above as one event: a resize if W/H changed, a move "
                          "if X/Y changed, else the Soft/Hard toggle."):
            if (w, h) != (w0, h0):
                _apply("on-resize-complete", [x, y, w, h])
            elif (x, y) != (x0, y0):
                _apply("on-drop", [x, y, w, h])
            elif want_hard != hard_now:
                _apply("lock-toggle", hard=want_hard)
            else:
                st.toast("Nothing changed.")
        st.caption("A moved or resized node becomes Hard: the solver keeps it exactly there and "
                   "re-flows the Soft nodes around it (Formula 3.10).")

        _section("Typography")
        t = session.typography
        family = t["family"].split(",")[0].strip("'\" ")
        st.markdown(f"**{family}** · weight {t['weight']} · {t['base_size']:g} px base")
        with st.expander("Administrative typography (schema-validated)", icon=":material/text_fields:"):
            fam = st.text_input("Font family stack", value=t["family"], key=f"fam_{state_key}")
            wt = st.selectbox("Font weight", FONT_WEIGHTS, index=FONT_WEIGHTS.index(int(t["weight"])),
                              format_func=lambda v: f"{v} — {WEIGHT_NAMES[v]}", key=f"wt_{state_key}")
            bs = st.number_input("Base size (px)", value=float(t["base_size"]), step=1.0, key=f"bs_{state_key}")
            if st.button("Validate and apply typography"):
                try:
                    new = session.set_typography({"family": fam, "weight": int(wt), "base_size": float(bs)})
                except ValueError as e:
                    st.error(str(e))
                else:
                    st.session_state.pop("orch_thumbs", None)
                    st.session_state["flash"] = f"{new['state_id']}: typography applied (schema validation passed)"
                    st.rerun()

        _section("State Timeline (JSON Sync)")
        states = session.chain.states
        with st.container(height=min(64 + 44 * len(states), 300), key="ts_timeline"):
            for i, s in enumerate(states):
                c_total = (s.get("fitness") or {}).get("Total_Cost")
                now = i == len(states) - 1
                row = st.columns([6, 1], vertical_alignment="center")
                row[0].markdown(f'<div class="ts-row{" now" if now else ""}"><code>{s["state_id"]}</code>'
                                f'<span>{html.escape(s["label"])}'
                                + (f" · C={c_total:.4f}" if c_total is not None else "")
                                + ('  <span class="ts-badge on">current</span>' if now else "")
                                + "</span></div>", unsafe_allow_html=True)
                if not now and row[1].button(":material/history:", key=f"restore_{i}", width="stretch",
                                             help=f"Restore {s['state_id']} as a new state (history kept)"):
                    new = session.restore_state(i)
                    st.session_state["flash"] = f"{new['state_id']}: restored {s['state_id']} (history kept)"
                    st.rerun()
        j1, j2 = st.columns([1, 1.2])
        j1.download_button("State chain", data=session.chain.to_json(), icon=":material/data_object:",
                           file_name=os.path.basename(session.chain_path), mime="application/json",
                           width="stretch")
        with j2.popover("Latest event (JSON)", icon=":material/code:", width="stretch"):
            st.json({"state_id": state["state_id"], "event": state["event"],
                     "hard_nodes": state["hard_nodes"], "fitness": state.get("fitness")})

    with tab_reco:
        st.caption("Parallel layout variations — layout type, margin, vertical rhythm and motif "
                   "arrangement — each solved by Cassowary and ranked by the Heuristic Fitness Function "
                   "(lower is better). The first is the fittest of the layout type the master's "
                   "composition calls for.")
        thumbs_key = (id(session), json.dumps(session.typography, sort_keys=True))
        cached = st.session_state.get("orch_thumbs")
        if not cached or cached["key"] != thumbs_key:
            with st.spinner("Rendering the candidates..."):
                items = [(c["candidate_id"], ui.png_of(svg_c, 0.35)) for c, svg_c in session.render_candidates()]
            cached = {"key": thumbs_key, "items": dict(items)}
            st.session_state["orch_thumbs"] = cached
        grid = st.columns(2, gap="small")
        for rank, cand in enumerate(session.candidates, start=1):
            cid = cand["candidate_id"]
            active = state.get("candidate_id") == cid and state["event"].get("type") == "candidate"
            with grid[(rank - 1) % 2], st.container(border=True, key=f"cand_{'on_' if active else ''}{cid}"):
                st.image(cached["items"][cid], width="stretch")
                badges = f'<span class="ts-badge">#{rank}</span>'
                if cand.get("chosen_because"):
                    badges += '<span class="ts-badge rec">Recommended</span>'
                if active:
                    badges += '<span class="ts-badge on">Active</span>'
                st.markdown(f"{badges} **{cid.replace('_', ' ')}**", unsafe_allow_html=True)
                st.caption(cand["label"])
                m = cand["metrics"]
                st.markdown(f'<span class="ts-pill total">C_total {cand["c_total"]:.4f}</span>',
                            unsafe_allow_html=True)
                st.caption(f"collision {m['P_collision']:.4f} · alignment {m['P_align']:.4f} · "
                           f"whitespace {m['P_space']:.4f} · legibility {m['P_legibility']:.4f}"
                           + (f" — recommended: {cand['chosen_because']}" if cand.get("chosen_because") else ""))
                if st.button("In use" if active else "Use this design", key=f"use_{cid}", disabled=active,
                             icon=":material/check:" if active else ":material/swap_horiz:", width="stretch"):
                    new = session.select_candidate(cid)
                    st.session_state["flash"] = f"{new['state_id']}: {cid} is now the active canvas"
                    st.rerun()

# ---------------------------------------------------------------------------
# LEFT — the Active Canvas on a grey workspace, with a status bar
# ---------------------------------------------------------------------------
with canvas_col, st.container(key="ts_workspace"):
    canvas_editor.active_canvas(session, _friendly)
    fit = state.get("fitness") or {}
    info = (f'<span class="ts-pill"><b>{state["state_id"]}</b> · {html.escape(state["label"])}</span>'
            f'<span class="ts-pill">{session.canvas_w}×{session.canvas_h}px</span>')
    status_col, master_col = st.columns([5, 1.2], vertical_alignment="center")
    status_col.markdown(f'<div class="ts-status">{info}{_pills(fit) if fit else ""}</div>',
                        unsafe_allow_html=True)
    master = st.session_state.get("orch_master")
    if master and os.path.exists(master):
        with master_col.popover("Master", icon=":material/image:", width="stretch",
                                help="The master layout this design takes its theme from."):
            st.image(master, width="stretch")
