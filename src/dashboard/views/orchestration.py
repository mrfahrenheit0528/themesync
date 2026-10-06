"""
ThemeSync — Active Orchestration & Heuristic Scoring Workspace (Figure 3)
==========================================================================
Chapter 3, pp. 53-54. The central canvas shows the design adapted to the
target format; the right-hand interface has two tabs:

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
"""

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


session = st.session_state.get("orch")
st.title("ThemeSync")
st.caption("Phase 2 & 3 · Active Orchestration & Heuristic Scoring (Figure 3)")
if session is None:
    st.info("No orchestration yet — extract the Visual DNA and press **Initialize Orchestration** "
            "on the Perceptual Ingestion page first.")
    st.page_link("views/ingestion.py", label="Go to Perceptual Ingestion (Fig. 2)", icon="🧬")
    st.stop()

state = session.chain.current
nodes = state["nodes"]
node_by_id = {n["node_id"]: n for n in nodes}
state_key = state["state_id"]
# A fixed slot: a message that appears only after an event would shift every
# element below it on the next rerun, and Streamlit would remount the canvas
# (losing its keyboard focus).
flash_slot = st.empty()
if "flash" in st.session_state:
    flash_slot.success(st.session_state.pop("flash"))

canvas_col, panel_col = st.columns([1.35, 1], gap="large")

# ---------------------------------------------------------------------------
# RIGHT — Constraint Editor | Recommendation Engine
# ---------------------------------------------------------------------------
with panel_col:
    tab_editor, tab_reco = st.tabs(["CONSTRAINT EDITOR", "RECOMMENDATION ENGINE"])

    with tab_editor:
        ids = list(node_by_id)
        default = st.session_state.get("sel_node")
        selected = st.selectbox("Selected Node", ids, index=ids.index(default) if default in ids else 0,
                                format_func=lambda i: _friendly(node_by_id[i]))
        st.session_state["sel_node"] = selected
        node = node_by_id[selected]
        x0, y0, w0, h0 = node["bbox"]

        st.markdown("**Spatial Parameters**")
        c1, c2, c3, c4 = st.columns(4)
        k = f"{state_key}_{selected}"
        x = c1.number_input("X (px)", value=float(x0), step=1.0, key=f"x_{k}")
        y = c2.number_input("Y (px)", value=float(y0), step=1.0, key=f"y_{k}")
        w = c3.number_input("W (px)", value=float(w0), min_value=4.0, step=1.0, key=f"w_{k}")
        h = c4.number_input("H (px)", value=float(h0), min_value=4.0, step=1.0, key=f"h_{k}")

        t = session.typography
        family = t["family"].split(",")[0].strip("'\" ")
        st.markdown(f"**Font:** {family} | Weight: {t['weight']} | Size: {t['base_size']:g}px "
                    f"(base of the type scale)")

        hard_now = node.get("constraint_type") == "Hard"
        status = st.radio(f"Constraint Status (“{_friendly(node)}”)",
                          ["Soft (Algorithmic Logic)", "Hard (Manual Override)"],
                          index=1 if hard_now else 0, key=f"ct_{k}")
        want_hard = status.startswith("Hard")

        def _apply(event_type: str, bbox=None, hard=None, note=""):
            try:
                new = session.apply_event(event_type, selected, bbox=bbox, hard=hard)
            except (KeyError, ValueError) as e:
                st.error(str(e))
                return
            st.session_state["flash"] = f"{new['state_id']}: {new['event']['summary']}{note}"
            st.rerun()

        b1, b2, b3, b4, b5 = st.columns(5)
        if b1.button("←", help=f"Nudge left {NUDGE:g}px (on-drop)", width="stretch"):
            _apply("on-drop", [x0 - NUDGE, y0, w0, h0])
        if b2.button("↑", help=f"Nudge up {NUDGE:g}px (on-drop)", width="stretch"):
            _apply("on-drop", [x0, y0 - NUDGE, w0, h0])
        if b3.button("↓", help=f"Nudge down {NUDGE:g}px (on-drop)", width="stretch"):
            _apply("on-drop", [x0, y0 + NUDGE, w0, h0])
        if b4.button("→", help=f"Nudge right {NUDGE:g}px (on-drop)", width="stretch"):
            _apply("on-drop", [x0 + NUDGE, y0, w0, h0])
        if b5.button("Apply", type="primary", width="stretch",
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

        with st.expander("Administrative typography (schema-validated)"):
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

        st.markdown("**State Timeline (JSON Sync)**")
        for i, s in enumerate(session.chain.states):
            c_total = (s.get("fitness") or {}).get("Total_Cost")
            line = f"> **{s['state_id']}**: {s['label']}" + (f" · C={c_total:.4f}" if c_total is not None else "")
            row = st.columns([5, 1.3])
            row[0].markdown(line + ("  ◀ current" if i == len(session.chain.states) - 1 else ""))
            if i < len(session.chain.states) - 1 and row[1].button("Restore", key=f"restore_{i}"):
                new = session.restore_state(i)
                st.session_state["flash"] = f"{new['state_id']}: restored {s['state_id']} (history kept)"
                st.rerun()
        st.download_button("⬇ State chain (JSON)", data=session.chain.to_json(),
                           file_name=os.path.basename(session.chain_path), mime="application/json")
        with st.expander("Latest event (JSON)"):
            st.json({"state_id": state["state_id"], "event": state["event"],
                     "hard_nodes": state["hard_nodes"], "fitness": state.get("fitness")})

    with tab_reco:
        st.markdown("**Heuristic Recommendation Engine**")
        st.caption("Parallel layout variations — layout type, margin, vertical rhythm and motif "
                   "arrangement — each solved by Cassowary and scored by the fitness function (lower is "
                   "better). The first is the fittest of the layout type the master's composition calls for.")
        thumbs_key = (id(session), json.dumps(session.typography, sort_keys=True))
        cached = st.session_state.get("orch_thumbs")
        if not cached or cached["key"] != thumbs_key:
            with st.spinner("Rendering the candidates..."):
                items = [(c["candidate_id"], ui.png_of(svg, 0.35)) for c, svg in session.render_candidates()]
            cached = {"key": thumbs_key, "items": dict(items)}
            st.session_state["orch_thumbs"] = cached
        for rank, cand in enumerate(session.candidates, start=1):
            active = state.get("candidate_id") == cand["candidate_id"] and state["event"].get("type") == "candidate"
            with st.container(border=True):
                img_col, info_col = st.columns([1, 1.4])
                img_col.image(cached["items"][cand["candidate_id"]], width="stretch")
                info_col.markdown(f"**[ {cand['candidate_id'].replace('_', ' ')} ]** · rank {rank}"
                                  + ("  ◀ active" if active else ""))
                info_col.caption(cand["label"])
                if cand.get("chosen_because"):
                    info_col.caption(f"Recommended: {cand['chosen_because']}.")
                info_col.markdown(_metrics_line(cand["metrics"]))
                if info_col.button("Use this candidate", key=f"use_{cand['candidate_id']}", disabled=active):
                    new = session.select_candidate(cand["candidate_id"])
                    st.session_state["flash"] = f"{new['state_id']}: {cand['candidate_id']} is now the active canvas"
                    st.rerun()

# ---------------------------------------------------------------------------
# LEFT — Active Canvas
# ---------------------------------------------------------------------------
with canvas_col:
    st.subheader("Active Canvas")
    svg = session.rendered_path
    canvas_editor.active_canvas(session, _friendly)
    fit = state.get("fitness") or {}
    st.caption(f"{session.domain.replace('_', ' ').title()} · {session.canvas_w}×{session.canvas_h}px · "
               f"{state['state_id']} ({state['label']}) · {'GNN-guided' if session.use_gnn else 'no-GNN baseline'}")
    if fit:
        st.markdown(_metrics_line(fit))
    d1, d2, d3 = st.columns(3)
    d1.download_button("⬇ SVG", data=ui.reader(svg), file_name=os.path.basename(svg), mime="image/svg+xml",
                       width="stretch")
    d2.download_button("⬇ PNG (2×)", data=lambda: open(ui.png_of(svg, 2.0), "rb").read(),
                       file_name=os.path.basename(svg).replace(".svg", ".png"), mime="image/png",
                       width="stretch")
    d3.download_button("⬇ PDF", data=lambda: open(rasterize.svg_to_pdf(svg), "rb").read(),
                       file_name=os.path.basename(svg).replace(".svg", ".pdf"), mime="application/pdf",
                       width="stretch")
    master = st.session_state.get("orch_master")
    if master and os.path.exists(master):
        with st.expander("Master layout (theme source)"):
            st.image(master, width="stretch")
