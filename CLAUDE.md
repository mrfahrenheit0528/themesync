# ThemeSync — context for Claude Code

CSPC BSCS thesis: *ThemeSync: A Graph-Based Design Orchestration Framework with
Real-Time Constraint Satisfaction and Stateful Refinement*. Group lead:
Guiller Angelo Hermoso, with Rona Mae Quite and Michelle Tercero.

**`Final Manuscript.pdf` is the source of truth** for what the system is
supposed to do. Search it with `pdftotext -layout "Final Manuscript.pdf" out.txt`.
- Chapter 3 (Methodology) starts at p.35.
- The 4-phase Research Procedure is pp.50–58.
- Figures 2 and 3 (the dashboard prototypes) are on pp.51 and 53.
- **The repo's PDF is the May 2026 version, in the future tense.** The
  group revises the manuscript in Prism and has converted it to the past
  tense (2026-10-08). Its content still rules, but its wording and page
  numbers may differ from the PDF. Advise past tense for every addition,
  and ask for an export of the revised version before quoting it exactly.

Before claiming the code "matches the manuscript", re-read the PDF and the
code; notes go stale.

## Where things stand (2026-10-08)

Read first: `notes/system_development_progress.md`, then the tail of
`notes/gnn_fixes_and_methodology_notes.md`, which is chronological (latest
§3.35).

- **Progress:** the statistics consultant put the project at **70%** after
  a live demo (2026-09-29). Quote that, not the progress file's internal
  ~88%.
- **Deployed:** YOLO **v5** (`themesync_yolo_v5.pt`) and GNN **v3**
  (`themesync_gnn_v3.pth`). The pipeline picks the newest checkpoint in the
  repo root.
  - v5 is trained on the group's 200-image re-annotation, with v4's recipe:
    COCO YOLOv8s at 1024 px.
  - The deployed detector is **not** CGL-pretrained, so don't write that it
    is. CGL-Dataset V2 trains only the GNN.
- **Stage 2:**
  - The master poster's structure (logo row, header, title, details) is
    mapped onto the target. The GNN's output is registered to those
    anchors, which hold at `ANCHOR` strength in Cassowary.
  - Each output's layout type follows the poster's composition
    (`structure_mapping.master_composition` / `archetype_for`): left-aligned
    text, a large artwork beside the text, text on a panel, or a footer
    band. Formula 3.11 still scores every candidate.
- **Dashboard:** three steps, one at a time (the consultant's remark):
  Step 1 Figure 2 → Step 2 Figure 3 → Step 3 Evaluation Report on the
  user's layout (`views/report.py`, `src/evaluation/layout_report.py`,
  notes §3.32). Phase 4 sits apart under "Research tools". Figure 3's
  canvas is edited in place (`src/dashboard/canvas_editor.*`).
  - **Laid out like Canva, in ThemeSync's own colours** (§3.34): a navy
    bar and a coral accent, not Canva's gradient or purple (user's
    request). See `.streamlit/config.toml` (start Streamlit from the repo
    root) and `EDITOR_CSS` in `components.py`. Keep p.53–54's arrangement:
    canvas centre, the two tabs on the right.
  - The top bar is pinned, with Streamlit's » and ⋮ inside it. Steps 1
    and 3 are bento grids of `card_*` containers: master/preview on the
    left (kept in view), cards on the right (p.51's "right-hand panel").
- **Phase 4:**
  - 16 unseen posters are in `data/raw/phase4_posters/` with
    `manifest.csv`, which Claude drafted from the posters. Unconfirmed
    guesses:
    - ANTI_HAZING's university;
    - CMET's year;
    - "DEBESMSCAT" as the acronym for GUESS_THE_TEACHER;
    - blank dates on DEAR_SENDER, LUCKY_TERA and SHARE_KO_LANG.
  - Manifest overrides: `title_artwork` = no for CMET and
    SIGN_LANGUAGE_DAY.
    - **ANTI_HAZING_LAW's overrides were lost before the rated set was
      generated** (notes §3.35). Its four rated pages carry the "CLOSED"
      stamp as a decoration and the title cut with the statue across
      "GENDER".
    - **Leave its row blank.** The manifest now records what was rated,
      and `weight_calibration.py` regenerates the rated runs from it.
  - **Packets went out on 2026-10-07** to four experts, all built from that
    day's key (14:43, after the layout-type and motif fixes, except
    ANTI_HAZING_LAW's overrides): Eisen Rose D. Galvante, Kyz Denise
    Aquino, Mark Joseph Orias and Mark Kenneth C. Ellorde.
    - Eisen's packet is `packets/Eisen_Rose_D_Galvente/` (misspelled
      folder; the correctly spelled duplicate was never sent and was
      deleted). Import it with `--evaluator "Eisen Rose D. Galvante"`.
    - Each expert's scores go into the `scores_<name>.csv` in their packet
      folder; its rows follow that packet's page order.
  - The group went ahead without the TA: four experts and the blind no-GNN
    baseline (revision-list items 1.3, 3.7 and 3.8 updated).
  - The rated layouts come from the code at commit `8422282`. **The
    experts won't re-score** (no time; user, 2026-10-08), so keep layout
    generation and the fitness weights (α–δ) as they are. A change there
    would mean the MOS rates a system that no longer exists. Run anything
    that would change them (e.g. the weight calibration, item 3.25) as an
    analysis only.
- **Consultant's remarks** (received 2026-10-07) and their status are in
  `notes/system_development_progress.md`. All three are done: the steps
  (§3.32), a report on the user's layout (§3.32), the dataset (v5).
- **Waiting on the consultant's answers** from the 2026-10-09 statistics
  consultation (the answer sheet in `notes/consultation_guidelines.pdf`).
  If the user hasn't sent them, remind them. They decide item 3.9 and the
  Phase 4 analysis script; don't pick the tests before they arrive.
- **Waiting on:** the expert scores. The user will upload all four at
  once (the first expert's arrived 2026-10-07). Import them with
  `mos_collector.py --import_scores … --key data/phase4/phase4_key.csv`.

## Working rules (from the user)

- **The manuscript is the primary basis** (user, 2026-10-08). Bring the
  system to what it says. Change the manuscript only where that makes the
  system better, and then as little as possible.
- **No thesis prose unless asked.** Notes, findings, evidence tables and
  revision lists are welcome; chapter drafts (Chapter 4, etc.) wait for an
  explicit request.
- **Don't update `notes/manuscript_revision_list.md` until the revised
  manuscript is in the repo** (user, 2026-10-08). The group will upload
  the Prism version. Until then, record new findings in the notes
  (§3.35 holds five).
- **Commit and push after each set of changes** (user, 2026-10-07), so
  work survives the school server going down.
  - The server's push uses the user's token, cached for a day
    (`credential.helper cache`). If the push asks for a password, tell the
    user to push.
  - Regenerable output (`data/rendered/`, `data/processed/Candidate_*.json`)
    is git-ignored, so commits stay small.
- **"Run the dashboard" means start it and hand over the URL.** No
  unrequested test drives or debugging; mention anything broken in one
  line and offer.
- **Consultations happen over Google Chat** with the TA (thesis adviser),
  the TSA (thesis subject adviser, methodology and citation rigour) and
  the statistics consultant. Prepare chat-ready message text, not meeting
  scripts. Don't conflate the three roles.
- **Never print or share `data/phase4/phase4_key.csv`** with the experts.
  It keeps the rating blind.
- **`data/raw/ID_layouts/`** (18 sample IDs with real people's photos)
  stays out of git.
- **Phase 4 posters must be unseen:** check them with
  `src/evaluation/poster_overlap.py`, or `phase4_packet.py template`
  warns.
- **The "ID" format is an event ID (lanyard pass)**, not a student ID. The
  manuscript still says "Student Identification Cards"; that's a pending
  revision.
- **Judge rendered output with cairosvg** (`src/renderers/rasterize.py`,
  bundled Montserrat), not ImageMagick.

## Running it

See `README.md`. In short:

```bash
conda activate themesync_env
streamlit run src/dashboard/app.py --server.address 127.0.0.1 --server.port 8502
```

- **Restart the dashboard after code changes.** Streamlit doesn't reload
  helper modules (`pipeline.py`, `phase4_packet.py`, …), and a stale
  process gives errors like "module 'phase4_packet' has no attribute …".
- **Tests:** `python tests/test_certificate_pipeline.py`,
  `python tests/test_id_pipeline.py` (12 tests).
- **The user's Windows checkout has its own `.venv`** (2026-10-08; README
  "Setting up on Windows").
  - It has Python 3.12, torch 2.5.1+cu121 on an RTX 3060, and
    `requirements.txt`. Cairo comes from Tesseract's folder on PATH.
  - Run with `PYTHONUTF8=1`: 48 text `open()` calls in `src/` rely on
    the default encoding, and Windows' cp1252 can't write the pipeline
    log's ✔.
  - The 12 tests pass there, and the dashboard runs.
  - 20 regenerated Phase 4 pages matched the server's winners and
    C_total. A few GNN-placed boxes differed by up to 13 px, a GPU-level
    rounding difference.
  - Results of record (the Phase 3 battery, Chapter 4, Phase 4) still
    come from the server.
- **Results:** `experiment_runner.py` (the Phase 3 battery),
  `gnn_heldout_eval.py`, `evaluate.py`, then re-execute
  `notebooks/results_analysis.ipynb`. `weight_calibration.py` is the
  Formula 3.11 weight calibration (item 3.25; analysis only, `--reuse`
  re-analyses the saved runs).

## Gotchas

- **`requirements.txt` is UTF-8 now** (it was UTF-16 until 2026-10-08).
  - It pins the server's torch 2.5.1 / torchvision 0.20.1 and torch's
    sympy 1.13.1, so a CUDA build installed first is kept.
  - torchaudio was dropped: nothing imports it.
  - The other pins come from a different machine. The server's Python is
    3.10.20, with ultralytics 8.4.121.
- **cairosvg needs the Cairo library.** On Windows, UB Mannheim's
  Tesseract ships `libcairo-2.dll`: put its folder on PATH. Elsewhere,
  use conda-forge: `conda install -c conda-forge cairosvg`.
- **Roboflow exports mix polygon and box rows,** and Ultralytics silently
  drops those files. Always run
  `src/data_preprocessing/prepare_master_layout_dataset.py` and
  `finetune_yolo_master_layout.py --check_only`.
- **Train detectors to `*_candidate.pt`.** The pipeline adopts
  `themesync_yolo_vN.pt` as soon as it exists; compare first with
  `src/evaluation/yolo_compare.py`.
- **The school server's `/home` disk fills up** (shared by all users). On
  2026-10-07 it hit 0 bytes free and the dashboard failed to save state
  ("No space left on device"), and again that evening. Check `df -h /home`.
  Already cleared: pip and conda caches, the raw CGL download in
  `~/.cache/huggingface`, and (at the user's request) `~/Hermoso` (old
  coursework) and `~/nltk_data`.
- **Not in git:**
  - generated output (`data/rendered/` etc.); regenerate it;
  - the CGL dataset (`data/processed/cgl_tensor_dataset`, 2.8 GB). Only
    GNN training and `gnn_heldout_eval.py` need it;
  - the symlinked training copies `data/processed/yolo_master_v4/v5`.
    Rebuild them with the prepare script.
- **Stage 0 K-Means is seeded** (notes §3.29). Results from before
  2026-09-29 carry palette noise.

## Memory carried over from the server

Claude's saved notes from the server are in `notes/claude_memory/`.
`CLAUDE.md` already covers what matters; those files are the originals.
