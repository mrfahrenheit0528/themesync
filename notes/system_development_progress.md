# System Development Progress

Snapshot assessment of how much of the ThemeSync system, as described in the
manuscript's Chapter 3 Research Procedure (p. 50-58), is actually built and
working. Written 2026-09-15, while waiting on the scheduled adviser
consultation. Re-run this assessment (re-check code + `results/` + this file)
before citing the percentage anywhere final like Chapter 4 — it will go stale
as work continues.

## Overall: ~74% complete (updated 2026-09-15, post-dashboard build)

This is a weighted estimate, not a literal average of the table below — the
backend/algorithmic core (Phases 1-3) is the bulk of the manuscript's
technical contribution and is largely done and *executed*, not just coded.
Figure 2's dashboard UI is now built and verified (see Phase 1 below,
`src/dashboard/app.py`). The two remaining gaps are Figure 3's orchestration
workspace (Constraint Editor + Recommendation Engine tabs) and the actual
human expert MOS validation (Phase 4), both currently near 0%.

---

## Phase-by-phase breakdown

### Phase 1: Data Extraction and Graph Construction (p. 50-51)

| Component | Manuscript requirement | Status |
|---|---|---|
| K-Means LAB color extraction | Dominant color centroids via K-Means | **Done** — `vision_extraction.py`, `template_ingestor.py` |
| SIFT/SURF stylistic markers | "K-Means and SIFT/SURF algorithms" | **Partial** — only SIFT is actually invoked in code; SURF is named in the manuscript but not implemented. Flagged in `adviser_consultation_checklist.md` section C as a wording-vs-code discrepancy to resolve with adviser |
| Semantic Layout Parsing (YOLOv8 + Tesseract OCR) | Object bounding-box detection + text extraction, converting raster pixels into structured nodes | **Done** — `layout_extractor.py`, fine-tuned on 65 real annotated master-layout images (`themesync_yolo_v2.pt`, held-out mAP50 0.325), wired into `pipeline.py` as Stage 0b (2026-09-15). Full history in `gnn_fixes_and_methodology_notes.md` sections 3.6-3.8 |
| GNN construction + training on CGL-Dataset | GNN maps extracted visual elements into a formal graph, learns hierarchical node-edge dependencies and spatial reasoning baselines | **Done** — `gnn_model.py`, `graph_builder.py`, `train_gnn.py`; trained weights exist (`themesync_gnn_v1.pth`) and are loaded at inference in `pipeline.py`, `evaluate.py`, `experiment_runner.py` |
| Perceptual Ingestion & Initialization Dashboard (Figure 2) | Interactive UI: master template preview, "Visual DNA" panel (K-Means centroids, SIFT/SURF keypoints, relational node graph, user-injected typography), target-format dropdown, "Initialize Orchestration" button | **Built (2026-09-15)** — `src/dashboard/app.py`, a Streamlit app wrapping the existing Stage 0/0b/1-6 backend. Upload → Extract Visual DNA (palette swatches, saliency, detected nodes list) → pick target format (dynamically read from `data/raw/*_payload.json`) → Initialize Orchestration → live rendered SVG + timing breakdown. Font-family is now a real, wired constraint (`AestheticSVGRenderer(font_family=...)`, threaded through `pipeline.py`'s `run_pipeline()`/`stage_render()`/CLI `--font_family`); font weight and base size are captured in the UI but not yet applied to rendering (flagged in-app). Verified end-to-end against a real, unseen poster (`YOUR_TEMPLATE3.jpg`) with a non-default font override landing correctly in the output SVG; both existing test suites still pass |

**Phase 1 estimate: ~90%** — backend and the Figure 2 dashboard are both done and verified; remaining gap is Figure 3 (the orchestration/constraint-editor workspace), not built yet.

### Phase 2: CSP Integration and State Synchronization (p. 51-52)

| Component | Manuscript requirement | Status |
|---|---|---|
| Dynamic Node Instantiation | Ingest user's structural schema (JSON payload), assign Baseline Geometric Tensors per Spatial Hierarchy Index | **Done** — `dynamic_instantiation.py` (`NodeInstantiator`) |
| Cassowary Algorithm constraint solver | Primary linear arithmetic constraint solver; bounding boxes adapt to varying aspect ratios without overlap | **Done** — `cassowary_engine.py` (`ConstraintSolverEngine`) |
| Bi-directional State Machine | Serializes project state to JSON; captures manual HITL interventions as hardened constraints, preventing destructive overwrite on automated updates | **Done** — `state_manager.py` (`LayoutFSM` + `StateManager`), including a `simulate_human_intervention()` method that stands in for a real manual-edit event |
| Constraint Editor UI (Figure 3, right panel) | Interactive tab exposing per-node X/Y/W/H, font, and Soft/Hard constraint toggle, plus a visual JSON state timeline | **Not built** — same gap as Phase 1's dashboard; the backend state it would expose (`StateManager`, FSM history) exists and is inspectable via code/JSON, but not through any UI |

**Phase 2 estimate: ~80%** — backend fully implemented and testable; HITL is currently simulated programmatically, not through a real interface.

### Phase 3: Heuristic Testing and Optimization (p. 52, 55-58)

| Component | Manuscript requirement | Status |
|---|---|---|
| Parallel state-space exploration / candidate generation | Generate multiple layout candidates per run | **Done** — `candidate_generator.py` (`MetaheuristicStateExplorer`), deterministic parametric constraint solving (refactored from stochastic mutation per earlier commit) |
| Heuristic Fitness Function (Formulas 3.11-3.15) | F_layout = α·P_collision + β·P_align + γ·P_whitespace + δ·P_legibility, with legibility cross-referenced against the SIFT/SURF saliency map | **Done** — `optimization_engine.py` (`HeuristicEvaluator`) implements all four penalty terms plus the combined `C_total` score |
| Aesthetic Rendering Pipeline | Projects K-Means color clusters + extracted typography onto generated bounding boxes as a final SVG | **Done** — `aesthetic_renderer.py`; verified rendered SVG outputs exist in `data/rendered/` |
| IoU, Latency, F1/Structural Accuracy metrics | Quantify extraction accuracy (Phase 1), algorithmic latency, and constraint-satisfaction F1 | **Done and actually executed** — `evaluate.py` and `experiment_runner.py` implement and compute all three; `results/evaluation_results.json` and `results/experiment_log.json` contain real, already-generated output, not placeholder code |
| Recommendation Engine UI (Figure 3, "Candidate A/B/C" thumbnails) | Tab showing ranked candidate previews for the designer to choose from | **Not built** — ranked candidates are computed and saved as JSON/SVG, but there's no UI presenting them side-by-side |

**Phase 3 estimate: ~85%** — this is the strongest phase: not only implemented but already run and producing real quantitative results. UI presentation layer is the only missing piece.

*Update 2026-09-28:* results were re-run against the current system (10 trials
per format, event-ID format, format-correct canvases; notes §3.18–3.19).
Baseline is now narrowly better than GNN-guided on both formats (certificate
1.1876 vs 1.2029, event ID 1.2834 vs 1.3012), entirely through the alignment
penalty. That's a real result to report honestly, not a regression in the code.

### Phase 4: Expert Aesthetic Validation (p. 54, 57-58)

| Component | Manuscript requirement | Status |
|---|---|---|
| MOS collection tool | 5-point Likert scale, 3 named dimensions (Visual Hierarchy Preservation, Brand & Typographic Consistency, Constraint & Whitespace Harmony), each scored via Table 2's descriptive rubric, on a randomized sample of outputs | **Built and matches the manuscript (fixed 2026-09-26).** `mos_collector.py` now uses the 3 named parameters verbatim, shows Table 2's full score/rating/description scale to the evaluator (start of session + `?` at any prompt), and presents layouts in a seeded random order (`--sample_size`, `--seed`). Previously implemented a different 4-dimension rubric — found in the 2026-09-15 audit (§3.10), fixed in §3.13 of `gnn_fixes_and_methodology_notes.md`. |
| Actual expert evaluation data | A designated domain expert (professional layout artist/graphic designer) rates a randomized subset of generated outputs | **Not done — 0%.** No MOS results file exists anywhere in `data/processed/` or `results/`. This requires recruiting and running an actual outside expert, which hasn't happened yet |

**Phase 4 estimate: ~20%** — the collection instrument now matches the manuscript and is ready to use; no real evaluation data collected yet. Remaining: pick the fixed set of generated outputs to be rated, recruit the domain expert, run the session.

---

## Cross-cutting gaps (affect multiple phases)

- **Figure 2's dashboard is now built; Figure 3's is not.** The
  Perceptual Ingestion & Initialization Dashboard (master template preview,
  Visual DNA panel, target-format selection, Initialize Orchestration) exists
  as a working Streamlit app (`src/dashboard/app.py`, run via
  `streamlit run src/dashboard/app.py` — must use the `themesync_env` conda
  environment, not `base`, since that's where torch/ultralytics/opencv are
  actually installed). The Active Orchestration workspace (Figure 3 —
  Constraint Editor tab for per-node manual overrides, Recommendation Engine
  tab showing ranked candidate thumbnails side-by-side) is still unbuilt;
  that data is computed and available (`StateManager`, ranked candidates from
  `MetaheuristicStateExplorer`) but not yet exposed through a second UI
  screen. Worth asking the adviser whether Figure 3 is needed for defense or
  whether Figure 2 + the CLI/JSON outputs are sufficient.
- **Underlay detection remains weak** (YOLO mAP50 0.029 on held-out data) —
  already tracked in `adviser_consultation_checklist.md` section A.
- **`aesthetic_cnn.py` is not wired into the live ranking pipeline** — it's a
  standalone, heuristically-distilled model (no real MOS labels yet), trains
  and evaluates independently of `pipeline.py`/`optimization_engine.py`.
  Already tracked in `adviser_consultation_checklist.md` section B as a
  phased-approach question.
- **SIFT is implemented; SURF is not**, despite both being named in the
  manuscript text. Already tracked in section C of the adviser checklist.

---

## How this maps to the adviser checklist

This file is the detailed evidence; `adviser_consultation_checklist.md` is
the short, meeting-ready version. The two new findings from this assessment
worth raising with the adviser that weren't already tracked:

1. Whether Figure 3's Active Orchestration workspace (Constraint Editor +
   Recommendation Engine tabs) is an actual defense requirement, now that
   Figure 2's dashboard is built — or whether Figure 2 + the CLI-driven
   pipeline's generated JSON/SVG artifacts are sufficient.
2. Timeline/logistics for recruiting the Phase 4 domain expert, since MOS
   collection can't start until that person is identified — this is the
   only phase with genuinely zero real data behind it.

---

**How to use this:** treat the percentages here as directional, not
precise — they're a rough weighting of "how much of what the manuscript
describes actually runs," not a line-count or ticket-count metric. Re-derive
from current code + `results/` state rather than trusting old numbers here
if significant time has passed.
