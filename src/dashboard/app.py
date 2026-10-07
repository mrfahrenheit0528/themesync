"""
ThemeSync — Dashboard
======================
Streamlit implementation of the manuscript's two interface prototypes as a
three-step workflow, plus the Phase 4 tooling:

  Workflow (one step at a time; the others are disabled)
    1. Perceptual Ingestion & Initialization Dashboard  (Figure 2, pp. 50-51)
         views/ingestion.py
    2. Active Orchestration & Heuristic Scoring Workspace (Figure 3, pp. 53-54)
         views/orchestration.py, with the canvas edited in place by
         canvas_editor.py (select, drag, resize, retype, lock, undo/redo)
    3. Evaluation Report on the finished layout (Chapter 3's metrics,
         pp. 55-58)   views/report.py, computed by
         src/evaluation/layout_report.py
  Research tools
    Phase 4 Evaluation Set (expert rating packet)     views/phase4.py

A thin UI over the pipeline (src/pipeline.py): Stage 0/0b/0c extraction,
OrchestrationSession for Stages 1-6 and the human-in-the-loop events. No
algorithm lives here.

Run (in the themesync_env conda environment):
    streamlit run src/dashboard/app.py
"""

import streamlit as st

import components as ui

st.set_page_config(page_title="ThemeSync", layout="wide")

pages = [st.Page(page, title=f"Step {n} · {title}", icon=icon, default=n == 1)
         for n, page, title, icon in ui.STEPS]
pages += [st.Page(page, title=title, icon=icon) for page, title, icon in ui.RESEARCH_PAGES]
navigation = st.navigation(pages, position="hidden")
ui.sidebar()
navigation.run()
