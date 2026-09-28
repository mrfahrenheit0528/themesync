# Manuscript Revision List: What to Fix and Add

Every place where `Final Manuscript.pdf` needs to change so it matches what
was actually built, or answers a grounding question. Each item gives the
page, what the manuscript says now, what's wrong, and what to change.

This is a **to-do list, not draft prose.** Wording drafts get written only
when asked for explicitly.

- Page numbers are the manuscript's printed page numbers.
- Checked against the PDF text on 2026-09-28.

**Legend:**
- 🔴 **Must fix.** Wrong, contradicts the code, or a missing citation the
  TSA already asked about.
- 🟡 **Should add.** Missing documentation of something that exists.
- ⏸ **Blocked.** Waiting on a TA decision; do not edit until she answers.

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

**Blocked on:** the TA's answer to "1 expert vs. 3–5" (see Ch3 item 3.7).
If she approves 3–5, pluralize both places.

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

### 3.2 🟡 New Research Instrument: the 124-image master-layout dataset (between "Training Data and Feature Mapping" and "Synthetic Administrative Templates", p.49)

**Now:** "Research Instruments and Data Gathering" (pp.45–50) lists only
CGL-Dataset V2 and the synthetic certificate/ID templates. The group's own
annotated dataset is not mentioned anywhere in the manuscript.

**Why it's needed:**
- It exists, and it trained the YOLOv8 model the system actually uses.
- It was sent for expert validation.
- The TSA asked what backs the dataset.

**Add a subsection covering:**
- **Purpose:** the Stage 0b YOLOv8 model trained only on CGL-Dataset V2
  didn't transfer to real master layouts (top confidence 0.03–0.11 on real
  CSPC posters, §3.5–3.7). Real branded designs are needed for fine-tuning.
- **Source and scope:** 124 real event-poster/branding master layouts
  (a "master layout" is any generic branded design a user uploads). State
  where the images came from and the permission/usage basis. **Fill this
  in; it isn't in the notes.**
- **Annotation protocol:**
  - Roboflow, bounding boxes only.
  - The 4 classes reuse CGL-Dataset's taxonomy (Zhou et al. 2022).
  - Written guidelines: `notes/annotation_guidelines.md`.
  - Who annotated, and the cross-checking between annotators.
- **Split:** 99 train / 25 validation (80/20).
- **Quality control:**
  - Export check: mixed polygon/box rows and a class-index reorder were
    found and fixed before training (§3.12).
  - Independent expert validation of a 15-image sample against the class
    definitions (`notes/annotation_validation_reference.md`).
- **How it's used:** continued fine-tuning of the CGL-pretrained YOLOv8,
  run in two stages: v2 on 65 images, v3 on 124.

### 3.3 🟡 Phase 1 YOLOv8 text doesn't say what the detector is trained on (p.50)

**Now:** "Semantic Layout Parsing utilizing YOLOv8 for object bounding box
detection and Tesseract OCR…" There is no training-data statement for
YOLOv8, while the GNN's is stated ("trained using the CGL-Dataset").

**Add one sentence:** YOLOv8 is pretrained on CGL-Dataset V2, then
fine-tuned on the master-layout dataset from item 3.2.

**Consider also:** Figure 2's "Affine scaling" readout is now real. The
detected logo's aspect ratio locks the certificate/ID logo's proportions
(§3.11). No text change is needed unless you want to describe it.

### 3.4 🟡 IoU evaluation set is out of date (pp.55–56, "Intersection over Union")

**Now:** IoU is measured between YOLOv8 predictions and "the ground-truth
annotations established in the baseline dataset," i.e. CGL-Dataset.

**Problem:**
- The model the system uses (v3) is evaluated on the master-layout
  dataset's held-out validation split. That's the number that shows it
  works on real uploads.
- Results are reported as mAP50 / mAP50-95, which are IoU-thresholded.
  The manuscript's metric is a raw IoU score.

**Fix:**
- Name both evaluation sets: CGL-Dataset V2 test, and the master-layout
  validation split.
- State that detection accuracy is reported as mAP at IoU ≥ 0.5 (and
  0.5:0.95), the standard for YOLO, with IoU as the matching criterion.
- Alternatively, compute a mean IoU of matched detections to match the
  current wording. **Code gap:** no mean-IoU script exists for YOLO yet.

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

**Blocked on the TA.** If she approves:
- Pluralize the evaluator to 3–5 professional designers.
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

### 3.7c 🟡 Optional: name the vertical-balance rule among Cassowary's soft constraints (pp.38–39)

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
- 15 unseen master layouts (event pubmats not used in YOLO training) × 2
  formats × 2 conditions = 60 layouts.
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
- Detection: mAP50 / mAP50-95.
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

---

## Chapter 4: Results (don't draft until asked)

Not revisions, but the findings Chapter 4 will need, so nothing gets lost:

- **YOLO domain gap and closing it:**
  - v1, CGL only: mAP50 0.539 in-domain, but near-zero confidence on real
    posters.
  - v2 (65 images): mAP50 0.325.
  - v3 (124 images): mAP50 0.370; logo 0.620, text 0.595.
  - Underlay and embellishment remain weak (§3.7, §3.12).
- **Data-quality catch:** a mixed-format export would have silently
  dropped about 23% of images (§3.12).
- **GNN-guided vs. baseline fitness:** GNN better on average in the
  multi-trial runs, but worse on the fixed certificate comparison
  (C_total 1.2029 vs. 1.1876). Report both honestly.
- **AAPA diversity collapses under GNN guidance:** a limitation (§1.4).
- **Phase 4 MOS results:** none yet.

---

## Order of work

1. **Can do now, no TA decision needed:** 1.1, 1.2, 3.1, 3.2, 3.3, 3.5,
   3.6, 3.7b (tell the TA about 3.7b).
   - These answer the TSA directly.
   - 3.2 needs the image source/permission details from the group.
2. **After the consultant weighs in:** 3.4, 3.8, 3.9.
3. **After the TA answers:** 1.3, 3.7, 3.10, 3.11, 3.12.
