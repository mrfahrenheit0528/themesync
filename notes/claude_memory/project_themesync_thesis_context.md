---
name: themesync-thesis-context
description: "ThemeSync is a BS Computer Science thesis (CSPC) — codebase must stay consistent with the actual manuscript, \"Final Manuscript.pdf\", found at repo root."
metadata: 
  node_type: memory
  type: project
  originSessionId: f00aab06-eab2-417f-a14e-13e54f10a9af
  modified: 2026-09-28T16:11:58.530Z
---

The `themesync` repo is a Bachelor of Science in Computer Science thesis project at Camarines Sur Polytechnic Colleges (CSPC), titled "ThemeSync: A Graph-Based Design Orchestration Framework with Real-Time Constraint Satisfaction and Stateful Refinement." Authors: Guiller Angelo Hermoso (the user, group lead), Rona Mae Quite, Michelle Tercero. Defense/submission target: May 2026.

**Three distinct committee-adjacent roles — do not conflate them (confirmed 2026-09-22):**
- **TA (Thesis Adviser)** — was their panel from the last title defense; technical/content adviser.
- **TSA (Thesis Subject Adviser)** — a separate, distinct role. Methodology/citation-rigor focused: her first real consultation (reported 2026-09-22, having happened "last week") pushed on whether Table 2's Likert/MOS scale, the 3 named MOS dimensions, and the domain-expert evaluator concept are each "backed with study."
- **Consultant** — separate again, statistics/methodology focus, consults async via Google Chat (confirmed explicitly 2026-09-22).
All three may turn out to consult via Google Chat rather than live meetings — confirmed for TA and consultant so far; TSA's medium not yet confirmed as of this note. See [[project-adviser-consultation-format]].

The actual manuscript lives at `Final Manuscript.pdf` in the repo root — Chapter 1 (Intro) starts p.2, Chapter 2 (RRL) p.16, Chapter 3 (Methodology) p.35, Research Procedure/4-phase plan p.50-58. This is the authoritative source of truth for what the system is *supposed* to do. `pdftotext -layout "Final Manuscript.pdf" out.txt` works well for full-text search across it — much faster than paging through it as images when hunting for a specific claim/citation.

**Before claiming the system "matches the methodology," citing a completion %, or answering a citation/grounding question, re-check the actual PDF text/formulas and the current code — don't trust old audit notes at face value, they go stale fast in an actively-worked project.** Two confirmed examples of this exact trap: (1) an earlier version of this memory claimed K-Means elbow-method k-selection was "specified, not implemented" — true 2026-09-09, false once built (§3.3). (2) `system_development_progress.md` once claimed the MOS collector's dimensions matched the manuscript's 3 named ones — that was asserted without re-reading the actual code, and turned out wrong (§3.10). **Known citation gap (2026-09-22):** the manuscript's *only* citation anywhere for "Mean Opinion Score" is [18] a Twilio marketing-glossary page (Chapter 1, Definition of Terms) — no academic source backs the Likert scale, the 3 MOS dimensions, or the single-domain-expert evaluator methodology yet, and the group's own 124-image annotated master-layout batch isn't mentioned in Chapter 3's prose at all (only CGL-Dataset is described there as a Research Instrument) — likely why TSA is asking. **Citations verified against primary sources 2026-09-28 in `notes/mos_parameter_grounding.md`** (P.800, Likert, O'Donovan 2014, CGL-GAN 2022, RADM/CGL-Dataset V2 2023, Wheeler 2013, Nielsen & Molich 1990), but still NOT added to the manuscript — don't describe them as already cited. That check surfaced a real gap: the manuscript's *single* Phase 4 expert contradicts the very sources that back the method (Nielsen & Molich recommend 3–5 evaluators; both CGL papers used 5 professional + 20 novice designers). A switch to 3–5 experts is pending TA sign-off. Don't cite Nielsen & Molich in support of a single expert.

**Where to look for current state (all in `notes/`, check freshness against git log before relying on any of them):**
- `system_development_progress.md` — phase-by-phase % complete against the manuscript's own 4-phase Research Procedure (p.50-58); read this first for "what's left."
- `adviser_consultation_checklist.md` — meeting-ready list of decisions/questions for the **TA** (sections A: decided without consult, B: open design questions, C: minor follow-ups, D: unaudited).
- `manuscript_revision_list.md` — page-by-page list of what to fix/add in the manuscript (🔴 must fix, 🟡 add, ⏸ blocked on TA). A to-do list, not prose; check it before any manuscript edit.
- `mos_parameter_grounding.md` — verified citations + quotes for Table 2, the 3 MOS parameters, the evaluator count, and CGL-Dataset V2. Use it before answering any "is this backed by study" question.
- `consultant_cheatsheet.md` — Google-Chat-ready message blocks for the **consultant** (not a presentation script — see [[project-adviser-consultation-format]] for why it was revised into that shape).
- `gnn_fixes_and_methodology_notes.md` — the full technical audit trail, numbered fix sections (up to §3.29 as of 2026-09-29). Read the tail end first, it's chronological.
- `annotation_guidelines.md` — v2 (2026-09-29): the group's re-annotation rules (5 classes incl. `illustration`), Roboflow steps, the `--check_only` label check and the v5 training command.
- `notebooks/results_analysis.ipynb` — real charts/tables pulled live from `results/*.json` and `runs/yolo/*/results.csv` (YOLO training curves, GNN-vs-baseline fitness comparison). Re-run it after any new pipeline/training run rather than trusting stale cell outputs.

**Current build state (2026-09-22):** YOLO fine-tuning has gone through 3 stages — v1 (CGL-Dataset only, mAP50 0.539 in-domain) → v2 (65 real annotated posters, held-out mAP50 0.325) → **v3 (124 real posters, held-out mAP50 0.370, current default in `pipeline.py`'s Stage 0b)**. Getting to v3 required fixing a real bug in the newly-exported 124-image batch first: mixed polygon/bbox annotation rows were silently dropping ~23% of images during training, and the class index order had alphabetized differently between exports — both fixed and verified (§3.12) before retraining. `finetune_yolo_master_layout.py` is now parameterized (`--base_checkpoint`/`--output_checkpoint`/`--run_name`) so future batches don't have to overwrite the previous stage's checkpoint/logs. A Streamlit dashboard (`src/dashboard/app.py` router, **must run under the `themesync_env` conda environment**) implements both prototypes as of 2026-09-29: `views/ingestion.py` (Figure 2) and `views/orchestration.py` (Figure 3: Constraint Editor + State Timeline + Recommendation Engine), plus `views/phase4.py`. They sit on `pipeline.OrchestrationSession` (run once, then HITL events append to a JSON `StateChain`; notes §3.24). Stage 0b's detected logo aspect ratio feeds the schema's `lock_aspect_ratio` field (§3.11).

**Decisions from the user on 2026-09-28:**
- **Outputs carry the master poster's look.** The certificate and ID now use a text-free background built from the poster, its decorations as motifs, and its title artwork (Stage 0c, notes §3.23). This lifts the earlier "no motif/wordmark transfer yet" deferral.
- **The GNN was retrained properly.** v1 was degenerate (train/inference mismatch). `themesync_gnn_v2.pth` is now the default (notes §3.22). v1 is kept only as the "before" in Chapter 4.

The Phase 4 key and the packet the group built on 2026-09-28 at 23:09 (for Mark Joseph Orias) predate these changes and must be regenerated before printing.

**2026-10-06:** the group re-annotated **200** master layouts (kept 4 classes, no `illustration`). YOLO **v5** trained on them is now deployed (notes §3.30); its export needed `prepare_master_layout_dataset.py` (polygon rows). Phase 4 now uses **16 new posters** (PUP_FORUM, a training image, was replaced by DEAR_SENDER and SHARE_KO_LANG; all 16 verified unseen). I drafted their `manifest.csv` from the posters on 2026-10-06; the group should confirm the flagged guesses.

**Consultant's progress assessment (2026-09-29, after a live demo of the dashboard): 70% complete.** Use this over the internal ~88% in `system_development_progress.md` when citing progress.

**Decisions and state from 2026-09-29 (notes §3.25–3.29):**
- **Deployed models:** YOLO **v4** (YOLOv8s from COCO, 1024 px, cleaned labels; not CGL-pretrained, so don't write "pretrained on CGL" for the deployed detector) and GNN **v3** (trained from naive + distorted-structure starts).
- **GNN inputs:** the GNN now receives the master's structure (`structure_mapping.py`). Its output is registered to the master's anchors, and anchors hold at `ANCHOR` strength in Cassowary. The mapping transfers the composition; the GNN places the unmapped elements. Held-out evidence is in `results/gnn_heldout_eval.json` (`exact_anchors`).
- **Re-annotation:** the user chose it. The group re-annotates in Roboflow per `notes/annotation_guidelines.md` v2 (new `illustration` class, no over-half boxes). v5 is then trained with v4's recipe. Pending on the group.
- **Canvas editor:** the user chose "all of that plus text editing". The Figure 3 canvas is edited in place (`src/dashboard/canvas_editor.*`: drag/resize/retype/lock/undo), verified in headless Firefox. Streamlit doesn't hot-reload helper modules, so restart the dashboard after code changes.
- **Colour clustering was unseeded before 2026-09-29:** earlier results and packets carry palette noise (§3.29).
- **Dashboard exposure:** `streamlit run` binds all interfaces; on the school server it printed the machine's public IP. Recommended `--server.address 127.0.0.1` plus an SSH tunnel. Not changed without the group's decision.

**The "ID" format is an event ID (lanyard pass), not a student ID card (user, 2026-09-28).** The certificate layout is standard and fine as is. The group's real IDs, 18 of them in `data/raw/ID_layouts/`, are CSPC event passes: logo row, event title, name (often a nickname), and a role such as ORGANIZER. They have no photo, student number or barcode. The template was rebuilt to match (notes §3.15). The manuscript still says "Student Identification Cards" (pp.48/49/54), so that wording is pending in the revision list. Judge rendered output only with cairosvg (installed in themesync_env): ImageMagick's built-in SVG renderer distorts letter-spacing.

**Why the "code changes with thesis-structure implications" distinction matters:** a change to a named/described component (e.g. AAPA's diversity mechanism) generally needs Chapter 1/3 revision, not just a Chapter 4 footnote, whereas a bug fix that makes an already-described mechanism work as intended stays in Chapter 4 / the audit notes above. **Manuscript prose itself (any chapter, not just Ch4) is not edited without an explicit ask** — see [[wait-for-thesis-draft-command]].
