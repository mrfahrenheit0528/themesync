"""
ThemeSync — Evaluation Report (Step 3)
=======================================
The layout the designer finished in Step 2, scored against Chapter 3's
evaluation metrics (pp. 55-58) by src/evaluation/layout_report.py:

  - Heuristic fitness (Formula 3.11), next to ThemeSync's recommendation
  - Structural accuracy (F1, p.56), element by element
  - Manual refinements kept through every re-solve (non-destructive, p.54)
  - Algorithmic latency (p.55): the pipeline's stages and every edit
  - Hybrid Visual DNA correctness (pp.42-43): the K-Means elbow and the
    schema validations

It only reads the session: "Back to editing" returns to Step 2 with the
canvas as it was, and the report follows every further edit.
"""

import json
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import components as ui                    # noqa: E402
import rasterize                           # noqa: E402
from layout_report import build_report     # noqa: E402


@st.cache_data(show_spinner="Rendering the layout...")
def _preview(svg_path: str, mtime: float) -> str:
    return ui.png_of(svg_path, 1.0)


def _num(value, digits: int = 4) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _swatches(hexes: list) -> None:
    st.markdown("".join(f'<span title="{h}" style="display:inline-block;width:2.2rem;height:1.4rem;'
                        f'margin-right:.35rem;border-radius:4px;border:1px solid rgba(128,128,128,.4);'
                        f'background:{h};"></span>' for h in hexes)
                + "&nbsp;" + " · ".join(f"`{h}`" for h in hexes), unsafe_allow_html=True)


session = st.session_state.get("orch")
actions = ui.enter_step(3, ui.design_name(session))
session = st.session_state["orch"]   # without a layout, enter_step went back to Step 1
report = build_report(session)
layout, fit = report["layout"], report["fitness"]
acc, kept, lat, dna = (report["structural_accuracy"], report["retention"], report["latency"],
                       report["visual_dna"])

st.caption("Evaluation Report · the finished layout scored against Chapter 3's evaluation metrics "
           "(pp. 55-58). Go back to keep editing; the report follows every change.")
with actions:
    edit_col, back_col, json_col = st.columns([1.2, 1, 1.15], gap="small")
    if edit_col.button("Edit", icon=":material/arrow_back:", type="primary", width="stretch",
                       help="Back to Step 2, with the canvas as you left it."):
        ui.go_to_step(2)
    with back_col:
        ui.back_to_step_one("back_from_3")
    json_col.download_button("Report", data=json.dumps(report, indent=2, default=str),
                             icon=":material/download:", file_name=f"ThemeSync_{session.stem}_report.json",
                             mime="application/json", width="stretch", help="The report as JSON.")

# ---------------------------------------------------------------------------
# Headline numbers
# ---------------------------------------------------------------------------
yours, recommended = fit["yours"]["c_total"], fit["recommended"]["c_total"]
same = yours is not None and abs(yours - recommended) < 1e-9
with st.container(key="bento_tiles"):
    t1, t2, t3, t4 = st.columns(4, gap="small")
    with t1.container(border=True, key="card_m_fitness"):
        st.metric("Fitness (C_total)", _num(yours),
                  delta=None if same or yours is None else f"{yours - recommended:+.4f} vs. recommended",
                  delta_color="inverse",
                  help="Formula 3.11; lower is better." + (" Same as ThemeSync's recommendation." if same else ""))
    with t2.container(border=True, key="card_m_f1"):
        st.metric("Structural accuracy (F1)", f"{acc['f1']:.2f}",
                  help=f"p.56: TP {acc['tp']} · FP {acc['fp']} · FN {acc['fn']}.")
    with t3.container(border=True, key="card_m_kept"):
        if kept["edits_checked"]:
            st.metric("Manual edits kept", f"{kept['edits_checked'] - len(kept['violations'])}/{kept['edits_checked']}",
                      help=f"Edit checks across {kept['resolves']} re-solve(s), within 1 px.")
        else:
            st.metric("Manual edits kept", "—", help="No moves, resizes or locks yet.")
    with t4.container(border=True, key="card_m_latency"):
        if lat["event_total"]["n"]:
            st.metric("Median edit latency", f"{lat['event_total']['median_ms']:.0f} ms",
                      help=f"{lat['event_total']['n']} edit(s); slowest {lat['event_total']['max_ms']:.0f} ms. "
                           "Re-solve, re-score, re-render and save.")
        else:
            st.metric("Pipeline latency", f"{lat['pipeline_total_ms'] / 1000:.1f} s",
                      help="Stages 0-6 at initialization.")

preview_col, detail_col = st.columns([0.95, 1.65], gap="medium")

# ---------------------------------------------------------------------------
# LEFT — the layout being evaluated, kept in view
# ---------------------------------------------------------------------------
with preview_col, st.container(border=True, key="card_preview"):
    st.markdown(":material/image: **Evaluated layout**")
    svg = session.rendered_path
    st.image(_preview(svg, os.path.getmtime(svg)), width="stretch")
    st.caption(f"{layout['format'].replace('_', ' ').title()} · {session.canvas_w}×{session.canvas_h}px · "
               f"{layout['state_id']} ({layout['label']}) · {layout['states']} states, "
               f"{layout['designer_edits']} designer edit(s) · "
               f"{'GNN-guided' if session.use_gnn else 'no-GNN baseline'}")
    d1, d2, d3 = st.columns(3, gap="small")
    d1.download_button("SVG", data=ui.reader(svg), file_name=os.path.basename(svg), mime="image/svg+xml",
                       icon=":material/download:", width="stretch")
    d2.download_button("PNG", data=lambda: open(ui.png_of(svg, 2.0), "rb").read(),
                       file_name=os.path.basename(svg).replace(".svg", ".png"), mime="image/png",
                       icon=":material/download:", width="stretch", help="2× resolution")
    d3.download_button("PDF", data=lambda: open(rasterize.svg_to_pdf(svg), "rb").read(),
                       file_name=os.path.basename(svg).replace(".svg", ".pdf"), mime="application/pdf",
                       icon=":material/download:", width="stretch")
    master = st.session_state.get("orch_master")
    if master and os.path.exists(master):
        with st.popover("Master layout (theme source)", icon=":material/image:", width="stretch"):
            st.image(master, width="stretch")

# ---------------------------------------------------------------------------
# RIGHT — the metrics, as cards
# ---------------------------------------------------------------------------
with detail_col, st.container(key="bento_report"):
    f_col, k_col = st.columns([1.45, 1], gap="small")
    with f_col.container(border=True, key="card_fitness"):
        st.markdown(":material/functions: **Heuristic fitness (Formula 3.11)**")
        rec_name = fit["recommended"]["candidate_id"].replace("_", " ")
        rows = [{"Penalty": f"{a['term']} (Formula {a['formula']})", "Weight": a["weight"],
                 "Your layout": a["weighted"], f"Recommended ({rec_name})": b["weighted"]}
                for a, b in zip(fit["yours"]["terms"], fit["recommended"]["terms"])]
        rows.append({"Penalty": "C_total", "Weight": None, "Your layout": yours,
                     f"Recommended ({rec_name})": recommended})
        st.dataframe(rows, hide_index=True, width="stretch")
        st.caption(f"Each cell is the penalty × its weight; they add up to C_total, and lower is better. "
                   f"By C_total your layout ranks **{fit['rank']} of {fit['candidates']}** among the "
                   f"Recommendation Engine's candidates.")
    with k_col.container(border=True, key="card_kept"):
        st.markdown(":material/push_pin: **Manual refinements kept (p.54)**")
        if not kept["edits_checked"]:
            st.info("No moves, resizes or locks yet, so there is nothing to check. Refine the layout in "
                    "Step 2 and come back.")
        elif not kept["violations"]:
            st.success(f"Every manual edit stayed exactly where it was put (within 1 px) through "
                       f"{kept['resolves']} re-solve(s): {kept['edits_checked']} checks, none failed.")
        else:
            st.error(f"{len(kept['violations'])} of {kept['edits_checked']} checks failed: the solver moved "
                     "an element that was set by hand.")
            st.dataframe([{"State": v["state_id"], "Element": v["node_id"], "Set to": v["designer_box"],
                           "Found at": v["box"]} for v in kept["violations"]], hide_index=True, width="stretch")

    with st.container(border=True, key="card_accuracy"):
        st.markdown(":material/fact_check: **Structural accuracy (F1, p.56)**")
        st.markdown(f"Precision **{acc['precision']:.2f}** · recall **{acc['recall']:.2f}** · "
                    f"F1 **{acc['f1']:.2f}** — {acc['tp']} TP, {acc['fp']} FP, {acc['fn']} FN")
        ok = {"algorithm": "no overlap, inside the canvas", "designer": "where the designer put it"}
        rows = [{"Element": r["name"], "Placed by": r["placed_by"] or "—", "Result": r["result"],
                 "Why": "; ".join(r["reasons"]) or ok.get(r["placed_by"], "")}
                for r in acc["nodes"]]
        if any(r["notes"] for r in acc["nodes"]):
            for row, r in zip(rows, acc["nodes"]):
                row["Designer's placement"] = "; ".join(r["notes"])
        st.dataframe(rows, hide_index=True, width="stretch")
        st.caption("TP: an element of the content payload placed with no overlap and inside the canvas "
                   "(and, if you moved, resized or locked it, still exactly there). FP: one the algorithm "
                   "placed over another element or past the canvas edge, or one of yours the solver moved. "
                   "FN: a payload element missing from the canvas. Where you put an element is your call, "
                   "so it is noted, not counted.")

    with st.container(border=True, key="card_latency"):
        st.markdown(":material/speed: **Algorithmic latency (p.55)**")
        stage_col, event_col = st.columns([1, 1.25], gap="small")
        with stage_col:
            st.dataframe([{"Stage": s["stage"], "ms": s["ms"]} for s in lat["stages"]]
                         + [{"Stage": "Total", "ms": lat["pipeline_total_ms"]}], hide_index=True, width="stretch")
            st.caption("At initialization. Stage 0b shows 0 ms: Step 1's detection is reused.")
        with event_col:
            if lat["events"]:
                st.dataframe([{"State": e["state_id"], "Event": e["summary"], "Solver (ms)": e["solve_ms"],
                               "Total (ms)": e["total_ms"]} for e in lat["events"]],
                             hide_index=True, width="stretch")
                solver = lat["resolve_solver"]
                st.caption("Total: re-solve, re-score, re-render and save of the state chain."
                           + (f" Cassowary alone: median {solver['median_ms']:.1f} ms over {solver['n']} "
                              f"re-solve(s)." if solver["n"] else ""))
            else:
                st.caption("No edits yet; each one's latency appears here.")

    with st.container(border=True, key="card_dna"):
        st.markdown(":material/palette: **Hybrid Visual DNA correctness (pp.42-43)**")
        if dna["palette"]:
            _swatches(dna["palette"])
        elbow_col, schema_col = st.columns([1, 1.2], gap="small")
        elbow = dna["elbow"]
        with elbow_col:
            if elbow:
                st.dataframe([{"k": k, "WCSS": w, "": "◀ chosen (elbow)" if k == elbow["k"] else ""}
                              for k, w in zip(elbow["ks"], elbow["wcss"])], hide_index=True, width="stretch")
                st.caption(f"K-Means in CIE L*a*b* (Formula 3.1) for k = {elbow['ks'][0]}–{elbow['ks'][-1]}; "
                           f"the Elbow Method picked k = {elbow['k']}, the point farthest from the line "
                           "joining the curve's ends.")
            else:
                st.caption("Elbow Method: not recorded for this layout (a grayscale master clusters with a "
                           "fixed k).")
        with schema_col:
            st.dataframe([{"Schema validation": c["check"], "Result": c["result"],
                           "Errors": "; ".join(c["errors"]) or "—"} for c in dna["schema_checks"]],
                         hide_index=True, width="stretch")
            st.caption(f"Text and typography edits re-validated in Step 2: {dna['revalidated_edits']} passed "
                       "(a rejected edit is never applied).")

    st.caption("IoU (p.55) needs ground-truth boxes and the MOS (pp.57-58) needs expert raters, so neither "
               "applies to a single layout: they are measured in Phase 1 and Phase 4.")
