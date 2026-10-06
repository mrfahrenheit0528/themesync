# System Development Progress

Snapshot assessment of how much of the ThemeSync system, as described in the
manuscript's Chapter 3 Research Procedure (p. 50-58), is actually built and
working. Written 2026-09-15, while waiting on the scheduled adviser
consultation. Re-run this assessment (re-check code + `results/` + this file)
before citing the percentage anywhere final like Chapter 4 — it will go stale
as work continues.

## Overall: ~88% complete (updated 2026-09-29, second pass)

**Consultant's assessment (2026-09-29, after a live demo of the dashboard
and system): 70%.** Her figure counts for more than this file's internal
estimate below, which weighs only how much of Chapter 3's system runs.
The difference hasn't been broken down yet: record what she said is
missing here.

This is a weighted estimate, not a literal average of the table below. The
backend/algorithmic core (Phases 1-3) is the bulk of the manuscript's
technical contribution, and it is done and *executed*, not just coded.

As of 2026-09-29:
- **Both interface prototypes are built:** Figures 2 and 3
  (`src/dashboard/`, notes §3.24). Figure 3's canvas is edited in place:
  select, drag, resize, retype, lock, undo/redo (§3.28).
- **Detector:** YOLO **v5** is deployed (2026-10-06, §3.30), trained on the
  group's 200-image re-annotation. On 32 images neither model trained on:
  mAP50 0.728 vs. v4's 0.486; embellishment recall 0.51 vs. 0.21.
- **GNN:** v3 reads the master's structure, and its output is registered
  to the master's anchors (§3.26).
- **Candidates** differ in layout archetype (§3.27).
- **Colour clustering is seeded** (§3.29). Earlier results carry palette
  noise.

The remaining gap is the human expert MOS validation (Phase 4). Its packet
has to be regenerated with the current system first.

---

## Phase-by-phase breakdown

### Phase 1: Data Extraction and Graph Construction (p. 50-51)

| Component | Manuscript requirement | Status |
|---|---|---|
| K-Means LAB color extraction | Dominant color centroids via K-Means | **Done** — `vision_extraction.py`, `template_ingestor.py` |
| SIFT/SURF stylistic markers | "K-Means and SIFT/SURF algorithms" | **Partial** — only SIFT is actually invoked in code; SURF is named in the manuscript but not implemented. Flagged in `adviser_consultation_checklist.md` section C as a wording-vs-code discrepancy to resolve with adviser |
| Semantic Layout Parsing (YOLOv8 + Tesseract OCR) | Object bounding-box detection + text extraction, converting raster pixels into structured nodes | **Done; v4 deployed 2026-09-29 (notes §3.25).** `layout_extractor.py` runs `themesync_yolo_v4.pt`: YOLOv8s from COCO weights at 1024 px, trained on the 124-image batch with its over-half-poster boxes removed. Validation mAP50 0.454 (v3: 0.363); logo 0.818, text 0.682, underlay 0.115, embellishment 0.201. The automatic logo row is right on 15 of 15 unseen posters. **Pending (group):** re-annotation per `annotation_guidelines.md` v2, then v5 with the same recipe (`finetune_yolo_master_layout.py`; `--check_only` validates the export first). History: §3.6–3.8, 3.12, 3.25 |
| GNN construction + training on CGL-Dataset | GNN maps extracted visual elements into a formal graph, learns hierarchical node-edge dependencies and spatial reasoning baselines | **Done; v3 deployed 2026-09-29 (notes §3.22, §3.26).** v1 was worse than no model (order kept 47%). v2 learned designers' positions from a naive stack. **v3** starts from the master's mapped structure (`structure_mapping.py`, Table 1's `bbox [x, y]` → initial encoding), trained from naive and distorted-structure starts. Held-out (2,900 CGL layouts): position error 0.036 vs. 0.050 for the structure start alone. Its output is registered to the master's anchors, and the anchors hold at `ANCHOR` strength in Cassowary. With exact anchors, the anchored elements are kept and the unmapped ones are placed 8% better than interpolation (`results/gnn_heldout_eval.json`). `themesync_gnn_v3.pth` is the default |
| Stylistic marker extraction (Stage 0c) | "Scale-invariant stylistic markers" (p.51); saliency of the "inpainted background layer" (p.38, Figure 1(b)) | **Done (2026-09-28, notes §3.23)** — `stylistic_markers.py`: text-free background rebuilt from the master's border, motifs (YOLO detections cut out, ranked by SIFT keypoint density; `illustration` detections preferred once v5 exists, §3.25), title artwork (title groups, cut out when they separate cleanly). Title artwork found on 13 of 15 unseen posters, motifs on 8 (after the motif-quality filters) |
| Perceptual Ingestion & Initialization Dashboard (Figure 2) | Interactive UI: master template preview, "Visual DNA" panel (K-Means centroids, SIFT/SURF keypoints, relational node graph, user-injected typography), target-format dropdown, "Initialize Orchestration" button | **Built; rebuilt 2026-09-29 (notes §3.24)** — `src/dashboard/views/ingestion.py`. Everything in the mockup, plus the Stage 0c markers (with ticks and uploads), the logo picker, and an editable content payload. Font family, weight and base size now all drive the renderer's type scale, and typography and content are JSON-Schema-validated before Initialize is allowed. Initialize opens the Figure 3 workspace |

**Phase 1 estimate: ~95%** — done and verified; SURF remains named but not implemented (revision list 3.10).

### Phase 2: CSP Integration and State Synchronization (p. 51-52)

| Component | Manuscript requirement | Status |
|---|---|---|
| Dynamic Node Instantiation | Ingest user's structural schema (JSON payload), assign Baseline Geometric Tensors per Spatial Hierarchy Index | **Done** — `dynamic_instantiation.py` (`NodeInstantiator`) |
| Cassowary Algorithm constraint solver | Primary linear arithmetic constraint solver; bounding boxes adapt to varying aspect ratios without overlap | **Done** — `cassowary_engine.py` (`ConstraintSolverEngine`) |
| Bi-directional State Machine | Serializes project state to JSON; captures manual HITL interventions as hardened constraints, preventing destructive overwrite on automated updates | **Done (2026-09-29)** — `StateChain` (append-only JSON chain, Formula 3.9) + `OrchestrationSession.apply_event` (on-drop / on-resize-complete / lock-toggle re-solve with the adjusted node Hard, Formula 3.10). Retention is measured: moves, resizes and locks are kept exactly through re-solves, no overlap (`evaluate.py`, `test_hard_constraints_preserved`) |
| Pre-orchestration schema validation (p.44) | Typography and payload validated against a rigid schema; a violation rejects the initialization | **Done (2026-09-29)** — `schema_validation.py`, JSON Schema (Draft 2020-12): weight ∈ {100…900}, base size 8 px to 15% of the viewport; each content variable present, within `max_characters` |
| Constraint Editor UI (Figure 3, right panel) | Interactive tab exposing per-node X/Y/W/H, font, and Soft/Hard constraint toggle, plus a visual JSON state timeline | **Built (2026-09-29)** — `src/dashboard/views/orchestration.py`: node selection, X/Y/W/H, font, Soft/Hard, nudges, Apply; State Timeline (JSON Sync) with Restore and download |
| Active canvas (Figure 3, centre) | The design adapted to the target format, where the designer's manual overrides happen (pp.53–54); terminal events only (p.42) | **Built (2026-09-29, notes §3.28)** — `src/dashboard/canvas_editor.*`: click to select (the Constraint Editor follows), drag, resize handles, double-click to retype (schema-validated), arrow nudges, L to lock, Ctrl+Z / Ctrl+Shift+Z (undo/redo append states), snapping to Formula 3.13's grid. The browser only previews; each gesture sends one event. Tested in headless Firefox |

**Phase 2 estimate: ~97%** — implemented, interactive (including editing on the canvas itself), and measured.

### Phase 3: Heuristic Testing and Optimization (p. 52, 55-58)

| Component | Manuscript requirement | Status |
|---|---|---|
| Parallel state-space exploration / candidate generation | Generate multiple layout candidates per run | **Done** — `candidate_generator.py`: six candidates, each a layout archetype (classic, left-aligned, art column, banner, floating card, full-width band) with its own margin, rhythm and motif arrangement (incl. a "hero" motif). Each is solved by Cassowary and scored on its own composed background, with Formulas 3.13–3.14 taken over its own content area (notes §3.27) |
| Heuristic Fitness Function (Formulas 3.11-3.15) | F_layout = α·P_collision + β·P_align + γ·P_whitespace + δ·P_legibility, with legibility cross-referenced against the SIFT/SURF saliency map | **Done** — `optimization_engine.py` (`HeuristicEvaluator`) implements all four penalty terms plus the combined `C_total` score |
| Aesthetic Rendering Pipeline | Projects K-Means color clusters + extracted typography onto generated bounding boxes as a final SVG | **Done** — `aesthetic_renderer.py` + `decor.py`: text-free master background, certificate panel with the title artwork as a watermark, motifs, title artwork on the event ID, WCAG-checked text colours, type scale on the user's base size (2026-09-28) |
| IoU, Latency, F1/Structural Accuracy metrics | Quantify extraction accuracy (Phase 1), algorithmic latency, and constraint-satisfaction F1 | **Done and actually executed** — `evaluate.py` and `experiment_runner.py` implement and compute all three; `results/evaluation_results.json` and `results/experiment_log.json` contain real, already-generated output, not placeholder code |
| Recommendation Engine UI (Figure 3, "Candidate A/B/C" thumbnails) | Tab showing ranked candidate previews for the designer to choose from | **Built (2026-09-29)** — every ranked candidate with its thumbnail and all four penalties; "Use this candidate" makes it the active canvas (a state in the chain) |

**Phase 3 estimate: ~92%** — implemented, run on real posters, UI built. The CNN aesthetic evaluator is still not wired into ranking (revision list 3.11).

*Update 2026-10-06 (notes §3.26, §3.30):* the Phase 3 battery runs the
group's new set of 16 unseen Phase 4 posters × 2 formats × 3 Stage 2
conditions (GNN, mapping only, baseline) with YOLO v5: 96 full runs
(`results/experiment_log.json`, `notebooks/results_analysis.ipynb`).
- **Structure transfer works.** The output is closer to the master than
  the baseline:
  - event IDs: on 15 of 16 (structure error 0.045 vs. 0.117);
  - certificates: on 14 of 16 (0.056 vs. 0.089).
- **Formula 3.11 doesn't see it.**
  - Certificates tie on 15 of 16.
  - On IDs the baseline is slightly better (0.1456 vs. 0.1492), through
    legibility.
- **GNN vs. mapping only:** the same anchors; the GNN moves the unmapped
  elements on 13 of 32 runs. Its gain is shown on held-out data.
- **Reading:** report this as is. Phase 4's blind MOS judges composition.

### Phase 4: Expert Aesthetic Validation (p. 54, 57-58)

| Component | Manuscript requirement | Status |
|---|---|---|
| MOS collection tool | 5-point Likert scale, 3 named dimensions (Visual Hierarchy Preservation, Brand & Typographic Consistency, Constraint & Whitespace Harmony), each scored via Table 2's descriptive rubric, on a randomized sample of outputs | **Built and matches the manuscript (fixed 2026-09-26).** `mos_collector.py` now uses the 3 named parameters verbatim, shows Table 2's full score/rating/description scale to the evaluator (start of session + `?` at any prompt), and presents layouts in a seeded random order (`--sample_size`, `--seed`). Previously implemented a different 4-dimension rubric — found in the 2026-09-15 audit (§3.10), fixed in §3.13 of `gnn_fixes_and_methodology_notes.md`. |
| Actual expert evaluation data | A designated domain expert (professional layout artist/graphic designer) rates a randomized subset of generated outputs | **Not done — 0%.** No MOS results file exists anywhere in `data/processed/` or `results/`. This requires recruiting and running an actual outside expert, which hasn't happened yet |

| Rating set and packet | Outputs compared against the original master layout (p.54) | **Built (2026-09-28).** `phase4_packet.py`: 15 unseen posters × 2 formats × GNN / no-GNN baseline, blind codes, private key, printable packet and score sheet per expert (§3.20). Dashboard page "Phase 4 Evaluation Set" does the same without editing CSVs: event text, logo pick from Stage 0b detections, preview, generate, packets (§3.21). The 15 posters are collected and their details drafted. |

**Phase 4 estimate: ~30%.** The instrument, the rating set, and the packet tooling are ready. No real evaluation data has been collected yet. Remaining:
- the TA's approval of the blind baseline condition, and of 1 vs 3–5 experts;
- the group confirming each poster's details and logos;
- **the set is now 16 new posters** (2026-10-06; manifest drafted, a few
  guesses for the group to confirm, notes §3.30);
- **regenerating the set with the current system:** the key and the
  packet for Mark Joseph Orias (2026-09-28, 23:08–23:09) were built before
  GNN v2/v3, the poster-derived look, the archetypes and the seeded palette
  (§3.29). They must not be printed; the Phase 4 page moves them aside when
  the set is regenerated;
- a colour test print, the expert session, and the import.

---

## Cross-cutting gaps (affect multiple phases)

- **Both dashboards are built** (`streamlit run src/dashboard/app.py`,
  in the `themesync_env` conda environment). Restart the dashboard after
  pulling code changes: Streamlit doesn't hot-reload helper modules.
- **The dashboard is exposed by default.** `streamlit run` binds every
  interface, and on the school server it printed the machine's public
  address. Consider `--server.address 127.0.0.1` plus an SSH tunnel; it
  has no login and holds students' names (notes §3.28).
- **Underlay and embellishment detection remain weak** (v4 mAP50 0.115 and
  0.201; recall 0.10 and 0.18). The re-annotation (guidelines v2) targets
  embellishment/illustration. Already tracked in
  `adviser_consultation_checklist.md` section A.
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

1. Timeline/logistics for recruiting the Phase 4 domain expert, since MOS
   collection can't start until that person is identified — this is the
   only phase with genuinely zero real data behind it.
2. Whether the Phase 3 result (the fitness function can't separate the
   Stage 2 conditions on certificates; the structure error can) is
   reported as is, with the MOS as the deciding measure.

---

**How to use this:** treat the percentages here as directional, not
precise — they're a rough weighting of "how much of what the manuscript
describes actually runs," not a line-count or ticket-count metric. Re-derive
from current code + `results/` state rather than trusting old numbers here
if significant time has passed.
