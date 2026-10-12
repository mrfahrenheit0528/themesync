# System Development Progress

Snapshot assessment of how much of the ThemeSync system, as described in the
manuscript's Chapter 3 Research Procedure (p. 50-58), is actually built and
working. Written 2026-09-15, while waiting on the scheduled adviser
consultation. Re-run this assessment (re-check code + `results/` + this file)
before citing the percentage anywhere final like Chapter 4 — it will go stale
as work continues.

## Overall (re-assessed 2026-10-12): ~98% of what the final manuscript, Manu 1210.1, describes runs and is measured

**Re-assessed 2026-10-12** against Manu 1210.1 (the final manuscript), the
code at `f97d897` and `results/` (dev findings, section H):
- **Every component and metric** Chapters 3–5 describe runs and is
  measured. The 12 tests pass, and every Chapter 4 number checked matches
  the results files.
- **The 2026-10-10 gaps are closed:**
  - **On the manuscript side:** SURF, the CNN and Appendix A were
    reworded to the system. The two renderer limits are reported as
    limitations, with a recommendation each.
  - **On the system side:** the checkbox bug is fixed, and the notebook
    is updated.
- **What remains is wording, with no code to write:**
  - **One claim is met only in part:** that manual edits survive "global
    theme updates" (H1). Typography updates keep them. A candidate switch
    or a new Initialize starts a fresh layout, and the earlier edits stay
    restorable in the chain or the session folder.
  - **Four small mismatches (H2–H5):**
    - a re-solve "on every terminal event";
    - "the rule of thirds";
    - mean ± SD promised but not given;
    - markers that can't be "replaced".
- **Completeness isn't the result:** Phase 4 found the baseline rated
  higher than structure mapping + GNN (§3.49).

### Re-assessed 2026-10-10: ~95% of what Manu 0910.1 describes

**Re-assessed 2026-10-10** against Manu 0910.1, the code, and `results/`:
- **What runs and is measured:** every component Chapter 3 describes,
  and every metric it names: IoU, latency, F1, the stress test, the MOS.
  The Phase 4 rating is analysed.
- **What's left is not building. It is:**
  - **three claims the code doesn't meet:** SURF (3.10), a CNN "deployed
    for quantitative aesthetic evaluation" (3.11), and Appendix A's
    per-node GNN features (3.12). Changing the code for the last would
    change the rated system, so rewording is the likely route;
  - **two renderer limits the stress test found** (§3.42), and one
    dashboard bug (the Phase 4 page's checkboxes, §3.35);
  - **housekeeping:** the results notebook predates Phase 4 and the new
    analyses; the Phase 3 battery was run before F1 was recorded.
- **Completeness isn't the result:** Phase 4 found the baseline rated
  higher than structure mapping + GNN (§3.49).

*The 2026-09-29 weighting below gave ~88%; per-phase figures are updated
in place.*

**Consultant's assessment (2026-09-29, after a live demo of the dashboard
and system): "at least 70%".** Her figure counts for more than this
file's internal estimate below, which weighs only how much of Chapter 3's
system runs. Her remarks, as the user relayed them on 2026-10-07 (given
before the dataset was improved), with the status of each:

| Remark | Status (2026-10-07) |
|---|---|
| The dashboard must reflect the steps (Perceptual Ingestion, Active Orchestration); disable the other steps so the user knows which step they're on. | **Done (2026-10-07, notes §3.32).** A step bar marks the current step; only it is enabled in the sidebar; buttons move on or back. |
| Fix the evaluation part and isolate it from the two steps. She meant a report on the **user's layout**, not the Phase 4 packet tool (user, 2026-10-07). | **Done (2026-10-07, notes §3.32).** Step 3, Evaluation Report, scores the finished layout against Chapter 3's metrics; F1 now follows p.56. Phase 4 sits apart under "Research tools". |
| Improve the dataset and avoid background noise. | **Done with YOLO v5** (200 re-annotated images, 2026-10-06). On 32 validation images that neither v4 nor v5 trained on: precision 0.58 → 0.84 (embellishment 0.48 → 0.78, underlay 0.48 → 0.83), mAP50 0.486 → 0.728. Boxes covering over half a poster (background taken as an element) are dropped from training (notes §3.30). |

This is a weighted estimate, not a literal average of the table below. The
backend/algorithmic core (Phases 1-3) is the bulk of the manuscript's
technical contribution, and it is done and *executed*, not just coded.

As of 2026-10-08:
- **The dashboard runs as three steps** (§3.32), styled like Canva in
  ThemeSync's own colours (§3.34):
  - Step 1 is Figure 2 and Step 2 is Figure 3 (`src/dashboard/`,
    notes §3.24). Figure 3's canvas is edited in place: select, drag,
    resize, retype, lock, undo/redo (§3.28).
  - Step 3 is an Evaluation Report on the user's layout, with F1 as p.56
    defines it.
- **The fitness weights are calibrated** (§3.33): p.52's loop kept the
  deployed weights.
- **Detector:** YOLO **v5** is deployed (2026-10-06, §3.30), trained on the
  group's 200-image re-annotation. On 32 images neither model trained on:
  mAP50 0.728 vs. v4's 0.486; embellishment recall 0.51 vs. 0.21.
- **GNN:** v3 reads the master's structure, and its output is registered
  to the master's anchors (§3.26).
- **Candidates** differ in layout archetype (§3.27).
- **Colour clustering is seeded** (§3.29). Earlier results carry palette
  noise.

Phase 4 is analysed (2026-10-10, notes §3.48–3.49). The 2026-10-09
consultation concluded "recommended for POD". The group adopted the
consultation guide's suggested statistical treatment, fixed in
`phase4_analysis.py` before the scores were imported.
- **The experts rated the baseline significantly higher** than structure
  mapping + GNN: overall MOS 3.73 vs 3.33, p_Holm < 0.001, r = −0.95.
- **Most of it is Constraint & Whitespace** (3.77 vs 2.92).
- **Post hoc,** it goes with the larger, uneven gaps the structure mapping
  leaves.
- Five smaller gaps found on 2026-10-08 are in notes §3.35.

---

## Phase-by-phase breakdown

### Phase 1: Data Extraction and Graph Construction (p. 50-51)

| Component | Manuscript requirement | Status |
|---|---|---|
| K-Means LAB color extraction | Dominant color centroids via K-Means | **Done** — `vision_extraction.py`, `template_ingestor.py` |
| SIFT/SURF stylistic markers | "K-Means and SIFT/SURF algorithms" | **Partial** — only SIFT is actually invoked in code; SURF is named in the manuscript but not implemented. Flagged in `adviser_consultation_checklist.md` section C as a wording-vs-code discrepancy to resolve with adviser |
| Semantic Layout Parsing (YOLOv8 + Tesseract OCR) | Object bounding-box detection + text extraction, converting raster pixels into structured nodes | **Done; v5 deployed 2026-10-06 (notes §3.30).** `layout_extractor.py` runs `themesync_yolo_v5.pt`: YOLOv8s from COCO weights at 1024 px (v4's recipe), trained on the group's 200-image re-annotation (160 train / 40 validation), polygons converted and over-half-poster boxes dropped. On 32 validation images neither v4 nor v5 trained on: mAP50 0.728 (v4: 0.486); logo 0.977, text 0.684, underlay 0.643, embellishment 0.609. Tesseract reads each text box; the OCR text is shown, not used as content (the content comes from the user's payload, p.51). **Mean IoU** (p.62 of Manu 0910.1, notes §3.41) on the 40 validation images at the deployed operating point: strict 0.644 (every box; a miss counts 0), and 0.837 for the 75% of boxes found at IoU ≥ 0.5 (logo 0.957 found, mean IoU 0.882). History: §3.6–3.8, 3.12, 3.25, 3.30, 3.41 |
| GNN construction + training on CGL-Dataset | GNN maps extracted visual elements into a formal graph, learns hierarchical node-edge dependencies and spatial reasoning baselines | **Done; v3 deployed 2026-09-29 (notes §3.22, §3.26).** v1 was worse than no model (order kept 47%). v2 learned designers' positions from a naive stack. **v3** starts from the master's mapped structure (`structure_mapping.py`, Table 1's `bbox [x, y]` → initial encoding), trained from naive and distorted-structure starts. Held-out (2,900 CGL layouts): position error 0.036 vs. 0.050 for the structure start alone. Its output is registered to the master's anchors, and the anchors hold at `ANCHOR` strength in Cassowary. With exact anchors, the anchored elements are kept and the unmapped ones are placed 8% better than interpolation (`results/gnn_heldout_eval.json`). `themesync_gnn_v3.pth` is the default |
| Stylistic marker extraction (Stage 0c) | "Scale-invariant stylistic markers" (p.51); saliency of the "inpainted background layer" (p.37, Figure 1(b)) | **Done (2026-09-28, notes §3.23, §3.31)** — `stylistic_markers.py`: text-free background rebuilt from the master's border, motifs (YOLO detections cut out, ranked by SIFT keypoint density; lettering skipped, §3.31), title artwork (title groups, cut out when they separate cleanly). In the automatic Phase 3 battery on the 16 Phase 4 posters (run 20261006_195534): title artwork in 14 of 16 outputs per format, motifs in 3. The packet's per-poster overrides are a separate, human choice (§3.31, §3.35) |
| Perceptual Ingestion & Initialization Dashboard (Figure 2) | Interactive UI: master template preview, "Visual DNA" panel (K-Means centroids, SIFT/SURF keypoints, relational node graph, user-injected typography), target-format dropdown, "Initialize Orchestration" button | **Built; rebuilt 2026-09-29 (notes §3.24)** — `src/dashboard/views/ingestion.py`. Everything in the mockup, plus the Stage 0c markers (with ticks and uploads), the logo picker, and an editable content payload. Font family, weight and base size now all drive the renderer's type scale, and typography and content are JSON-Schema-validated before Initialize is allowed. Initialize opens the Figure 3 workspace |

**Phase 1 estimate: ~93%** (2026-10-10). Done and verified. SURF remains named but not implemented (revision list 3.10), and the GNN reads one global colour and saliency per layout, not Appendix A's per-node fields (3.12).

### Phase 2: CSP Integration and State Synchronization (p. 51-52)

| Component | Manuscript requirement | Status |
|---|---|---|
| Dynamic Node Instantiation | Ingest user's structural schema (JSON payload), assign Baseline Geometric Tensors per Spatial Hierarchy Index | **Done** — `dynamic_instantiation.py` (`NodeInstantiator`) |
| Cassowary Algorithm constraint solver | Primary linear arithmetic constraint solver; bounding boxes adapt to varying aspect ratios without overlap | **Done** — `cassowary_engine.py` (`ConstraintSolverEngine`) |
| Bi-directional State Machine | Serializes project state to JSON; captures manual HITL interventions as hardened constraints, preventing destructive overwrite on automated updates | **Done (2026-09-29)** — `StateChain` (append-only JSON chain, Formula 3.9) + `OrchestrationSession.apply_event` (on-drop / on-resize-complete / lock-toggle re-solve with the adjusted node Hard, Formula 3.10). Retention is measured: moves, resizes and locks are kept exactly through re-solves, no overlap (`evaluate.py`, `test_hard_constraints_preserved`; every re-solve of a session's chain is checked by `layout_report.retention_check`, §3.32) |
| Pre-orchestration schema validation (p.43) | Typography and payload validated against a rigid schema; a violation rejects the initialization | **Done (2026-09-29)** — `schema_validation.py`, JSON Schema (Draft 2020-12): weight ∈ {100…900}, base size 8 px to 15% of the viewport; each content variable present, within `max_characters` |
| Constraint Editor UI (Figure 3, right panel) | Interactive tab exposing per-node X/Y/W/H, font, and Soft/Hard constraint toggle, plus a visual JSON state timeline | **Built (2026-09-29)** — `src/dashboard/views/orchestration.py`: node selection, X/Y/W/H, font, Soft/Hard, nudges, Apply; State Timeline (JSON Sync) with Restore and download |
| Active canvas (Figure 3, centre) | The design adapted to the target format, where the designer's manual overrides happen (pp.53–54); terminal events only (p.42) | **Built (2026-09-29, notes §3.28)** — `src/dashboard/canvas_editor.*`: click to select (the Constraint Editor follows), drag, resize handles, double-click to retype (schema-validated), arrow nudges, L to lock, Ctrl+Z / Ctrl+Shift+Z (undo/redo append states), snapping to Formula 3.13's grid. The browser only previews; each gesture sends one event. Tested in headless Firefox |

**Phase 2 estimate: ~100%** (2026-10-10). Implemented, interactive (including editing on the canvas itself), and measured: retention, schema validation, and latency over 1,360 edits (§3.43, §3.47).

### Phase 3: Heuristic Testing and Optimization (p. 52, 55-58)

| Component | Manuscript requirement | Status |
|---|---|---|
| Parallel state-space exploration / candidate generation | Generate multiple layout candidates per run | **Done** — `candidate_generator.py`: six candidates, each a layout archetype (classic, left-aligned, art column, banner, floating card, full-width band) with its own margin, rhythm and motif arrangement (incl. a "hero" motif). Each is solved by Cassowary and scored on its own composed background, with Formulas 3.13–3.14 taken over its own content area (notes §3.27) |
| Heuristic Fitness Function (Formulas 3.11-3.15) | F_layout = α·P_collision + β·P_align + γ·P_whitespace + δ·P_legibility, with legibility cross-referenced against the SIFT/SURF saliency map | **Done** — `optimization_engine.py` (`HeuristicEvaluator`) implements all four penalty terms plus the combined `C_total` score. Weights calibrated 2026-10-08 (`weight_calibration.py`, notes §3.33): p.52's loop kept the deployed weights; halving or doubling any weight changes at most 1 of the 64 rated layouts |
| Aesthetic Rendering Pipeline | Projects K-Means color clusters + extracted typography onto generated bounding boxes as a final SVG | **Done** — `aesthetic_renderer.py` + `decor.py`: text-free master background, certificate panel with the title artwork as a watermark, motifs, title artwork on the event ID, WCAG-checked text colours, type scale on the user's base size (2026-09-28) |
| IoU, Latency, F1/Structural Accuracy metrics | Quantify extraction accuracy (Phase 1), algorithmic latency, and constraint-satisfaction F1 | **All three measured.** **F1** follows p.56 per element (`layout_report.structural_accuracy`, §3.32): 1.0 on `evaluate.py`'s run, and 1.0 on all 64 rated layouts, read from the packet's own files (`rated_layouts_check.py`, §3.44; `experiment_runner.py` records it per run too). **Latency** over 1,360 edits in 34 sessions (`latency_benchmark.py`, §3.43): Cassowary median 0.4 ms (all within 0.1 s); a full edit median 90 ms, 95th pct 176 ms, max 206 ms (all within 1.0 s, 61% within 0.1 s) after §3.47's image caches, which leave the output byte-identical (before: 157 / 338 / 393 ms). **IoU** as p.62 defines it (YOLO v5 on the 40 validation images): strict mean 0.644, mean of found boxes 0.837 at 75% recall (`yolo_iou.py`, §3.41). **Stress test** (p.55, `stress_test.py`, §3.42): the solver holds at every max length (F1 1.0) and the schema rejects max + 1; the certificate's text fits at every max; the event ID's organisation header overflows past 48 characters per line, and more than 5 signature blocks overlap. F1 scores boxes, so only the text-fit measure sees the overflow. The GNN-to-solver IoU is renamed "GNN–solver overlap" (§3.45) |
| Recommendation Engine UI (Figure 3, "Candidate A/B/C" thumbnails) | Tab showing ranked candidate previews for the designer to choose from | **Built (2026-09-29)** — every ranked candidate with its thumbnail and all four penalties; "Use this candidate" makes it the active canvas (a state in the chain) |

**Phase 3 estimate: ~95%** (2026-10-10). Every Chapter 3 metric is measured, including the stress test, the weight calibration and a master-derived R_target (§3.41–3.46). The CNN aesthetic evaluator (`themesync_cnn_v1.pth`) is still not wired into ranking or the report (revision list 3.11).

*Update 2026-10-06 (notes §3.26, §3.30, §3.31):* the Phase 3 battery runs
the group's new set of 16 unseen Phase 4 posters × 2 formats × 3 Stage 2
conditions (GNN, mapping only, baseline) with YOLO v5: 96 full runs
(run 20261006_195534, `results/experiment_log.json`,
`notebooks/results_analysis.ipynb`).
- **Each poster's output follows its own composition** (§3.31): 4 layout
  types per format across the 16 posters, where before every ID was
  left-aligned.
- **Structure transfer works.** The output is closer to the master than
  the baseline:
  - event IDs: on 15 of 16 (structure error 0.045 vs. 0.117);
  - certificates: on 14 of 16 (0.056 vs. 0.089).
- **Formula 3.11 doesn't see it.**
  - Certificates: the GNN's C_total equals the baseline's on 10 of 16, is
    lower (better) on 4 and higher on 2 (means 0.0125 vs. 0.0126). The "15 of 16" tie was the earlier
    run 20261006_144208.
  - On IDs the baseline is slightly better (0.1583 vs. 0.1633), through
    legibility.
- **GNN vs. mapping only:** the same anchors; the GNN moves the unmapped
  elements on 14 of 32 runs. Its gain is shown on held-out data.
- **Reading:** report this as is. Phase 4's blind MOS judges composition.

### Phase 4: Expert Aesthetic Validation (p. 54, 57-58)

| Component | Manuscript requirement | Status |
|---|---|---|
| MOS collection tool | 5-point Likert scale, 3 named dimensions (Visual Hierarchy Preservation, Brand & Typographic Consistency, Constraint & Whitespace Harmony), each scored via Table 2's descriptive rubric, on a randomized sample of outputs | **Built and matches the manuscript (fixed 2026-09-26).** `mos_collector.py` now uses the 3 named parameters verbatim, shows Table 2's full score/rating/description scale to the evaluator (start of session + `?` at any prompt), and presents layouts in a seeded random order (`--sample_size`, `--seed`). Previously implemented a different 4-dimension rubric — found in the 2026-09-15 audit (§3.10), fixed in §3.13 of `gnn_fixes_and_methodology_notes.md`. |
| Actual expert evaluation data | A designated domain expert (professional layout artist/graphic designer) rates a randomized subset of generated outputs | **Collected and analysed (2026-10-10).** Four experts (Eisen Rose D. Galvante, Kyz Denise Aquino, Mark Joseph Orias, Mark Kenneth C. Ellorde), 768 ratings, in `results/mos_results.json`. `phase4_analysis.py` (the adopted plan, committed before the import): baseline MOS 3.73 vs 3.33 for structure mapping + GNN, Wilcoxon p_Holm < 0.001, r = −0.95; Constraint & Whitespace 3.77 vs 2.92; Visual Hierarchy n.s.; Kendall's W 0.63. Post hoc: `phase4_posthoc.py` (§3.49) |
| Rating set and packet | Outputs compared against the original master layout (p.54) | **Built and sent (2026-10-07).** `phase4_packet.py`: 16 unseen posters × 2 formats × GNN / no-GNN baseline = 64 layouts, blind codes, a private key (2026-10-07 14:43), a packet and score sheet per expert (§3.20). The layouts come from the code at `8422282` (§3.32). ANTI_HAZING_LAW's four pages carry the "CLOSED" stamp and a damaged title cut (§3.35). The dashboard page "Phase 4 Evaluation Set" does the same without editing CSVs (§3.21) |

**Phase 4 estimate: done** (2026-10-10). The scores are imported and
analysed (§3.48–3.49). Without ANTI_HAZING_LAW, the conclusions are the
same. Remaining:
- confirming the manifest's guesses: ANTI_HAZING_LAW's university, CMET's
  year, "DEBESMSCAT", and the three blank dates. They are already printed
  on the rated pages, so this is for the record, not a change.

---

## Cross-cutting gaps (affect multiple phases)

- **The dashboard is built:** three steps plus the Phase 4 research tool
  (`streamlit run src/dashboard/app.py` from the repo root, in
  `themesync_env` on the server, or in `.venv` on Windows per the README).
  Restart the dashboard after pulling code changes: Streamlit doesn't
  hot-reload helper modules.
- **The dashboard is exposed by default.** `streamlit run` binds every
  interface, and on the school server it printed the machine's public
  address. Consider `--server.address 127.0.0.1` plus an SSH tunnel; it
  has no login and holds students' names (notes §3.28).
- **Underlay and embellishment detection improved with v5** (mAP50 0.643
  and 0.609, recall 0.52 and 0.51; v4: recall 0.10 and 0.21), on 32
  validation images neither model trained on (§3.30). They remain below
  logo (0.977) and text (0.684).
- **`aesthetic_cnn.py` is not wired into the live ranking pipeline** — it's a
  standalone, heuristically-distilled model (no real MOS labels yet), trains
  and evaluates independently of `pipeline.py`/`optimization_engine.py`.
  Already tracked in `adviser_consultation_checklist.md` section B as a
  phased-approach question.
- **SIFT is implemented; SURF is not**, despite both being named in the
  manuscript text. Already tracked in section C of the adviser checklist.
- **The Phase 4 page's checkboxes ignore the manifest** once a session has
  shown them (§3.35; how ANTI_HAZING_LAW lost its overrides). Not fixed.
  The rated set won't be regenerated, but fix it before the page is used
  again.
- **`notebooks/results_analysis.ipynb` predates Phase 4** (its Phase 4
  section says "No real data yet"). It also lacks the IoU, stress-test,
  latency, rated-layout and R_target results (§3.41–3.49).

---

## How this maps to the adviser checklist

This file is the detailed evidence; `adviser_consultation_checklist.md` is
the short, meeting-ready version. The two new findings from this assessment
worth raising with the adviser that weren't already tracked:

1. Recruiting the Phase 4 experts: **done** (four experts, packets out
   2026-10-07).
2. Whether the Phase 3 result (the fitness function can't separate the
   Stage 2 conditions on certificates; the structure error can) is
   reported as is, with the MOS as the deciding measure. The weight
   calibration (§3.33) found the same: Formula 3.11 barely separates the
   candidates.

---

**How to use this:** treat the percentages here as directional, not
precise — they're a rough weighting of "how much of what the manuscript
describes actually runs," not a line-count or ticket-count metric. Re-derive
from current code + `results/` state rather than trusting old numbers here
if significant time has passed.
