"""
ThemeSync — Dashboard
======================
Streamlit implementation of the manuscript's two interface prototypes plus
the Phase 4 tooling:

  - Perceptual Ingestion & Initialization Dashboard  (Figure 2, pp. 50-51)
      views/ingestion.py
  - Active Orchestration & Heuristic Scoring Workspace (Figure 3, pp. 53-54)
      views/orchestration.py, with the canvas edited in place by
      canvas_editor.py (select, drag, resize, retype, lock, undo/redo)
  - Phase 4 Evaluation Set (expert rating packet)     views/phase4.py

A thin UI over the pipeline (src/pipeline.py): Stage 0/0b/0c extraction,
OrchestrationSession for Stages 1-6 and the human-in-the-loop events. No
algorithm lives here.

Run (in the themesync_env conda environment):
    streamlit run src/dashboard/app.py
"""

import streamlit as st

st.set_page_config(page_title="ThemeSync", layout="wide")

pages = [
    st.Page("views/ingestion.py", title="Perceptual Ingestion (Fig. 2)", icon="🧬", default=True),
    st.Page("views/orchestration.py", title="Active Orchestration (Fig. 3)", icon="🧩"),
    st.Page("views/phase4.py", title="Phase 4 Evaluation Set", icon="🗂️"),
]
st.navigation(pages).run()
