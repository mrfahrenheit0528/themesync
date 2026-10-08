# Manuscript Revision List: What to Fix and Add

Every place where `Final Manuscript.pdf` needs to change so it matches what
was actually built, or answers a grounding question. Each item gives the
page, what the manuscript says now, what's wrong, and what to change.

This is a **to-do list, not draft prose.** Wording drafts get written only
when asked for explicitly.

- Page numbers are the manuscript's printed page numbers.
- Checked against the PDF text on 2026-09-28. Chapter 3 was re-read
  against the code on 2026-10-07, which added items 3.24–3.29, and every
  item's page numbers were re-checked against the PDF (six were off). The
  PDF itself is unchanged since May, so no item has been applied yet.
- **The working manuscript is now in Prism** (user, 2026-10-08), and the
  group has converted it to the **past tense**. Quotes here come from the
  May PDF's future tense ("will be calibrated" is now "were calibrated"),
  and page numbers may have shifted. Search the revised text for the key
  phrase, not the exact sentence. Write every addition in the past tense.

**Legend:**
- 🔴 **Must fix.** Wrong, contradicts the code, or a missing citation the
  TSA already asked about.
- 🟡 **Should add.** Missing documentation of something that exists.
- ⏸ **Blocked.** Waiting on a TA decision; do not edit until she answers.
- ✅ **Resolved.** Fixed in the code; Chapters 1–3 need no change (Chapter 4 may).

**Source notes:**
- `mos_parameter_grounding.md`: verified citations and quotes.
- `gnn_fixes_and_methodology_notes.md`: code-side evidence (§ numbers
  below).
- `adviser_consultation_checklist.md`: the open decisions.

---

## Chapter 1: Introduction

### 1.1 🔴 MOS definition cites a Twilio glossary page (Definition of Terms, p.11, ref. [18])

**Now:** "A standardized, quantitative measure used to evaluate the
subjective quality … by human experts [18]." Here [18] is *Twilio. 2026.
What is a mean opinion score (mos)?*, a marketing glossary.

**Fix:**
- Cite ITU-T Recommendation P.800 (1996). It is the standard that defines
  MOS.
- Keep or drop Twilio as you prefer, but P.800 has to be there.

### 1.2 🔴 The MOS definition names different criteria than Chapter 3 (p.11)

**Now:** MOS is "utilized by the layout expert to mathematically grade the
*aesthetic validity, visual hierarchy, and brand compliance*."

**Problem:** Chapter 3 (p.57) names the three parameters *Visual Hierarchy
Preservation*, *Brand and Typographic Consistency* and *Constraint and
Whitespace Harmony*. "Aesthetic validity" isn't one of them, and
constraint/whitespace is missing.

**Fix:** reword the definition to name Chapter 3's three parameters exactly.

### 1.3 ⏸ "A human domain expert" (singular), p.8 and the Definition of Terms (p.11)

**Now:**
- p.8: "evaluated by a human domain expert (a professional layout
  artist)."
- The MOS definition says "the layout expert."

**Decided (2026-10-07):** the group went ahead with four experts (see Ch3
item 3.7). Pluralize both places.

---

## Chapter 2: Review of Related Literature

### 2.1 🟡 Optional: add the layout-quality literature behind the MOS parameters

**Now:**
- Chapter 2 already cites Xu, Zhou, Ge & Xu [2026] (ref. [36]) for the
  R_shm occlusion metric.
- It doesn't cite the design-principle sources behind the MOS parameters.

**Add, if the TA or TSA wants them in the RRL rather than only in
Chapter 3:**
- O'Donovan, Agarwala & Hertzmann (2014), energy-based layout model with
  hierarchy/emphasis, white-space and overlap terms.
- Zhou et al. (2022), CGL-GAN: the original CGL-Dataset, its 4-class
  taxonomy, and a designer user study.

Neither is strictly required in Chapter 2. Chapter 3 is where the TSA
asked for grounding.

---

## Chapter 3: Methodology

### 3.1 🔴 CGL-Dataset V2 is named but never cited (pp.45–46, "Training Data and Feature Mapping")

**Now:** "the framework will utilize the CGL-Dataset V2, hosted on the
Hugging Face repository, as its primary offline training corpus. This
dataset contains thousands of annotated graphic design layouts…"

**Fix:**
- Cite Li et al. (2023), CIKM '23, the source of CGL-Dataset V2.
- Cite Zhou et al. (2022), IJCAI-22, the original CGL-Dataset that V2
  extends.
- Optionally replace "thousands" with the real figures: **60,548 training
  and 1,035 test posters, 4 element classes (logo, text, underlay,
  embellishment)**, from the RADM paper.

### 3.2 🟡 New Research Instrument: the 200-image master-layout dataset (between "Training Data and Feature Mapping" and "Synthetic Administrative Templates", p.49)

**Now:** "Research Instruments and Data Gathering" (pp.45–50) lists only
CGL-Dataset V2 and the synthetic certificate/ID templates. The group's own
annotated dataset is not mentioned anywhere in the manuscript.

**Why it's needed:**
- It exists, and it trained the YOLOv8 model the system actually uses.
- It was sent for expert validation.
- The TSA asked what backs the dataset.

**Where and how (user's question, 2026-10-08):** in Chapter 3, under
Research Instruments, in the past tense like the rest of the revised
manuscript. What the dataset *is* can stay in the present tense ("The
dataset consists of…"). Its results (v4 → v5, mean IoU) belong in
Chapter 4.

**Add a subsection covering:**
- **Purpose:** the Stage 0b YOLOv8 model trained only on CGL-Dataset V2
  didn't transfer to real master layouts (top confidence 0.03–0.11 on real
  CSPC posters, §3.5–3.7). Real branded designs are needed for fine-tuning.
- **Source and scope:** 200 real event-poster/branding master layouts
  (re-annotated 2026-10; it was 124 before)
  (a "master layout" is any generic branded design a user uploads). State
  where the images came from and the permission/usage basis. **Fill this
  in; it isn't in the notes.**
- **Annotation protocol:**
  - Roboflow, bounding boxes only.
  - The 4 classes reuse CGL-Dataset's taxonomy (Zhou et al. 2022).
  - Written guidelines: `notes/annotation_guidelines.md`.
  - Who annotated, and the cross-checking between annotators.
- **Split:** 160 train / 40 validation (80/20).
- **Quality control:**
  - Export checks: mixed polygon/box rows and a class-index reorder were
    found and fixed before training (§3.12). The 200-image export had the
    polygon problem again; `prepare_master_layout_dataset.py` converts
    them, and it drops boxes covering over half a poster (§3.30).
  - Independent expert validation of a 15-image sample against the class
    definitions (`notes/annotation_validation_reference.md`).
- **How it's used:** it trains the deployed detector.
  - v2 (65 images) and v3 (124) continued fine-tuning the CGL-pretrained
    YOLOv8n.
  - **v4** (deployed 2026-09-29 to 10-06) was YOLOv8s from COCO weights,
    trained at 1024 px on the 124 images, with the 60 over-half-poster
    boxes removed (notes §3.25).
  - The deployed **v5** is the same recipe on the 200-image
    re-annotation (notes §3.30). It kept CGL's 4 classes, so no extension
    of the taxonomy needs describing.

### 3.3 🟡 Phase 1 YOLOv8 text doesn't say what the detector is trained on (p.50)

**Now:** "Semantic Layout Parsing utilizing YOLOv8 for object bounding box
detection and Tesseract OCR…" There is no training-data statement for
YOLOv8, while the GNN's is stated ("trained using the CGL-Dataset").

**Add one sentence** stating what the deployed detector is (v5, updated
2026-10-08, notes §3.30): YOLOv8s initialised from COCO weights and trained
at 1024 px on the master-layout dataset from item 3.2.

- **Don't write "pretrained on CGL-Dataset V2".** That was v1–v3.
  - CGL pretraining didn't transfer to real posters (top confidence
    0.03–0.11, §3.5).
  - The deployed v5 doesn't use it.
  - CGL-Dataset V2 remains the **GNN's** training corpus.
- **Optionally:** the v4 → v5 gain (mAP50 0.486 → 0.728 on 32 validation
  images neither trained on) is a Chapter 4 result, not Chapter 3.

**Consider also:** Figure 2's "Affine scaling" readout is now real. The
detected logo's aspect ratio locks the certificate/ID logo's proportions
(§3.11). No text change is needed unless you want to describe it.

### 3.4 🟡 Name the dataset IoU is measured on (p.55, "Intersection over Union")

**Now:** IoU, confined to Phase 1, compares YOLOv8's predicted boxes with
"the ground-truth annotations established in the baseline dataset." The
manuscript calls CGL-Dataset "the baseline training dataset" (p.40) and
says it "establishes the baseline spatial intelligence" (p.48), so a
reader takes p.55's "baseline dataset" to be CGL-Dataset.

**System:**
- The deployed detector, v5 (`themesync_yolo_v5.pt`), was trained only on
  the group's master-layout dataset (item 3.2): 160 training images, 40
  held out for validation. It never saw CGL-Dataset (item 3.3).
- Its accuracy is reported so far as mAP50: 0.728 on the 32 validation
  images v4 never saw either (notes §3.30). No IoU has been computed.

**Decision (user, 2026-10-08):** keep IoU as p.55 defines it.

**Fix:**
- **Manuscript, one phrase:** replace "the baseline dataset" with the
  master-layout dataset's held-out validation split (40 images). The rest
  of p.55 stays.
- **Code (not written yet):** a script that runs v5 on the 40 validation
  images, pairs each predicted box with its ground-truth box of the same
  class, and averages overlap ÷ union, per class and overall. It doesn't
  change the system.
- **Chapter 4:** report the mean IoU. mAP50 can follow in one sentence:
  mean IoU covers only the elements YOLO found, while mAP also counts the
  ones it missed. Chapter 3 needn't mention mAP.

Measuring on CGL-Dataset instead would leave p.55 untouched, but v5 never
trained on it, and its posters aren't the event posters the system takes
in. The number wouldn't describe the deployed detector.

### 3.5 🔴 MOS parameters have no citation (p.57)

**Now:** the three parameters are listed with definitions and no source.

**Fix:** cite each one, using the quotes in `mos_parameter_grounding.md`
§2.

| Parameter | Cite |
|---|---|
| Visual Hierarchy Preservation | O'Donovan et al. 2014 ("Emphasis") |
| Brand and Typographic Consistency | Wheeler 2013, p.29 ("Coherence") |
| Constraint and Whitespace Harmony | O'Donovan et al. 2014 ("White Space", "Overlap and Boundaries") + Zhou et al. 2022 |

**Also worth one sentence:** each parameter is the human counterpart of a
computed component. Hierarchy sizing, the Visual DNA, and Formulas 12/14
all score layouts mathematically; MOS checks that they also look right.
p.58 already implies this ("mathematically confirming that the system's
heuristic constraint solvers successfully translate…").

### 3.6 🔴 Table 2 has no source (p.58)

**Now:** "Table 2: Mean Opinion Score Rating Scale for Aesthetic
Alignment," with no citation. The text calls it a "structured 5-point
Likert scale."

**Fix:**
- State that Table 2 is *adapted from the ITU-T P.800 Absolute Category
  Rating scale* (Excellent 5 / Good 4 / Fair 3 / Poor 2 / Bad 1).
  - Say that "Fair" → "Acceptable" and "Bad" → "Fail" were renamed, and
    that design-specific descriptions were added.
- Cite Likert (1932) for the 5-point ordinal format.
- Optionally change "Likert scale" to "Likert-type rating scale." Likert's
  original is an agreement scale; Table 2 is a quality scale.

### 3.7 ⏸ Single evaluator vs. 3–5 (p.54 Phase 4, p.55 Evaluation Metrics, p.57 MOS)

**Now:**
- "A designated domain expert" (p.54).
- "a human domain expert" (p.55).
- "the designated layout expert" (p.57).

**Problem:** the sources that back the method all use several raters:
- Nielsen & Molich (1990): individual evaluators find only 20–51% of
  problems; aggregates of 3–5 do well.
- Both CGL-Dataset papers: 5 professional + 20 novice designers.

Citing them for one expert contradicts them.

**Decided (2026-10-07):** the group went ahead without the TA's answer;
packets went to **four experts**. To write in:
- Pluralize the evaluator to four professional designers.
- Keep the qualification criterion ("documented industry experience").
- Cite Nielsen & Molich 1990 and the CGL-GAN/RADM protocol.
- Add inter-rater agreement to the statistical treatment (item 3.9).

### 3.7b 🔴 "Student Identification Cards" → event identification cards (pp.48, 49, 54)

**Now:**
- p.48: "Identification Cards and Academic Certificates."
- p.49: "specifically Academic Certificates and Student Identification
  Cards."
- p.54: "the synthetic Academic Certificates and Student Identification
  Cards."

**Why it changed:** the group's actual ID target is the event lanyard
pass, not a student ID card. Evidence: 18 real CSPC event IDs in
`data/raw/ID_layouts/` have a logo row, event title, name and role, and
0–1 of them have a student number, barcode or course (notes §3.15). The
system now generates that format.

**Fix:**
- Reword those three places to event identification cards / event IDs.
- Optionally describe the ID's fields and A6 proportion alongside the
  existing certificate description.
- p.6 ("school-wide materials such as IDs, certificates, and posters")
  can stay as is.

**Tell the TA.** It narrows the ID format rather than adding scope, but
it changes wording she has already read.

### 3.7c 🟡 Optional: name the vertical-balance rule among Cassowary's soft constraints (p.39)

**Now:** p.39 says soft constraints are "standard design rules (e.g.,
default margins)." The solver now also applies an equal top/bottom margin
("vertical balance") soft constraint (notes §3.16).

**Fix (optional):** add it to the examples, e.g. "default margins and
balanced vertical margins." This isn't strictly required, since it is
already covered by "standard design rules." It's worth it only if the TA
wants every soft constraint named.

### 3.8 🔴 Phase 4 sampling and design aren't specified, and a baseline condition was added (p.54, p.57)

**Now:** "a randomized subset of the algorithmically generated multi-format
layouts" and "a randomized sample." No size, no source, no comparison
condition.

**What the group decided (notes §3.20), to write into Chapter 3:**
- 16 unseen master layouts (event pubmats not used in YOLO training) × 2
  formats × 2 conditions = 64 layouts, rated by four experts (15 and 60
  in the first design).
- **New: a blind no-GNN baseline condition.** The same posters and
  content, with the GNN turned off, are mixed into the packet unlabelled.
  This lets Phase 4 compare GNN-guided and baseline outputs as rated by a
  human, not only by the fitness function (which currently favours the
  baseline by alignment alone; notes §3.19). It *adds* to the manuscript's
  Phase 4, so the TA should approve it.
- Printed packet, with each page showing the master layout next to the
  generated layout, since p.54 already says the expert compares against
  the master layout. Random sample codes, page order randomized per
  expert, same-poster pages never adjacent.
- Cite the 60-layout size to CGL-GAN/RADM's user studies (60 random test
  images).

### 3.9 🔴 The promised statistical treatment doesn't exist (p.45 "Materials and Evaluation Methods" → pp.55–58)

**Now:** p.45 promises "the targeted sampling techniques" and "the precise
statistical tools and overarching evaluation methods." The Evaluation
Metrics section (pp.55–58) defines IoU, latency, the fitness function and
MOS, but no statistical tools (§3.10 audit, 2026-09-15).

**Add a short "Statistical Treatment" part covering:**
- MOS: the mean per parameter and overall, with SD. P.800 defines MOS as
  the arithmetic mean.
- If item 3.7 is approved, inter-rater agreement (Kendall's W or ICC). The
  consultant can pick.
- GNN-guided vs. baseline fitness comparison: the test used on
  `experiment_log.json`.
- Detection: mean IoU (item 3.4).
- GNN vs. baseline MOS (item 3.8): a paired comparison per poster and
  format, e.g. a Wilcoxon signed-rank test (ordinal data, paired
  samples). Confirm the choice with the consultant.

This is also where the consultant (statistics focus) is most likely to
push, so it's worth confirming with her.

### 3.10 ⏸ SIFT **and** SURF vs. SIFT only (p.37 "Stylistic Marker Identification", p.40 Formula text, p.50)

**Now:** SIFT/SURF throughout.

**Code:** only SIFT is invoked. SURF is patent-encumbered and absent from
standard OpenCV builds.

**Blocked on the TA** (checklist C): reword to "SIFT", or add SURF to the
code.

### 3.11 ⏸ CNN aesthetic evaluator (p.36, "Theorems, Algorithms…")

**Now:** "Convolutional Neural Networks (CNN) deployed for quantitative
aesthetic evaluation."

**Code:**
- A CNN exists (`aesthetic_cnn.py`).
- It is trained by *distillation from the heuristic fitness function*,
  since no human labels exist yet.
- It isn't wired into ranking.

**Blocked on the TA** (checklist B): whether the manuscript should describe
the distillation approach, or treat retraining on MOS as future work.

### 3.12 ⏸ Appendix A per-node features vs. the GNN training pipeline (p.66)

**Now:** Appendix A shows each node with its own `node_id`, color
centroids, saliency weight and `text_features`.

**Code:** training broadcasts one global color and one global saliency
value into every node. There is no `node_id`, and `text_features` is
dropped (§3.10 Finding 3).

**Blocked on the TA** (checklist B): fix the code, or revise Appendix A and
report it as a limitation.

### 3.13 🟡 Say what the GNN is trained to predict (pp.39–41; Phase 1, p.51)

**Now:** the architecture is fully specified (Formulas 3.6–3.8), but not
the training objective. "Trained using the CGL-Dataset" is all the reader
gets.

**Code (v2, notes §3.22):**
- **Input:** each layout's logo and text elements start from a naive stack
  (centred, stacked in reading order). This is Formula 3.6's (x_i, y_i) at
  both training and inference, and exactly the arrangement the no-GNN
  baseline builds.
- **Target:** designers' real CGL positions (Smooth-L1), plus the offsets
  between consecutive elements, plus the fitness function's collision and
  in-bounds terms as regularisers.
- **Validation split:** a seeded 5% of CGL train is held out (CGL's own
  test split carries no annotations).

**Add:** two or three sentences stating this, and the held-out result
(position error 0.121 vs. 0.175 for the naive stack; gap error 0.074
vs. 0.077). Don't mention v1 in Chapter 3; it belongs in Chapter 4.

**Updated 2026-09-29 (v3, notes §3.26): the deployed GNN's input is the
master's structure, so the sentences should say:**
- **Input:**
  - The target's elements that have a counterpart on the master (logo
    row, header, and on the event ID also title and details) start where
    the counterpart sits.
  - The rest start in reading order between them.
  - Without a master, the naive stack as before.
- **Training:** CGL layouts from both starts. The structure start is a
  layout's own positions, distorted the way a cross-format mapping
  distorts them.
- **Output:** registered to the master's anchors. The mapped elements keep
  the master's positions, and the GNN places the others between them.
- **Held-out numbers:**
  - Position error 0.036 vs. 0.050 for the structure start alone.
  - With exact anchors, unmapped elements 0.075 vs. 0.081 for
    interpolation.

### 3.14 🟡 Stylistic markers: say what is extracted and where it goes (p.37 "Stylistic Marker Identification"; p.51 Phase 1; p.52 Phase 3)

**Now:**
- p.37: SIFT recognises the logo, and builds a saliency map "of the
  inpainted background layer".
- p.52: the rendering step projects "the K-Means color clusters and
  extracted stylistic typography" onto the boxes.

**Code (notes §3.23), Stage 0c:**
- The master's text-free background layer is rebuilt from the poster's
  border (the implementation's "inpainted background").
- Its motifs are YOLO detections cut out and ranked by SIFT keypoint
  density:
  - the embellishment class today;
  - the new `illustration` class first, once the re-annotated v5 exists
    (§3.25).
- Its title artwork is cut out too.
- The output is rendered on this layer, and the Legibility Penalty is
  scored against its saliency.

**Add:** a sentence each at p.37 (what "inpainted background" means here,
and that motifs and title artwork are the markers carried across), and at
p.52 (the rendering projects the background layer, motifs and title artwork
as well as the palette).

### 3.15 🟡 What the "parallel state-space explorations" vary (Phase 3, p.52; Figure 3, p.54)

**Now:** candidates are "multiple layout candidates" and "parallel
algorithmic layout variations", with nothing said about how they differ.

**Code (updated 2026-09-29, notes §3.27):** six candidates. Each combines
four things:
- a **layout archetype**: classic centred, left-aligned, art column (the
  title artwork in a side column), header banner, floating card (ID) or
  full-width band (ID);
- a page margin;
- a vertical rhythm (the stack's minimum gap);
- a motif arrangement: diagonal, anti-diagonal, four corners, side
  columns, base pair, crown pair, or a single enlarged "hero" motif.

Each is solved by Cassowary and scored on its own composed background.

**Add:** one sentence listing the four varied parameters.

### 3.16 🟡 Pre-orchestration schema validation: state the actual rules (p.43)

**Now:** the rules are given only by example ("font weight is evaluated as
a valid integer", "baseline tensor arrays do not exceed the viewport").

**Code:** JSON Schema (Draft 2020-12), and a violation rejects the
initialization.
- **Typography:** weight ∈ {100, 200, …, 900}; base size from 8 px to 15%
  of the viewport's shorter side.
- **Content payload:** every schema variable present, as a string within
  its `max_characters`.

**Add:** the two rule sets, in a sentence or a small table.

### 3.17 🟡 Optional: replace the Figure 2 and Figure 3 mockups with screenshots (pp.51, 53)

**Now:** both figures are mockups built around a Christmas poster.

**Code:** the dashboard now implements both, with the same panels and
labels:
- Visual DNA, User Injected and Target Initialization;
- the Constraint Editor with its State Timeline (JSON Sync), and the
  Recommendation Engine.

Screenshots on a CSPC poster would show the real system. Keep the mockups
if the committee prefers the figures as designed.

### 3.18 🟡 Phase 3 inputs: synthetic templates *and* real posters (p.52)

**Now:** Phase 3 "will be subjected to the synthetic administrative
templates".

**Code:**
- `evaluate.py` still runs on the synthetic theme.
- The Phase 3 battery (`experiment_runner.py`) runs on the 15 real,
  unseen event posters, because the Legibility Penalty needs a real
  background to measure anything.

**Add:** name both inputs.

### 3.19 🟡 Table 1's master-to-GNN mapping is now real: say how it works (Table 1, p.49; pp.39–41)

**Now:**
- Table 1 maps an ingested element's `bbox [x, y]` to the GNN's initial
  feature encoding.
- Nowhere does the text say how a poster's elements become a certificate's
  or ID's starting positions, when the two formats have different
  elements.

**Code (notes §3.26):**
- `structure_mapping.py` reads the master's logo row, header, title and
  details from Stage 0b's detections.
- It pins the target elements with the same role. Certificates take only
  the logo row and header: a poster's title position doesn't suit a
  certificate.
- The rest are placed in order between them.
- The GNN's output is registered back onto those anchors.

**Add:** two sentences at Table 1 or pp.39–41: role mapping, then
interpolation, then GNN refinement, registered to the anchors.

### 3.20 🟡 Formulas 3.13 and 3.14 need their reference area stated (p.44, Formulas 3.13–3.14)

**Now:**
- Formula 3.13 measures distance to "a dynamically generated structural
  grid G".
- Formula 3.14 uses the canvas area.
- Neither says what G is built from.

**Code (notes §3.27):**
- G spans the candidate's own content area: its margins, quarters and
  centre.
- An element counts as aligned when its left edge, centre or right edge is
  on a gridline.
- The whitespace ratio is taken over the candidate's content region. For
  the art-column layout that is the text column, not the whole page.

Otherwise a left-aligned or split layout is penalised simply for not being
centred.

**Add:** one sentence per formula.

### 3.21 🟡 Figure 3's canvas and the event set (p.42 "event-driven"; p.53 Figure 3; p.54)

**Now:**
- p.42 lists the terminal events: on-drop, on-resize-complete, lock
  toggles.
- Figure 3 shows a canvas and a Constraint Editor.

**Code (notes §3.28):**
- The canvas is edited in place: select, drag, resize, lock, and
  double-click to retype.
- Each gesture sends one terminal event. The browser only previews while
  the pointer moves, which matches p.42.
- Two event kinds were added:
  - **text edit:** re-validated against the content schema of p.44
    before it's accepted;
  - **undo/redo:** each restores an earlier state as a new one, so the
    JSON chain stays append-only (Formula 3.9).

**Add:** "text edit" to p.42's event list, and a sentence that undo/redo
append rather than rewrite.

### 3.22 🟡 Optional: K-Means initialisation (p.36, Formula 3.1)

**Code (notes §3.29):**
- The K-Means initialisation is seeded, best of 5 per k, so a master
  always yields the same palette. Unseeded, identical runs could render
  different colours.
- p.36 doesn't describe the initialisation.

**Add:** "k-means with seeded initialisations (best of five per k)"
belongs in the implementation details. That's only needed if the
committee asks about reproducibility.

### 3.23 🟡 Which candidate becomes the output (Phase 3, p.52; Figure 3's Recommendation Engine)

**Now:** candidates are "ranked" by the Heuristic Fitness Function, which
implies the lowest C_total is the output.

**Code (notes §3.31):**
- Formula 3.11 scores every candidate.
- The output is the fittest candidate of the layout type (archetype) the
  master's composition calls for: left-aligned text, an artwork beside the
  text, text on a panel, or a footer band. Classic is the default.
- Without a master, it's the lowest C_total.
- Reason: Formula 3.11 can't distinguish the archetypes (exact ties on
  certificates; one archetype won every ID), so every poster's output had
  the same layout.

**Add:** a sentence at Phase 3 (and in the Figure 3 description) saying
the master's composition picks the layout type and the fitness function
ranks within and across types.

### 3.24 🔴 The F1 score doesn't count what p.56 defines (p.56, "Structural Accuracy Rate")

**Now:**
- **TP:** a node placed with zero collision penalty that respects the hard
  constraints.
- **FP:** a node that overlaps a locked node or protrudes beyond the
  viewport.
- **FN:** a mandated node that is missing.

**Code** (`evaluate.py`, `calculate_constraint_f1`):
- A hard node is a TP if it stays within 5 px, else an FP.
- **Every soft node is a TP** ("Cassowary always attempts satisfaction").
- Collisions and out-of-canvas boxes are never checked per node.
  P_collision after the edits is reported separately.

So the reported F1 of 1.0 measures hard-constraint retention only.

**Fix (code, not the manuscript):** score each node as p.56 defines. The
generated layouts don't change.

**Done in code (2026-10-07, notes §3.32):** `layout_report.structural_accuracy`;
`evaluate.py` uses it. F1 is still 1.0 on its run. Chapter 3 needs no
change; Chapter 4 should say F1 counts collisions and out-of-canvas
elements per element.

### 3.25 ✅ The fitness weights hadn't been calibrated (p.43, Formula 3.11; Phase 3, p.52): done 2026-10-08, no Chapter 3 change

**Now:**
- α–δ are "empirically calibrated during Phase 3 testing" (p.43).
- The penalty weights are "iteratively calibrated" until the scores align
  with the constraints and design rules (p.52).

**Code:** fixed by hand at α = 50, β = 2, γ = 1, δ = 1.5
(`optimization_engine.py`). No calibration run or record exists in the
notes.

**Fix, either:**
- run and record a calibration, e.g. how the ranking on the Phase 3
  battery changes as each weight varies; or
- reword to say the weights were set by hand with α largest, and report
  it as a limitation.

Changing the deployed weights changes which candidate becomes the output,
so the Phase 4 set would no longer reflect the system. Run it as an
analysis.

**Done (2026-10-08, notes §3.33):** `weight_calibration.py` ran p.52's loop
on the Phase 3 battery (the 64 Phase 4 runs), with criteria fixed
beforehand. It kept no change, so the deployed weights are confirmed.
Halving or doubling any weight changes at most 1 of the 64 rated layouts.
The experts won't re-score (user, 2026-10-08), so the weights stay as they
are either way.

**Manuscript:** p.43 and p.52 can stay as written. Chapter 4 reports the
calibration and says the weights were set by p.43's priority rule and then
confirmed. It ran after the Phase 4 layouts were generated (and before any
rating was analysed); don't claim it came first.

### 3.26 🟡 The Spatial Hierarchy Index is a reading order, not a size rank (p.48; Appendix B)

**Now:**
- p.48: the index "instructs the Cassowary constraint solver to allocate
  the largest baseline geometric tensors to primary nodes (e.g., ensuring
  a student's name receives a larger bounding box than a course
  subtitle)."
- Appendix B: Student_Name = 1, Course_Title = 2, Signature_Blocks = 3.

**Code:**
- The index is each element's slot in reading order: 0 (logo row) to 8
  (signatures) on the certificate, 0 to 5 on the event ID.
- `dynamic_instantiation.py` gives each slot a fixed baseline size, and the
  layout stacks in index order.
- On the certificate, the title gets the largest box and the name the
  third largest. The name is index 4. The real payloads have no
  Course_Title.

**Fix:**
- Reword p.48: the index sets each element's role and reading order, and
  each role has a fixed baseline size (title and name the largest).
- Replace Appendix B's sample with the real `academic_payload.json`.

Notes §3.10 called Appendix B a match. The field names match; the index's
meaning doesn't.

### 3.27 🟡 Two counting slips (p.50; p.59)

- p.50: "executed in three distinct developmental phases". The procedure
  has four.
- p.59: "grounded in four fundamental computer science theories". Five are
  described (HCI theory, for Phase 4, is the fifth).

### 3.28 🟡 The dashboard is now three steps, with an Evaluation Report (pp.50–54)

**Now:** Chapter 3 describes two screens: Figure 2 (Phase 1) and Figure 3
(Phases 2–3).

**Code (2026-10-07, notes §3.32, the consultant's remarks):**
- The dashboard runs as Step 1 (Figure 2) → Step 2 (Figure 3) → Step 3,
  an **Evaluation Report** on the finished layout. Only the current step
  is enabled.
- Step 3 shows Formula 3.11 next to the recommendation, the p.56 F1 per
  element, the manual edits kept through each re-solve, stage and
  per-edit latency, the K-Means elbow and the schema validations.

**Add:** a sentence after Figure 3's description, or a Figure 3b
screenshot, saying the workflow ends with this report.

### 3.29 🟡 "Strict time thresholds" are never stated (pp.55–56, "Algorithmic Latency")

**Now:** latency must be "within the strict time thresholds required for
real-time Human-in-the-Loop (HITL) interface responsiveness". No threshold
is given.

**Measured (2026-10-07):** one canvas edit takes about 160 ms end to end
(re-solve, re-score, re-render, save); Cassowary alone takes about 0.4 ms.

**Fix:** name the threshold and cite it, e.g. the 0.1 s / 1 s response-time
limits (Nielsen, *Usability Engineering*, 1993). Confirm the source with
the TSA.

---

## Chapter 4: Results (don't draft until asked)

Not revisions, but the findings Chapter 4 will need, so nothing gets lost:

- **YOLO domain gap and closing it:**
  - v1, CGL only: mAP50 0.539 in-domain, but near-zero confidence on real
    posters.
  - v2 (65 images): mAP50 0.325.
  - v3 (124 images): mAP50 0.370; logo 0.620, text 0.595.
  - **v4 (deployed):** YOLOv8s from COCO at 1024 px, the over-half boxes
    removed. On the same cleaned validation labels as v3:
    - mAP50 0.454 vs. 0.363;
    - logo 0.818 (recall 0.76 vs. 0.55);
    - text 0.682.
  - Embellishment didn't move (recall 0.18). That's a label-definition
    problem; the group is re-annotating with a new `illustration` class
    (notes §3.25), and v5 comes after.
  - The automatic logo row is right on **15 of 15** unseen posters (7 of 15
    before).
  - **v5 (deployed 2026-10-06, notes §3.30):** the group's 200-image
    re-annotation, same recipe. On 32 validation images neither model
    trained on, mAP50 0.728 vs. v4's 0.486; embellishment 0.609 vs. 0.263;
    underlay 0.643 vs. 0.138. The dataset is now **200** images
    (160 train / 40 validation); item 3.2 is updated.
  - **Mean IoU** on the 40 validation images: not computed yet (item 3.4).
- **Fitness weight calibration (item 3.25, notes §3.33):** the deployed
  weights are confirmed; halving or doubling any weight changes at most 1
  of the 64 rated layouts. No candidate ever overlapped, so α's value never
  decided; the choices come down to whitespace against legibility.
- **Data-quality catch:** a mixed-format export would have silently
  dropped about 23% of images (§3.12).
- **GNN v1 → v2 (notes §3.22):** the first GNN predicted from inputs it
  never saw in training; on 2,900 held-out CGL layouts it was worse than no
  model (order kept 47%, i.e. chance). v2 cuts position error 43% and gap
  error 79% against v1. The table is in `results/gnn_heldout_eval.json`.
- **GNN v3, the master's structure as input (notes §3.26):**
  - **Held-out:** v3 cuts the structure start's position error 28% (0.036
    vs. 0.050) and its overlap 89%; v2 makes it worse (0.096).
  - **With exact anchors:**
    - raw v3 moves them by 2.6% of the height;
    - registered to them, it keeps them and places the unmapped elements
      8% better than interpolation (0.075 vs. 0.081);
    - v2 registered is worse than interpolation.
  - That's the case for registration, and for training on structure
    starts.
- **Phase 3 battery, three Stage 2 conditions (notes §3.26, §3.30,
  `results/experiment_log.json`, run 20261006_195534: YOLO v5, the 16 new
  Phase 4 posters, layout type from the master, item 3.23):**
  - **Structure transfer works.** The output is closer to the master than
    the baseline:
    - event IDs: on 15 of 16 (structure error 0.045 vs. 0.117);
    - certificates: on 14 of 16 (0.056 vs. 0.089); the other two have no
      roles to map.
  - **Formula 3.11 doesn't reward it.**
    - Certificates mostly tie (equal on 10 of 16).
    - On IDs the baseline scores slightly better (0.1583 vs. 0.1633),
      through legibility: text goes where the poster had artwork.
    - Worth stating as a limitation of the fitness function. Phase 4's MOS
      (hierarchy, brand consistency) is where this is judged.
  - **GNN vs. mapping only:** the same anchors. The GNN moves the unmapped
    elements on 14 of 32 runs, by ≤ 7.5% of the height. The formats' tall
    stacks leave the solver's design rules little slack, so report the
    GNN's gain from the held-out test, not from the fitness.
  - The 2026-09-29 run (YOLO v4, the earlier 15 posters) showed the same
    pattern. The older 2-condition numbers (1.2029 vs. 1.1876) are
    obsolete.
- **Manual refinements are retained:** simulated moves, resizes and locks
  are kept exactly through re-solves, with no overlap (F1 1.0, `evaluate.py`,
  `test_hard_constraints_preserved`).
- **Stage 0b's automatic logo pick on unseen posters:** right on 7 of 15,
  incomplete on 6, wrong object on 1, nothing on 1 with v3 (notes §3.21).
  With v4 and the row-clustering rule it is right on 15 of 15 (§3.25). The
  dashboard's pickers remain the human-in-the-loop fix.
- **AAPA diversity:** candidates now differ in layout archetype, margin,
  rhythm and motif arrangement (§3.15 above, notes §3.27), superseding the
  earlier collapse finding (§1.4).
- **The ranking picks the same layout type for nearly every poster**
  (run 20261006_144208):
  - certificates: "classic centred" on 14 of 16, because the top
    candidates tie exactly on C_total and the first in the list wins;
  - event IDs: "left-aligned" on 16 of 16, by a small, steady margin.
  - So every poster's output had the same layout per format, and the
    candidates' variety was visible only in the Recommendation Engine.
  - **Fixed before Phase 4 (2026-10-06, notes §3.31):** the master's
    composition now picks the layout type (item 3.23). The Phase 4 set
    has 4 layout types per format across the 16 posters. Chapter 4
    should report the cost: the chosen type isn't always the lowest
    C_total.
- **Reproducibility catch:** Stage 0's K-Means was unseeded, so identical
  runs could render different palettes and pick different winners (notes
  §3.29). It is fixed, and everything reported comes from after the fix.
- **HITL on the canvas:** moves, resizes, locks, text edits and undo/redo
  are made directly on the Figure 3 canvas. Each is one terminal event,
  verified in a real browser (notes §3.28).
- **Phase 4 MOS results:** none yet.

---

## Order of work

1. **Can do now, no TA decision needed:** 1.1, 1.2, 1.3, 3.1, 3.2, 3.3,
   3.5, 3.6, 3.7, 3.7b (tell the TA about 3.7b), 3.8, 3.13–3.16,
   3.18–3.21, 3.23, 3.26–3.29.
   - These answer the TSA directly.
   - 3.2 needs the image source/permission details from the group.
2. **Code first, then the text:** 3.4 (mean-IoU script). 3.24 (F1) and
   3.25 (weight calibration) are done in code.
3. **After the consultant weighs in:** 3.9.
4. **After the TA answers:** 3.10, 3.11, 3.12.
