# ThemeSync — context for Claude Code

CSPC BSCS thesis: *ThemeSync: A Graph-Based Design Orchestration Framework with
Real-Time Constraint Satisfaction and Stateful Refinement*. Group lead:
Guiller Angelo Hermoso, with Rona Mae Quite and Michelle Tercero.

**`manuscript/Manu 0910.1.pdf` is the source of truth** for what the
system is supposed to do. It is the group's Prism revision (2026-10-09), in
the past tense. Search it with
`pdftotext -layout "manuscript/Manu 0910.1.pdf" out.txt`.
- Chapter 3 (Methodology) starts at p.37.
- The 4-phase Research Procedure is pp.55–61.
- Figures 2 and 3 (the dashboard prototypes) are on pp.56 and 59.
- The May PDF (future tense, formerly `Final Manuscript.pdf`) is
  `manuscript/Manu 1905.pdf`. Page numbers elsewhere in this file and in
  notes dated before 2026-10-09 are the May PDF's.
- The group edits the manuscript in Prism. The user uploaded the LaTeX
  again as `manuscript/Thesis Latex/` (2026-10-09). The manuscript chat
  edits those files there, and the user copies them into Prism. Cite the
  PDF's pages, not LaTeX lines, since the lines move. Write every addition
  in the past tense.
- `manuscript/RSC paged.pdf` is the panel's recommendation sheet from the
  May defense, with the group's actions.

Before claiming the code "matches the manuscript", re-read the PDF and the
code; notes go stale.

## Where things stand (2026-10-10)

Read first: `notes/system_development_progress.md`, then the tail of
`notes/gnn_fixes_and_methodology_notes.md`, which is chronological (latest
§3.53).

- **Progress:** the statistics consultant put the project at **70%** after
  a live demo (2026-09-29). Quote that, not the progress file's internal
  ~88%. The 2026-10-09 consultation concluded **"recommended for POD"**
  (user, 2026-10-10).
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
    root) and `EDITOR_CSS` in `components.py`.
  - **Step 2 is laid out like a design tool on one screen** (user's request,
    2026-10-09, §3.38), no longer as p.53–54's two tabs:
    - the canvas centre, with the Recommendation Engine as a strip of
      thumbnails beneath it; a click opens a candidate's details;
    - the right panel holds the selected element (undo, redo, name and
      Soft/Hard, X/Y/W/H, Edit text, Lock), the typography, and a
      collapsed "Canvas details";
    - the top bar's **Timeline** opens the State Timeline as a dialog.
    - The canvas component's own toolbar and footer are hidden
      (`canvas_editor.css`): their buttons remain for the keyboard
      shortcuts, and the panel's Edit text reaches the canvas through
      `canvas_editor.request_edit`.
    - The canvas renders in a shadow DOM: test it with Playwright locators,
      not `document.querySelector`.
  - The top bar is pinned, with Streamlit's » and ⋮ inside it.
  - **Added 2026-10-13, after the evaluation** (§3.53, dev findings I;
    rollback tag `pre-oral-demo`). None changes generation or scoring:
    - a font picker that shows each font in its typeface (Steps 1 and 2),
      over six bundled families;
    - a CSV mail merge: `mail_merge.py`, `OrchestrationSession.merge`,
      a ZIP from Step 2's Download menu;
    - Style tools in Step 2's right panel (`set_style`, event type
      `style`);
    - drop an image on a Step 1 tile to replace it (`background_path` for
      the background).
  - **Step 3:** the evaluated layout is fixed on the left at the window's
    height; the report (intro, headline tiles, cards) scrolls on the right
    in `report_scroll`; the page itself doesn't scroll (§3.39). The
    Visual DNA card draws p.60's K-Means elbow graph (Altair; §3.45).
  - **Step 1 follows the user's mockups A1–A3** (2026-10-09, §3.37) and
    fits one screen with no page scroll:
    - left, the **Master Layout**:
      - A1, before extraction: an upload area, Extract, and the toggle;
      - A2, after: the preview (⤢ full size; ⓘ opens the node graph
        modal; an upload icon replaces the poster), with K-Means and
        SIFT/SURF beneath;
    - right: logos + stylistic markers in one card (tick a tile to use
      it; markers in one row), sized to its contents up to 42% of the
      column; typography in one row; the content payload in two columns,
      taking the rest;
    - **Target Initialization** is a fixed overlay opened from the top
      bar. It moves nothing, and **Initialize** is at its foot (only
      there).
    - Heights come from `--ts-avail` and its parts in `EDITOR_CSS`.
      Check 1780×880 and 1366×768 after changes.
    - Streamlit's markdown blocks carry a −1rem bottom margin. HTML
      blocks in the Step 1 cards and dialogs reset it, or the next
      element overlaps them.
    - It departs from p.51's "central viewport" plus "right-hand panel"
      (§3.36).
  - **Thumbnails go through `ui.thumbs`** (an HTML grid with gaps), not a
    list in `st.image`, which draws them edge to edge.
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
- **Final manuscript: `manuscript/Manu 1210.1.pdf`** (2026-10-12; 111
  pages).
  - Chapter 4 runs pp.76–103, Chapter 5 pp.104–107, the Appendices from
    p.108.
  - **Pre-oral defense: 2026-10-13.**
  - The TA no longer checks the manuscript (from 2026-10-12), so no more
    "for checking" messages.
  - Checked: no PENDING, `??`, "et al." or placeholder text. SURF appears
    only in Chapter 2's literature and a reference title.
  - **Checked against the system** (2026-10-12, dev findings section H):
    ~98% of what it describes runs and is measured. Five wording items
    remain (H1–H5); none changes a result. The main one is H1: manual
    edits survive typography updates, not every "global theme update".
- **Manuscript (2026-10-10):** the latest build was
  `manuscript/Manu 1010.1.pdf`. `manuscript/Thesis Latex/` holds Chapters
  1–5.
  - Everything in the dev findings' section G is applied there,
    uncommitted, for the user to review. That includes the group's
    decisions of 2026-10-10:
    - SIFT only, everywhere (SO1 included);
    - the CNN removed (future work);
    - c_i and s_i described as per-layout values, with a limitation;
    - the certificate printed on US Letter;
    - Figures 2–4 are now the dashboard screenshots, plus five Chapter 4
      figures;
    - the Significance in the past tense;
    - Chapter 5 drafted.
  - **Not done:**
    - the cover month (the user fills it in);
    - the abstract (later);
    - the example-pair figure (left out: licensed cartoon characters).
  - **Prism needs the current `references.bib`,** or new citations print
    as raw keys.
- **Phase 4 is analysed** (2026-10-10, notes §3.48–3.49, handoff D7):
  - **The statistical treatment:** the consultant checks only the
    prototype, so the group adopted the consultation guide's suggested
    answer to all eleven questions (`notes/consultation_guidelines.pdf`).
    `src/evaluation/phase4_analysis.py` implements them. It was committed
    (`b9a60ab`) before the scores were imported; change it only to fix a
    bug, and say so.
  - **The data:** all four experts' sheets are imported into
    `results/mos_results.json` (768 ratings).
  - **The result:** the experts rated the **baseline significantly higher**
    than structure mapping + GNN: overall MOS 3.73 vs 3.33, p_Holm < 0.001,
    r = −0.95. It was mainly on Constraint & Whitespace (3.77 vs 2.92);
    Visual Hierarchy n.s.
  - **Post hoc** (`phase4_posthoc.py`): mapping + GNN leaves larger,
    uneven gaps. Formula 3.11 doesn't measure that.
  - **Reporting:** report it as found; label the conditions "structure
    mapping + GNN" vs "baseline (neither)". The system stays as rated.

## Working rules (from the user)

- **The manuscript is the primary basis** (user, 2026-10-08). Bring the
  system to what it says. Change the manuscript only where that makes the
  system better, and then as little as possible.
- **No thesis prose unless asked.** Notes, findings, evidence tables and
  revision lists are welcome; chapter drafts (Chapter 4, etc.) wait for an
  explicit request.
- **References are in ACM format, and there is never an "et al."**
  (user, 2026-10-09).
  - In the text, name every author, or use a numeric `\cite{}`.
  - In the Notes, `acmnumeric.bbx` truncates after 10 authors, so give a
    longer entry `options = {maxbibnames=99}`. "and others" in an author
    field also prints "et al.".
  - Keep the formatting consistent with Chapters 1–3.
- **Chapters 4 and 5 follow the TSA's guidelines** in
  `manuscript/Learning Materials/`.
  - Chapter 4: per objective, Results (facts only) and then Discussion
    (principal findings, interpretation, context of the literature,
    implications, limitations, summary). Past tense, with no proposal
    language.
  - Chapter 5: Summary, Findings, Conclusions, Recommendations.
  - **The TA's remarks (2026-10-11), applied to the LaTeX:**
    - Chapter 4: one section per objective and nothing else; no separate
      "Evaluation" section (TA, third round: "para saan objective ung
      evaluation?"). Each SO's opening states its own data and setup:
      - SO1: the validation split, the held-out CGL layouts, the 16
        posters, and the three conditions;
      - SO2: the rated layouts, the stress test, and the RTX 3060
        workstation;
      - SO3: the Phase 3 battery on the RTX A5000 server, and the Phase 4
        experts.
      The evaluation-sets table was dropped. Each subsection is a part the objective names,
      titled in its own words in Chapter 3's "Topic (Method)" style.
      Each table or figure is followed by its own Results and PIIILS
      discussion, with one table or figure per page: `\clearpage` before
      each item and `[!ht]` floats like Chapter 3's. Not `[H]`, which
      double-spaced the tables and left a gap under the chapter title. No
      separate Results or Discussion headings. After any edit, recompile
      and check that each item still fits its page.
    - Chapter 4's section headings carry no "Objective #" (TA,
      2026-10-11, second round).
    - Chapter 5: no subsections. **No more findings, conclusions, or
      recommendations than SOs** (TA, second round): three of each,
      numbered, one per SO. Conclusion n comes from Finding n, and
      Recommendation n from Conclusion n.
    - Direct statements, "not AI written": short sentences with one point
      each, few numbers per sentence, no stock connectors.
  - **No hanging lines or gaps in the manuscript** (user, 2026-10-12):
    - `thesis.tex` sets `\widowpenalty`, `\clubpenalty` and
      `\displaywidowpenalty` to 10000. The user adds them in Prism.
    - Chapter 3's Figure 1 floats (`[!ht]`); as `[H]` it left a gap on
      the page before it.
    - Chapter 4 and Chapter 5 pages were filled by extending or
      tightening sentences with real results, not filler.
    - After edits, rebuild and check each page's fill. Chapter ends
      before the Notes may stay short; Chapter 2's last page was left as
      the group wrote it.
- **`notes/manuscript_revision_list.md` tracks the manuscript against the
  code.** It was re-checked against Manu 0910.1 on 2026-10-09: 26 earlier
  items applied, 27 new (M1–M27, including §3.35's open findings and the
  development chat's M22–M26). When the group uploads a newer export,
  re-check it the same way, against the PDF and the code.
- **Two chats share this repo:** this one for the manuscript, another for
  the system. The development chat writes
  `notes/dev_findings_for_manuscript.md`; the manuscript chat writes
  `notes/manuscript_findings_for_dev.md`. Each reads the other's file
  before starting.
- **Commit and push after each set of changes** (user, 2026-10-07), so
  work survives the school server going down.
  - **Except manuscript drafts** (anything under `manuscript/`: the LaTeX,
    chapter drafts, the fix list). Leave them uncommitted; the user checks
    and commits them (user, 2026-10-09).
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
  `gnn_heldout_eval.py`, `evaluate.py`, `yolo_iou.py` (the detector's mean
  IoU, p.62), `stress_test.py` (p.55's extreme payloads; analysis only),
  `latency_benchmark.py` (p.62's edit latency), `rated_layouts_check.py`
  (F1 and text fit of the 64 rated layouts, read-only),
  `r_target_analysis.py` (a master-derived R_target; analysis only),
  `phase4_analysis.py` (the fixed Phase 4 plan; `--simulate` tests it) and
  `phase4_posthoc.py` (exploratory), then re-execute
  `notebooks/results_analysis.ipynb` with `python notebooks/run_notebook.py`
  (needs nbformat, nbclient, ipykernel). It saves every figure to
  `results/figures/` (PNG 300 dpi + PDF); the clean ones for Chapter 4 are
  `fig4_*` (§3.51, handoff F). `weight_calibration.py` is the
  Formula 3.11 weight calibration (item 3.25; analysis only, `--reuse`
  re-analyses the saved runs).

## Gotchas

- **`requirements.txt` is UTF-8 now** (it was UTF-16 until 2026-10-08).
  - It pins the server's torch 2.5.1 / torchvision 0.20.1 and torch's
    sympy 1.13.1, so a CUDA build installed first is kept.
  - torchaudio was dropped: nothing imports it.
  - The other pins come from a different machine. The server's Python is
    3.10.20, with ultralytics 8.4.121.
- **The renderer caches image files** by path, size and modification
  time (`aesthetic_renderer._load_image`, `_background_uri`;
  `decor._decoded`, `_covered`; §3.47). A file rewritten in place is read
  again. The output is byte-identical to the uncached code (checked on the
  64 rated runs and 1,360 edits).
- **Fonts live in `assets/fonts/`** (Montserrat plus five OFL families
  built by `src/renderers/build_fonts.py`; §3.53).
  - Linux reads them through fontconfig.
  - On Windows, Cairo reads fonts through DirectWrite, so `rasterize`
    registers the families Windows lacks for the session at import. It
    skips installed ones, and the first render waits 2 s for DirectWrite.
  - Add a family to `ui.FONTS` and rebuild with the script.
- **Browser tests upload a copy of the poster from outside
  `data/raw/dashboard_uploads/`.** Re-uploading a file from there saves a
  duplicate (`X_hash_hash.jpg`). Delete any that appear.
- **Cairo runs on one thread** (`rasterize.on_cairo_thread`).
  - On Windows, Tesseract's Cairo DLL segfaults when a second thread
    renders, and Streamlit runs every rerun on a new thread. The dashboard
    died on Step 3 (§3.36).
  - Any new cairosvg call must go through `rasterize`.
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
