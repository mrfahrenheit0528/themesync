# Findings from system development, for the manuscript chat

> **Start here (2026-10-13):** section I, at the end, lists five dashboard
> features added after Manu 1210.1 (fonts, mail merge, Style tools,
> drop-to-replace). Nothing in the manuscript has to change; the table there
> lists optional touches. Section H (2026-10-12) checks Manu 1210.1 against
> the system: five wording items (H1–H5). Section G (2026-10-10) was the
> list for Manu 1010.1, and it is applied. Sections A–F are the detail.

The system-development chat checked the revised manuscript against the
code on 2026-10-09:
- **Manuscript:** Manu 0910.1, as the LaTeX in `manuscript/LaTeX/chapters/`
  and the build `manuscript/Manu 0910.1.pdf`.
- **Code:** commit `d974808`.

The development chat doesn't edit the manuscript or the revision list.
This note lists only what **isn't already** in
`notes/manuscript_revision_list.md` (M1–M21 and the earlier items); section C
maps the rest. Please merge section A into the revision list. Section B is
for information only.

- **Where:**
  - LaTeX line numbers (`chapter3.tex:62`), with a phrase to search for,
    since lines drift as you edit;
  - "p." means the page in Manu 0910.1.
- **Tense:** write every addition in the past tense.

---

## A. New items for the revision list

### A1 🟡 "Incrementally" overstates how Cassowary is used (`chapter3.tex:62`, p.40)

**Now:** "The solver uses a dual-simplex method to maintain these
relationships established in Formula 3 incrementally, allowing the layout
to re-calculate in milliseconds whenever a single variable … is adjusted."

**Code:**
- `cassowary_engine.py` builds a fresh solver and solves the whole layout
  for every event.
- One re-solve takes about 0.4 ms.

**Fix:** e.g. "re-solves the whole layout on every terminal event, in
under a millisecond". The revision list's p.27 point about the ORCSolver
citation is related.

### A2 🟡 Table 1 reuses symbols that already mean something else (`chapter3.tex:340–358`, p.54)

- **Typography:** administrative typography (`font_family`, `weight`) is
  mapped to **S_i**. But:
  - s_i is the SIFT descriptor in Formula 3.6;
  - S_i is a K-Means cluster in Formula 3.1.
- **Saliency:** `extracted_saliency_weight` → **p_i(legibility)**, while
  Formula 3.15 writes the saliency as S(p).

**Fix:** use distinct symbols, e.g. T for typography, and the formulas'
own symbols for saliency.

### A3 🟡 Figure 2's text names two things the panel doesn't show (`chapter3.tex:384`, p.56–57)

An addition to M17, which covers the arrangement.

- **"the structural hierarchy parsed by the GNN":** the node graph on Step
  1 (now in the (i) dialog) is Stage 0b's parse, by YOLOv8 + Tesseract.
  The GNN runs only at Initialize.
- **"boolean feature detection via SIFT/SURF":** the SIFT card shows the
  saliency weight, "logo detected: yes/no" and the image size. Only "logo
  detected" is boolean, and it comes from YOLO's logo class.

**Fix:** "the elements parsed by the layout detector"; "SIFT keypoint
saliency and whether a logo was detected".

### A4 🟡 OCR isn't what makes the nodes' words (`chapter3.tex:375`, p.56)

**Now:** Tesseract OCR for text extraction, "converting the flattened
raster pixels into structured, editable nodes".

**Code:** OCR text labels the parsed nodes in the node graph. The
layout's words come from the user's content payload, which is what p.45's
argument against OCR "typographic hallucinations" supports.

**Fix (optional):** "OCR labelled the parsed text nodes; their content
came from the validated payload".

### A5 🟡 Which latency meets which limit (`chapter3.tex:433`, p.62)

Item 3.29 is applied: the thresholds are cited. But the measurements so
far split across them:
- **One Cassowary re-solve:** about 0.4 ms, well within 0.1 s.
- **One whole canvas edit** (re-solve, re-score, re-render, save the
  state chain): about 160 ms. That's over 0.1 s and within 1.0 s (notes
  §3.32).

**Fix:** after the development chat's benchmark (section B), say that the
solver meets 0.1 s and a full edit meets 1.0 s. The development chat may
also bring the full edit under 0.1 s; wait for its numbers.

---

## B. Passages the development chat will make true (keep the text)

These describe things the system doesn't fully do yet. The development
chat is building them in this order and will report numbers. Don't add
results before then.

1. **Mean IoU on the 40 validation images** (p.62). This is in "Code
   before Chapter 4".
2. **The stress test** (p.55; M3). Done: numbers in D2.
3. **The latency benchmark** (p.62; A5 above). Done: numbers in D3.
4. **F1 over the 64 rated layouts** ("Code before Chapter 4"). Done:
   numbers in D4.
5. **"the K-Means elbow graph"** in the Step 3 report (p.60). Done:
   see D5.
6. **The GNN–solver "Mean IoU"** ("Code before Chapter 4"). Renamed:
   see D5.

Also: the Phase 4 analysis waits on the consultant's answers and the
experts' scores (item 3.9).

## C. Checked and already in the revision list (no action from this note)

| Finding | Already tracked as |
|---|---|
| SIFT and SURF: only SIFT runs | 3.10 (⏸ TA) |
| GNN c_i, s_i are layout-level; Annex A's per-node fields | 3.12 (⏸ TA) |
| "Larger footprint, higher relational weight" | M8 |
| "Gap error 0.075 vs 0.081" is a position error | M6 |
| R_target fixed at 0.65 | M19 |
| Formulas 3.12, 3.13, 3.15 normalised in the code | M20 |
| CNN "deployed for quantitative aesthetic evaluation" | 3.11 (⏸ TA) |
| Figures 2 and 3 show the May mockups | M17 (plus A3 above) |
| Annex B's payload isn't the system's | M7 |
| Unescaped `_` (`max_characters`, `spatial_hierarchy`) | M1 |
| The State Synchronization paragraph printed twice | M2 |
| Future tense left over | M11 |
| "introduced by introduced by", "Emperical", "placement A sample" | M12 |
| ANTI_HAZING_LAW's rated pages; with/without analysis | 3.9 |

---

## D. Numbers for the manuscript (as they arrive)

### D1. The detector's mean IoU (p.62; item 3.4) — 2026-10-09

`src/evaluation/yolo_iou.py` → `results/yolo_iou.json`; notes §3.41.

**Setup:**
- **What's measured:** the deployed detector (YOLOv8s, `themesync_yolo_v5.pt`,
  at 1024 px) on the master-layout dataset's 40 held-out validation images.
- **Operating point:** the system's own (confidence ≥ 0.25, or ≥ 0.15 for
  title-sized text).
- **Ground truth:** the validation labels as training saw them (polygons
  as their enclosing boxes; boxes over half the image dropped). 607 boxes.

**The matching rule:**
- **Pairing:** in each image and for each class, every ground-truth box
  is paired with at most one detection, and vice versa. The pairing chosen
  maximises the total IoU (the Hungarian algorithm).
- **Strict mean IoU:** the average over every ground-truth box. A box with
  no overlapping detection counts as 0.
- **Found:** a pair with IoU ≥ 0.5, the usual threshold (as in mAP50).
  - Recall = found ÷ ground-truth boxes; precision = found ÷ detections.
  - The mean IoU is taken over those pairs.

| class | boxes | strict mean IoU | found (recall) | precision | mean IoU of found |
|---|---|---|---|---|---|
| logo | 140 | 0.844 | 0.957 | 0.957 | 0.882 |
| text | 260 | 0.679 | 0.796 | 0.695 | 0.818 |
| underlay | 41 | 0.548 | 0.634 | 0.605 | 0.850 |
| embellishment | 166 | 0.445 | 0.530 | 0.633 | 0.809 |
| **all** | **607** | **0.644** | **0.750** | **0.734** | **0.837** |

**For the text:**
- **Which number:** the development chat suggests reporting the strict
  mean IoU (0.644) as "the mean IoU", since it counts every element. Add
  that found elements average 0.837, with 75% found at IoU ≥ 0.5.
- **The duplicate:** one of the 40 images (HIRAYA) duplicates a training
  image. Without it (39 images), the figures are strict 0.640, found 74.4%,
  mean IoU of found 0.837, so the 40-image figure stands. Mention it once,
  as a footnote, if at all.
- **mAP50** on the same 40 images is 0.746 (Ultralytics' validator, all
  confidences), if Chapter 4 wants the one-sentence comparison the
  revision list mentions.
- **Machine:** measured on the Windows checkout (RTX 3060) with the
  server's library versions. A server run may differ in the last decimal.

### D2. The stress test (p.55; M3) — 2026-10-09

`src/evaluation/stress_test.py` → `results/stress_test.json`; notes §3.42.
It ran on this Windows checkout. No Phase 4 file or pipeline code changed.

**Setup:**
- **Theme and formats:** the synthetic theme (no master layout), GNN on,
  on both formats: the 4:3 certificate and the A6 event ID.
- **Content:**
  - every text field at 25/50/75/100% of its `max_characters`, as real
    words and as one unbroken token;
  - each field alone at its max;
  - each field at max + 1;
  - the certificate's signature blocks, 1 to 10 (the payload declares 3).
- **Measures:**
  - F1 as p.56 defines it;
  - the reading order (spatial hierarchy top to bottom);
  - text fit: each rendered line measured with the font's real glyph
    widths, against its box;
  - the smallest font size in points at print size: the event ID at A6;
    the certificate at US Letter landscape (an assumption; the manuscript
    gives no size, and on A4 every figure is 6% larger).

**Results:**

| | certificate | event ID |
|---|---|---|
| every field at its max, real words | all text fits | the organisation header overflows |
| first failure, real words | none | organisation header from 49 of 90 characters |
| first failure, one unbroken token | citation from 98 of 150 characters (spills ≤ 15 px into the margin) | event details from 51 of 80 |
| max + 1 characters | rejected, all 7 fields | rejected, all 5 fields |
| reading order | held in every run | held in every run |
| F1 | 1.0 in every length run | 1.0 in every run |
| signature blocks | clean up to 5; from 6 the blocks overlap (F1 0.92); from 7 names spill onto neighbours | — |
| smallest text | 7.8 pt (signature titles) | 6.5 pt (organisation header) |

**For the text:**
- **What holds:**
  - The solver kept every box apart, on the canvas and in hierarchy order
    at every length (F1 1.0).
  - The schema rejected every over-length field.
  - On the certificate, all text still fit its box at every maximum with
    real words. The longest names shrank from 31 to 13.5 pt.
- **What doesn't:**
  - **The event ID's organisation header** wraps at a fixed 60
    characters and doesn't shrink to the box width. A line over 48
    characters runs out of its box; from about 56 characters, off the
    canvas.
  - **Signature blocks:** there is no "maximum instantiation limit" in the
    system. Nothing caps the count, and signature text has no
    `max_characters`. The certificate holds 5 blocks cleanly; from 6 they
    overlap.
- **So, as written, p.55's "without violating predefined bounding box
  limits or overwriting surrounding structural nodes" is too strong.** Two
  honest options:
  - **report it as found:** it held for the certificate; the event ID's
    header overflowed past 48 characters per line; the layout held up to
    5 signature blocks;
  - **or wait for a fix:** the development chat can fix the header (and
    cap the signature count) after Phase 4 scoring ends, then re-run.
    That changes the renderer the experts' layouts came from, so the
    notes would record that the rated layouts predate the fix.
- **F1 alone doesn't show this:** F1 scores boxes, not the text inside
  them, so every length failure above still has F1 1.0. If Chapter 4
  reports the stress test, it needs the text-fit measure beside F1.
- **"student names":** p.55's example field is the certificate's
  recipient name, which passed at its 60-character maximum.

### D3. Latency over many edits (p.62; M26, A5) — 2026-10-09, updated after the speed-up

`src/evaluation/latency_benchmark.py` → `results/latency_benchmark.json`;
notes §3.43 and §3.47.

**Setup:**
- **Sessions:** 34 editing sessions: the 16 Phase 4 posters on both
  formats, opened as the packet opened them, plus the synthetic theme.
- **Edits:** 40 recorded edits per session, 1,360 in all: moves, resizes,
  locks, text edits, typography, undo, restore and candidate clicks.
- **Two timings per edit:**
  - **the solver:** the Cassowary re-solve, the "constraint
    recalculation";
  - **the full edit:** re-solve, re-score, re-draw and save the state
    chain, the "state synchronization".
  - Neither includes the browser redrawing the page.
- **Machine:** the Windows PC.

**The speed-up:** after the first measurement, the development chat made
the renderer stop re-reading image files that don't change during a
session (§3.47).
- The output is byte-identical: the same 64 rated layouts, and the same
  result after every edit.
- These are the numbers for the system as it is now; the earlier ones are
  in brackets.

| | edits | median | 95th percentile | max | within 0.1 s | within 1.0 s |
|---|---|---|---|---|---|---|
| solver | 1,012 | 0.4 ms | 0.8 ms | 1.9 ms* | 100% | 100% |
| full edit | 1,360 | 90 ms (157) | 176 ms (338) | 206 ms (393) | 61% (22%) | 100% |
| full edit, certificate | 680 | 146 ms (220) | 182 ms (370) | 206 ms (393) | 29% (19%) | 100% |
| full edit, event ID | 680 | 86 ms (143) | 103 ms (223) | 159 ms (298) | 93% (25%) | 100% |

\* One outlier of 95.9 ms (a pause of the process, in a session that
loads no images) is still within 0.1 s.

**For the text (M26):**
- **The solver met the 0.1 s limit on every edit.**
- **A full edit met the 1.0 s limit on every edit, and the 0.1 s limit on
  61% of them.**
  - Edits that only re-draw the canvas (text, typography, undo, restore,
    a candidate) all took under 0.1 s (median 12 ms).
  - Edits that re-solve the layout (move, resize, lock) took a median of
    104 ms on a poster's theme, about half of them under 0.1 s.
  - What's left is re-scoring legibility against the poster's background.
- **Suggested wording:** "constraint recalculation within 0.1 s, state
  synchronization within 1.0 s".
- **Not a per-edit figure:** opening a layout (Initialize, Stages 0–6)
  took a median of 3.4 s, once per layout.

### D4. F1 over the 64 rated layouts (Chapter 4) — 2026-10-09

`src/evaluation/rated_layouts_check.py` →
`results/rated_layouts_check.json`; notes §3.44.

**Setup:**
- **What it reads:** the files the packets were printed from. All 64
  match the Phase 4 key.
- **Measures:**
  - F1 as p.56 defines it;
  - the reading order;
  - whether each line of text fits its box (as in the stress test, D2).

| | certificate GNN | certificate baseline | event ID GNN | event ID baseline |
|---|---|---|---|---|
| F1 | 1.0 on all 16 | 1.0 on all 16 | 1.0 on all 16 | 1.0 on all 16 |
| reading order kept | 16 | 16 | 16 | 16 |
| text fits its box | 16 | 16 | 14 | 14 |
| text over other text or a picture | 0 | 0 | 0 | 0 |
| smallest text | 7.8 pt | 7.8 pt | 6.5 pt | 6.5 pt |

**For the text:**
- **F1 1.0 on all 64 rated layouts,** in both conditions: every mandated
  element present, none overlapping, none off the canvas.
- **Two event IDs (RXEADY, ARANTABAYAN), in both conditions:** a header
  line 6–19 px wider than its box on each side. It stays inside the card
  and covers nothing, so it doesn't change how the pages read. It's the
  stress test's header finding (D2) showing up mildly in the real set.
  Mention it only if Chapter 4 discusses D2.
- **The F1 is the same for both conditions,** so F1 doesn't separate GNN
  from baseline. The Phase 4 comparison rests on the experts' scores.

### D5. The elbow graph and "GNN–solver overlap" — 2026-10-09

Notes §3.45.
- **p.60, "the K-Means elbow graph": now true.** Step 3's Hybrid Visual
  DNA card draws WCSS against k, with the chosen k marked and the line
  joining the curve's ends. The Elbow Method picks the point farthest from
  that line. The WCSS table is still there, under the graph.
- **The GNN–solver "Mean IoU" is now called "GNN–solver overlap"**
  (`gnn_solver_overlap` in the results files written from now on; older
  files keep `mean_iou`). It is the IoU between each GNN-predicted box and
  where the solver finally put it. Chapter 4 should use that name, or leave
  it out; it isn't p.62's IoU, which is the detector's (D1).

### D6. A master-derived R_target (p.47; M19) — 2026-10-09

`src/evaluation/r_target_analysis.py` → `results/r_target_analysis.json`;
notes §3.46.

**Setup:**
- **Runs:** the 64 rated runs, regenerated. All 64 choices match the Phase
  4 key.
- **The master-derived R_target:** Formula 3.14 applied to the master
  poster itself, with its detected logos and text as the elements.
- **Re-ranking:** each run's candidates, re-ranked with that R_target in
  place of 0.65.

**Results:**
- **2 of the 64 rated layouts would have changed:** RZEADY_SET_BOOTH and
  SHARE_KO_LANG, event ID, baseline condition. Each swaps between two
  candidates of the same layout type whose whitespace differs by 0.5%.
- **The certificates and the GNN condition:** none would change.
- **The masters' own ratios** run from 0.46 to 0.86 (median 0.74).
- **The candidates' ratios:**
  - certificate: 0.57–0.65, so 0.65 fits it;
  - event ID: 0.46–0.51 on every candidate, so it can never reach 0.65.
- **Why it changes so little:** the system first keeps the layout type the
  master calls for, then compares the candidates of that type, and those
  have nearly the same whitespace. R_target only matters when choosing
  between layout types.

**For p.47:**
- R_target was a fixed 0.65, not derived from the master.
- Either reword p.47 to say so, or keep the sentence and report this
  analysis: a master-derived target would have changed 2 of the 64 rated
  layouts.
- The deployed value stays at 0.65 either way.

### D7. Phase 4: the analysis plan and the results — 2026-10-10

Notes §3.48 (plan) and §3.49 (results). Files:
- `src/evaluation/phase4_analysis.py` → `results/phase4_analysis.json`;
- the ratings: `results/mos_results.json`;
- post hoc: `results/phase4_posthoc.json`.

**The consultation:**
- **Outcome:** it concluded "recommended for POD".
- **Statistics:** the consultant checks only the prototype, so the group
  adopted the guide's suggested answer to all eleven questions (user,
  2026-10-10).
- **For item 3.9 and Chapter 3's statistical treatment,** the decisions
  are:
  - **Q1:** MOS (the arithmetic mean, ITU-T P.800) ± SD per parameter and
    overall, by condition and format; the count of each rating 1–5.
  - **Q2:** Kendall's W with its χ² test, per parameter and overall.
  - **Q3, Q4:** the Wilcoxon signed-rank test on the 32 pairs; each
    layout's score is the mean of its four experts' ratings.
  - **Q5:** both formats in one test; each format's MOS reported, not
    tested.
  - **Q6:** the overall MOS is the main test; the three parameters are
    follow-ups, with Holm's correction.
  - **Q7, Q8:** two-sided; "a significance level of 0.05" (not "α",
    which Formula 3.11 uses).
  - **Q9:** the rank-biserial r beside every p-value; a non-significant
    result is "no significant difference was detected".
  - **Q10:** purposive sampling, with three criteria:
    1. real school-organisation event posters;
    2. in no training data, checked with an image-duplicate test;
    3. their text fits both formats.
  - **Q11:** mean ± SD of C_total, latency, F1 and IoU; the same Wilcoxon
    test for GNN vs baseline C_total.
  - **Q2's "acceptable value and source" got no answer.** Commonly used,
    to verify before citing:
    - Schmidt (1997) for Kendall's W (0.5 moderate, 0.7 strong);
    - Krippendorff (2004) for α (0.667 / 0.800);
    - Koo & Li (2016) for ICC.
- **The plan was fixed in code and committed before any score was
  imported or summarised** (commit `b9a60ab`). Chapter 3 or 4 can say so.

**Label the conditions** "structure mapping + GNN" and "baseline (neither
structure mapping nor GNN)" (your C1; p.61's "GNN module deactivated" is
M4).

**Results** (768 ratings; 4 experts × 64 layouts × 3 parameters):

| | mapping + GNN, MOS ± SD | baseline, MOS ± SD | pairs where the baseline / mapping + GNN was higher / equal | p (Holm) | r |
|---|---|---|---|---|---|
| **overall (main test)** | 3.33 ± 0.89 | 3.73 ± 0.93 | 25 / 2 / 5 | **< 0.001** | **−0.95** |
| Visual Hierarchy | 3.61 ± 1.06 | 3.73 ± 1.11 | 16 / 7 / 9 | 0.127 | −0.36 |
| Brand & Typographic | 3.47 ± 1.09 | 3.70 ± 1.02 | 22 / 5 / 5 | < 0.001 | −0.74 |
| Constraint & Whitespace | 2.92 ± 1.18 | 3.77 ± 1.13 | 26 / 2 / 4 | < 0.001 | −0.98 |

- **By format, overall:**
  - certificates: 3.50 vs 3.78;
  - event IDs: 3.17 vs 3.69.
  - All 64 layouts together: 3.53 ± 0.93 (between Fair and Good on Table
    2's scale).
- **Agreement:** Kendall's W 0.63 overall (Hierarchy 0.58, Brand 0.48,
  Whitespace 0.57), all p < 0.001.
  - Absolute agreement is lower (ICC(2,1) 0.16–0.31, α 0.01–0.23). The
    experts order the layouts alike but differ in leniency: each one's
    mean runs from 2.88 to 4.32.
- **Q11:**
  - **C_total:** 0.0879 ± 0.0791 (mapping + GNN) vs 0.0855 ± 0.0766. The
    Wilcoxon test gives p = 0.030 (r = +0.53): Formula 3.11 also rated
    the baseline slightly better.
  - **F1:** 1.0 ± 0 in both conditions.
  - **Latency:** solver 0.53 ± 3.01 ms; full edit 90.6 ± 57.5 ms.
  - **IoU:** strict 0.644 ± 0.351; found 0.837 ± 0.097.
- **Sensitivity (secondary):** the paired t-test and Bonferroni give the
  same conclusions. Without the one pair whose layouts were identical,
  Visual Hierarchy reaches p = 0.046. Without ANTI_HAZING_LAW (its CLOSED
  stamp, item 3.9's question), all conclusions are unchanged.

**For Chapter 4 (don't draft until asked; these are the facts it must
carry):**
- **The main result:** at a significance level of 0.05, the experts rated
  the baseline significantly higher than structure mapping + GNN overall,
  with a large effect, and on Brand & Typographic Consistency and
  Constraint & Whitespace Harmony. No significant difference was detected
  on Visual Hierarchy Preservation.
- **Not a claim this supports:** "the GNN improved the layouts". The GNN's
  own gain is the Phase 3 held-out test.
- **Exploratory, labelled post hoc:**
  - Structure mapping + GNN places elements at the master's positions,
    leaving larger, uneven gaps. Its largest gap was bigger in 23 of 32
    pairs and never smaller, while the baseline's gaps were perfectly
    even.
  - The pairs whose gaps grew most lost the most MOS (Spearman ρ ≈ −0.42
    to −0.45, p ≈ 0.01–0.02).
  - Formula 3.11 doesn't measure gap evenness (its difference doesn't
    track the MOS, ρ = −0.20).
- **The system stays as rated.** Even spacing after anchoring, or a
  gap-evenness term, belongs in the recommendations; it would need new
  ratings.

---

## E. Manu 1010.1 checked against the system — 2026-10-10

The development chat checked `manuscript/Manu 1010.1.pdf` against the code
and `results/` (commit `7082b10`).
- **Chapter 3:** read in full.
- **Chapters 1–2:** the sentences changed since Manu 0910.1, for system
  claims.
- **Chapter 4:** every number in Tables 3–21 and in the text, recomputed
  from the results files.

"p." is Manu 1010.1's page. There is no Chapter 5 yet.

### What's wrong

#### E1 🔴 p.81 says the stamp and the title cut-outs "were corrected" in the Phase 4 set; for ANTI_HAZING_LAW they weren't

**Now:** "three posters with a wrong title-artwork cut-out, one poster
whose logotype had been taken as a motif, and one whose 'CLOSED' stamp had
been taken as a motif … the other cases were corrected as per-poster
choices in the Phase 4 evaluation set".

**Fact:**
- **Corrected:** CMET and SIGN_LANGUAGE_DAY (title artwork off).
- **Not corrected:** ANTI_HAZING_LAW's two corrections (its title cut-out
  and the CLOSED stamp) were lost before the evaluation set was generated
  (notes §3.35). Its four rated pages carry both.
- **p.93 says so correctly,** so p.81 contradicts it.

**Fix:** "… the other cases were corrected as per-poster choices for the
Phase 4 evaluation set, except on ANTI_HAZING_LAW, whose corrections were
lost before the set was generated (see Objective 3)."

#### E2 🔴 Eleven citations print as raw keys

**Now:** the PDF prints, for example, "[Badros2001Cassowary]" (pp.10,
28, 41, 90), "[schmidt1997managing]" (pp.67, 94), "[koo2016guideline]"
(p.99), "[etikan2016comparison]" (p.62), and in the statistical treatment
(pp.67–68) "[kendall1939problem]", "[wilcoxon1945individual]",
"[holm1979simple]", "[kerby2014simple]", "[cohen1988statistical]",
"[shrout1979intraclass]" and "[krippendorff2004content]". None appears in
the chapters' Notes.

**Fact:** all eleven entries are in `manuscript/Thesis Latex/references.bib`
(uncommitted). The Prism build didn't have the updated `.bib`, or wasn't
re-run after it.

**Fix:** copy `references.bib` into Prism and rebuild. Then check that each
appears in its chapter's Notes, ACM style, with every author named.

#### E3 🟡 p.78 "[PENDING: server GPU]"

**Fact:** an NVIDIA RTX A5000 (24 GB), from the server's own Ultralytics
logs (`results/yolo_v5_training.log`, `results/yolo_v4_experiment.log`:
"CUDA:0 (NVIDIA RTX A5000, 24112MiB)").

#### E4 🟡 p.99 "The system was not changed after the rating"

**Fact:**
- **The layout generation wasn't changed.** The code was:
  - the dashboard;
  - the Step 3 elbow graph;
  - a renderer cache that made edits faster (2026-10-09, while the experts
    were rating).
- **The cache left the generated layouts byte-identical:** checked on all
  64 rated runs and on 1,360 edits (notes §3.47).
- **Table 13's latency was measured with the cache.** Without it, the full
  edit's median was 157 ms, its 95th percentile 338 ms, its maximum 393 ms
  (D3).

**Fix (suggested):** "The generation of the layouts was not changed after
the evaluation set was produced; later changes to the dashboard and a cache
that made edits faster left the generated layouts byte-identical, so the
reported MOS described the system as it was evaluated." Optionally, add
that the latency was measured with that cache.

#### E5 🟡 p.29: the GNN isn't in the live loop

**Now:** "ThemeSync embeds multi-relational GNN inference and the Cassowary
constraint-solving algorithm within a live orchestration loop, allowing
structural changes to occur in real time".

**Fact:** the GNN runs once, when a layout is opened (Stage 2). Every edit
re-solves Cassowary from the GNN's stored output (`pipeline.py`:
`_resolve` starts from `self.guided_nodes`).

**Fix:** "… runs the GNN once when a layout is opened and keeps the
Cassowary solver in the live orchestration loop …"

#### E6 🟡 p.30 "GNN compositional scoring"; p.28 ranking "in real-time"

**Now (p.30):** "integrates Aesthetic-Aware Preference Alignment (AAPA)
and GNN compositional scoring into an interactive recommendation
dashboard … aesthetically validated layout candidates".

**Fact:**
- **AAPA is fine:** it is the code's own name for the candidate
  exploration (`pipeline.py`, Stage 4).
- **The GNN scores nothing:** candidates are ranked by Formula 3.11 alone.
- **"Aesthetically validated" overstates:** Phase 4 found the opposite
  for the transferred layouts.

**p.28:** the candidates are generated and ranked once, when a layout is
opened (about 1.6 s of ranking in the Phase 3 battery). Edits don't
re-rank them.

**Fix:**
- p.30: drop "GNN compositional scoring", and write "fitness-ranked layout
  candidates".
- p.28: "when a layout is initialized" instead of "in real-time".

#### E7 🟡 p.90 Limitations: a causal "because" that isn't

**Now:** "the certificate held at most five signature blocks because the
content schema set no upper limit on their number".

**Fact:** five is what the row fits. The missing schema limit is why more
can be requested.

**Fix:** "the certificate's row held at most five signature blocks without
overlap, and the content schema set no upper limit on their number".

#### E8 🟡 p.92: two figures slightly off

**Now:** "the art column scored about 0.076 against about 0.002 for the
classic layout, and the floating card about 0.185 against 0.149".

**Fact:** the means over the 64 rated runs' candidates, from
`results/r_target_analysis.json`:
- art column 0.0759, classic certificate 0.0025;
- floating card 0.1872;
- and 0.149 is the left-aligned candidate (0.1488), which the sentence
  doesn't name.

**Fix:** "about 0.076 against 0.003 for the classic layout, and the
floating card about 0.187 against 0.149 for the left-aligned layout".

#### E9 🟡 p.64: F1's definitions are narrower or wider than the code's

- **FN** "mandated by the Dynamic Content Payload or the relational graph
  of the master template": in the code, only the payload mandates
  elements (`layout_report.structural_accuracy`). Drop "or the relational
  graph of the master template".
- **FP** "overlapping an immutable designer-locked node": the code counts
  an overlap with any element. Chapter 4 (p.86) says so correctly. Write
  "overlapping another element (including a designer-locked one)".

### Still open (already in the revision list)

- **3.10 SURF:** pp.40, 56–57, 59, 65 and the Project Dictionary. Only SIFT
  runs.
- **3.11 CNN "deployed for quantitative aesthetic evaluation"** (p.39):
  `themesync_cnn_v1.pth` exists, but nothing in the system uses it.
- **3.12 Formula 3.6 and Appendix A** (pp.43, 104): c_i and s_i per
  element.
  - The GNN gets one value of each per layout: the master's primary
    L\*a\*b\* centroid (OpenCV's 8-bit encoding, /255) and one saliency
    weight, the same in every node.
  - Training and inference agree on that, so the gap is per-element vs
    per-layout.
  - Appendix A still shows `node_id` and `text_features`, which the
    pipeline drops.
- **M17 / M24, Figures 2 and 3:**
  - **Figure 2 (p.57)** still describes "the central viewport … the
    right-hand panel". Step 1 now has the master layout on the left, the
    logos and markers, typography and payload in cards on the right, and
    Target Initialization in an overlay from the top bar (§3.37).
  - **Figure 3 (p.60)** still describes "two critical computational tabs"
    with the timeline below the Constraint Editor. Step 2 now has:
    - the canvas, with the Recommendation Engine as a strip of thumbnails
      beneath it;
    - one right panel: the selected element, typography, and canvas
      details;
    - the State Timeline in a dialog opened from the top bar (§3.38).
- **p.87 "[PENDING: confirm the certificate's paper size]":** the group's
  call. US Letter landscape was assumed; on A4, every point size is 6%
  larger.

### Checked and correct

- **Chapter 4's numbers all match the results files:**
  - Table 4: `yolo_domain_gap_check.json`;
  - Table 5: `yolo_v4_experiment.json`;
  - Table 6: `yolo_v5_comparison.json`;
  - Table 7 and the IoU SDs: `yolo_iou.json`;
  - Tables 8–9, the 28%, 89% and 8% figures, and 8,356 / 2,432:
    `gnn_heldout_eval.json`;
  - Tables 10, 14 and 15, the 10/4/2 and 13-of-16 counts, and "every poster
    with mappable roles": `experiment_log.json` (run 20261006_195534);
  - Tables 11–12: `rated_layouts_check.json`, `stress_test.json`;
  - Table 13, the 0.53/90.6 ms means, 105 ms and 48% for re-solving edits,
    and 12 ms for re-drawing ones: `latency_benchmark.json`;
  - Tables 16–21, the sensitivity checks and the per-expert 0.15–0.75:
    `phase4_analysis.json`, `phase4_posthoc.json`;
  - the R_target paragraph: `r_target_analysis.json`.
- **Chapter 3 agrees with the code on:**
  - Formula 3.7 (an MLP message, mean aggregation, a GRU update) and
    Formula 3.8's edge features;
  - Hard constraints as `required`;
  - K-Means k = 2–6, best of five seeds;
  - the schema rules;
  - Formulas 3.12–3.15 with their normalisations and exclusions; R_target
    fixed at 0.65;
  - the re-solve on every terminal event (M22);
  - the vertical-centre error (M6);
  - the baseline described with both modules off (M4);
  - the no-master fallback (M5);
  - the event ID's and the certificate's box sizes;
  - the stress test's description;
  - the latency and IoU definitions;
  - Table 2's labels.
- **Appendix B** is now identical to `data/raw/academic_payload.json` (M7).
- **The statistical treatment (pp.67–68)** is exactly what
  `phase4_analysis.py` runs, and the "committed before the import" claim is
  true (`b9a60ab`, unchanged since).

---

## F. Figures for Chapter 4, and the dashboard screenshots — 2026-10-10

### F1. Result figures (`results/figures/`)

`notebooks/results_analysis.ipynb` now covers every result through Phase 4.
It was re-executed on 2026-10-10 on the Windows checkout, with no errors.
- **Each figure is saved twice:** a PNG at 300 dpi and a vector PDF, on
  white.
- **For LaTeX,** use the PDF; for Prism's image upload, the PNG.
- **The design:** no titles inside the images, so the captions go in the
  LaTeX; sized for a 6.5-inch text block.
- **Colours:** blue is structure mapping + GNN, orange the baseline, each
  with its own marker shape, so they also read in greyscale.

Chapter 4 has only tables now. These figures show what the tables can't:
the distribution, the pairs, and the example.

| File | What it shows | Data | Suggested place |
|---|---|---|---|
| `fig4_structure_error` | per poster, the structure error of structure mapping + GNN against the baseline (14 certificates, 15 event IDs); every pair improves | `experiment_log.json` (Table 10) | Objective 1, Transfer of the Master's Structure |
| `fig4_latency` | the cumulative share of edits by time (log scale) for the solver, re-drawing edits and re-solving edits, with the 0.1 s and 1.0 s limits | `latency_benchmark.json` (Table 13) | Objective 2, Algorithmic Latency |
| `fig4_mos_by_parameter` | MOS ± SD by parameter and condition, with each Holm-corrected p and r | `phase4_analysis.json` (Tables 16, 20) | Objective 3, beside Table 16 |
| `fig4_rating_distribution` | the share of ratings 1–5 per parameter and condition, centred on "Acceptable"; Constraint & Whitespace's 39% of 1–2 ratings for structure mapping + GNN stands out | `phase4_analysis.json` (Table 18, by parameter) | Objective 3, beside Table 18 |
| `fig4_pairs` | each of the 32 pairs' overall MOS, the baseline against structure mapping + GNN, with the equality line; 25 lie below it | `phase4_analysis.json` (Table 20) | Objective 3, beside Table 20 |
| `fig4_spacing_vs_mos` | the change in the largest gap against the change in overall MOS (Spearman ρ = −0.42, exploratory) | `phase4_posthoc.json` (Table 21) | Objective 3, the exploratory paragraph |
| `fig4_example_pair` | RxEADY's event ID: (a) the master, (b) structure mapping + GNN (MOS 2.50), (c) the baseline (MOS 3.67). The empty band below the header in (b) is what the spacing analysis measures | the rated files in `data/phase4/samples/` | Objective 3, Discussion (interpretation) |

**Two cautions:**
- **Label `fig4_spacing_vs_mos` as exploratory** in its caption, as Table 21
  is.
- **The example pair's master poster uses licensed cartoon characters.**
  The group should be comfortable printing it under academic fair use, or
  pick another pair. After RxEADY, the largest MOS losses
  are GUESS_THE_TEACHER's and KAINANG_PAMILYA's event IDs (−1.00 and
  −0.92).

**Also saved:** the notebook's own views (`nb_*`), as the notebook draws
them, with titles. They are for reference, not print.

### F2. The dashboard screenshots (`manuscript/Images/`, from the user)

All three are 1782 × 877 px, about 300 dpi at 6 inches wide.
- **The poster:** CTC ("CTC Got Talent"), one of the Phase 4 posters.
- **The content:** made up ("Luke", "Contestant"); no names from
  `data/raw/ID_layouts/` or the packets.

| File | Step | What it shows (for the figure text, M17/M24) |
|---|---|---|
| `Perceptual Ingestion.jpeg` | Step 1 (Figure 2) | The step bar along the top, and Target Initialization in the top bar. **Left:** the Master Layout preview, with K-Means Color Centroids (three swatches with hex codes) and SIFT/SURF Keypoints (saliency 0.0245, logo detected: yes, size 1313×1313) beneath. **Right:** the detected organisation logo and the Stage 0c stylistic markers (text-free background, title artwork) as ticked tiles; Administrative Typography (Lato, 700 Bold, 48 px) in one row; and the Content Payload for the event ID. |
| `Active Orchestration.jpeg` | Step 2 (Figure 3) | **Centre:** the event ID canvas, with the Event Title selected and its resize handles shown. **Beneath it:** the Recommendations strip of six candidates ranked by Formula 3.11. **Right:** the Selected Element panel (undo and redo, "Event Title · Hard · manual override", X 64, Y 313, W 616, H 263, Edit text, Release (Soft)), the typography, and Canvas details. **Top bar:** Timeline (the State Timeline opens as a dialog), Step 1, Download, Evaluate. |
| `Evaluation Report.jpeg` | Step 3 | **Left:** the evaluated layout, with SVG / PNG / PDF downloads. **Right:** the headline tiles (Fitness C_total 0.1591, Structural accuracy F1 1.00, Manual edits kept 5/5, median edit latency 93 ms), the Formula 3.11 table (your layout against Candidate E), Manual refinements kept, and the F1 table per element. |

**For the manuscript:**
- **Figure 2's text (p.57)** still says "central viewport" and "right-hand
  panel". The screenshot shows the master on the left and the cards on
  the right, with target selection in an overlay from the top bar.
- **Figure 3's text (p.60)** still says "two critical computational tabs"
  and a timeline below the Constraint Editor. The screenshot shows one
  right panel, the recommendations under the canvas, and the timeline
  behind the top bar's Timeline button.
- **Step 3** could become a third figure, since p.60 describes the
  Evaluation Report in words only.
- **The Step 1 screenshot labels the card "SIFT/SURF Keypoints".** If item
  3.10 rewords the manuscript to SIFT only, the dashboard's label should
  change too. Tell the development chat.
- **Two display glitches in the Step 3 screenshot are fixed in the code**
  (2026-10-10):
  - the C_total row's Weight column showed "None";
  - the caption under the layout printed "[{{Event_Details}}]".

  Re-take that screenshot after restarting the dashboard if it goes in the
  manuscript.

### F3. Dashboard changes after the screenshots — 2026-10-10 (notes §3.52)

- **SIFT only:**
  - The Step 1 card now reads "SIFT Keypoints". The dashboard no longer
    names SURF.
  - That leaves item 3.10's choice with the manuscript: reword "SIFT/SURF"
    to "SIFT" (pp.40, 56–57, 59, 65 and the Project Dictionary), as the
    system and now the dashboard show.
- **Condition names:** the dashboard uses Chapter 4's names.
  - The full name, "structure mapping + GNN", appears in the Target
    Initialization toggle and in the Step 3 caption.
  - The top bar uses the short form, "mapping + GNN".
  - The baseline is "baseline".
- **Thumbnails:** the Recommendations strip now shows the canvas's current
  words after a text edit. The earlier screenshot had "ANGELA" thumbnails
  under a "LUKE" canvas.
- **Re-take all three screenshots in `manuscript/Images/`** once the
  dashboard is restarted, so the figures match the system:
  - Step 1 shows "SIFT/SURF Keypoints";
  - Steps 2 and 3 show "GNN-guided" in the top bar;
  - the Step 2 strip shows stale names.

---

## G. Final checklist: what the manuscript still needs — 2026-10-10

**Start here.** This section consolidates everything still missing or
wrong, as of:
- **Manu 1010.1** and its LaTeX (`manuscript/Thesis Latex/`, commit
  `5015202`, unchanged since);
- **the system** at `f97d897`;
- **`results/`.** None of the numbers Chapter 4 cites have changed since
  1010.1; only the figures were added.

Both test files pass. Details are in the sections referenced; "p." is Manu
1010.1's page.

### G1 🔴 Errors to correct

1. **p.81, ANTI_HAZING_LAW (E1).** It says the CLOSED stamp and the title
   cut-outs "were corrected" in the Phase 4 set. They were for CMET and
   SIGN_LANGUAGE_DAY; ANTI_HAZING_LAW's corrections were lost, as p.93 says.
   Add the exception.
2. **Eleven citations print as raw keys in the Prism PDF (E2):**
   "[Badros2001Cassowary]", "[schmidt1997managing]", "[kerby2014simple]",
   and others on pp.10–99.
   - The local `thesis.pdf` resolves all of them, so only Prism's copy of
     `references.bib` is out of date.
   - Upload the current `references.bib` to Prism and rebuild.
3. **The title page says "May 2026"** (`thesis.tex`:
   `\makeTitlePage{May}{2026}`). Set it to the defense month. The approval
   date is still the template's "January 1, 2000", and the approval page is
   commented out; fill both in when the defense is scheduled.

### G2 🟡 Wording to fix

| Page | Now | Fix | See |
|---|---|---|---|
| p.78 | "[PENDING: server GPU]" | an NVIDIA RTX A5000 (24 GB) | E3 |
| p.99 | "The system was not changed after the rating" | the layout generation wasn't. The dashboard (labels, thumbnails, the Phase 4 page, the elbow graph) and a speed cache changed later, with the generated layouts byte-identical. Table 13's latency was measured with the cache. | E4, F3 |
| p.29 | the GNN "within a live orchestration loop" | the GNN runs once, when a layout is opened; edits re-solve Cassowary | E5 |
| p.30 | "AAPA and GNN compositional scoring … aesthetically validated layout candidates" | drop "GNN compositional scoring"; "fitness-ranked layout candidates" | E6 |
| p.28 | candidates ranked "in real-time" | "when a layout is initialized" | E6 |
| p.90 | "at most five signature blocks because the content schema set no upper limit" | "the row held at most five signature blocks without overlap, and the content schema set no upper limit on their number" | E7 |
| p.92 | "about 0.002 … the floating card about 0.185 against 0.149" | "0.003 … 0.187 against 0.149 for the left-aligned layout" | E8 |
| p.64 | FN "or the relational graph of the master template"; FP "overlapping an immutable designer-locked node" | only the payload mandates elements; an overlap with any element is an FP (as p.86 says) | E9 |
| pp.6–7 | Significance: "This study will benefit …", "will provide …" | the past tense (M11). "Maintains mathematical visual harmony among all the formats" holds for the constraints (F1 1.0); Phase 4 found the experts preferred the baseline's spacing, so consider "keeps every element within its constraints across formats". | M11 |

### G3 Content to add

1. **Figures 2 and 3 (pp.57, 60).**
   - **The images:** the chapter still includes the May mockups
     (`figures/ts1.png`, `ts2.png`, `ts3.png`). Replace them with the
     screenshots in `manuscript/Images/`, re-taken on 2026-10-10 after the
     dashboard fixes:
     - `Perceptual Ingestion.jpeg` → Figure 2;
     - `Active Orchestration.jpeg` → Figure 3.
   - **The text:** rewrite both descriptions to match ("central viewport",
     "two critical computational tabs" no longer apply). F2 says what each
     screenshot shows.
   - **Optional:** a third figure for the Evaluation Report
     (`Evaluation Report.jpeg`), which p.60 describes in words only.
2. **Figures for Chapter 4,** which has only tables now. The seven
   `results/figures/fig4_*` (PNG at 300 dpi + PDF) are listed in F1 with
   suggested places.
   - Label `fig4_spacing_vs_mos` as exploratory.
   - Decide whether `fig4_example_pair`'s licensed cartoon characters can
     be printed under fair use; GUESS_THE_TEACHER's event ID is the next
     example.
3. **Chapter 5 (Summary, Findings, Conclusions, Recommendations,** per the
   TSA's guide). `chapter5.tex` is still the template's placeholder (a
   sample galaxy figure) and is commented out in `thesis.tex`.
   - **Findings:** restate Chapter 4's numbers per objective (D1–D7).
   - **Recommendations** the results support:
     1. spread the remaining space evenly after anchoring the master's
        positions (Phase 4, §3.49);
     2. add a gap-evenness term to Formula 3.11, whose differences didn't
        follow the experts' (ρ = −0.20);
     3. rate structure mapping only against structure mapping + GNN with
        experts, which this design couldn't separate;
     4. fit the event ID header to its box's width; cap the signature
        blocks at five and limit their text (stress test, D2);
     5. derive R_target from the master, or report it as a fixed design
        choice (D6);
     6. per-element colour and saliency features for the GNN (Appendix A,
        item 3.12);
     7. retrain the aesthetic CNN on the 768 expert ratings now available
        (item 3.11);
     8. faster re-solving edits through cheaper legibility scoring (48%
        within 0.1 s, D3);
     9. validate the detector beyond 40 campus images, with clearer
        underlay and embellishment definitions (D1);
     10. more raters, or a calibration round, to raise the absolute
         agreement (ICC(2,1) 0.16–0.31, D7).
4. **An abstract,** if CSPC's format requires one. The manuscript has none.
   It would have to report the Phase 4 result as found.

### G4 Decisions still open (the group, or the TA)

- **3.10 SURF.** The dashboard now says "SIFT Keypoints" (F3), and only
  SIFT runs. Reword "SIFT/SURF" to "SIFT" on pp.40, 56–57, 59, 65 and in
  the Project Dictionary.
- **3.11 CNN (p.39), "deployed for quantitative aesthetic evaluation".**
  Nothing in the system uses it. Describe it as trained by distillation and
  not deployed, or move it to future work (G3, recommendation 7).
- **3.12 Formula 3.6 and Appendix A.** These describe c_i and s_i per
  element; the GNN gets one colour and one saliency value per layout.
  Reword, and list it as a limitation.
- **p.87, the certificate's paper size ([PENDING]).** US Letter landscape
  was assumed; on A4, every point size in Tables 11–12 is 6% larger.
- **The stress test's two renderer limits.**
  - Chapter 4 reports them as limitations, which is accurate.
  - Fixing the header fit would change how two rated event IDs render.
    Keep them as limitations unless the group wants the fix, and the
    rewording of p.99 that goes with it.
- **The manifest's guesses,** printed on the rated pages: ANTI_HAZING's
  university, CMET's year, "DEBESMSCAT", and the blank dates on
  DEAR_SENDER, LUCKY_TERA and SHARE_KO_LANG. Confirm them for the record.
- **`notes/manuscript_revision_list.md`** was last re-checked against
  Manu 0910.1. Re-check it against 1010.1 the same way.

### G5 Already in the manuscript (no action)

- **Chapter 3:**
  - the statistical treatment (exactly what `phase4_analysis.py` runs, and
    committed before the import);
  - p.55's stress-test design and p.62's two latency limits;
  - Cassowary re-solving on every event (M22) and the vertical-centre error
    (M6);
  - R_target fixed at 0.65 (M19), and the conditions named with both
    modules off (M4, M5);
  - the normalisations (M20);
  - "event identification cards".
- **Appendix B** is identical to the system's payload.
- **Chapter 4:** every number in Tables 3–21 and the text matches the
  results files (E, "Checked and correct").

---

## H. Manu 1210.1 checked against the system — 2026-10-12

**Start here for 1210.1.** The development chat checked the final
manuscript, `manuscript/Manu 1210.1.pdf` (111 pages), against the code and
`results/`. The code is unchanged since `f97d897` (2026-10-10); later
commits touched only notes, PDFs and two dashboard uploads.
- **Chapter 3:** read in full.
- **Chapters 1, 2 and 5:** read for system claims.
- **Chapter 4:** every number new since 1010.1 recomputed from the
  results files. Tables 5, 9 and 12 rechecked in full; the rest were
  checked on 1010.1 and haven't changed.
- **Both test files pass** (12 tests).

"p." is Manu 1210.1's page. Nothing below changes a result; all five are
wording.

### H1 🟡 "Manual edits survive global theme updates" is only partly true

**Where:**
- p.4: "brand updates propagate across publication formats";
- p.5: "global theme updates were mathematically synchronized without data
  loss";
- p.27: "refinements survive global theme updates";
- p.28: "persist through global synchronization events";
- p.57: "during automated global updates".

**Fact:**
- **Typography changes keep every manual edit.** `set_typography`
  re-renders the current layout, Hard nodes included.
- **Selecting another candidate opens that candidate's layout.** Earlier
  edits aren't carried over to it. They stay in the chain, and undo or the
  State Timeline restores them.
- **Palette, logos, markers and the target format are set in Step 1.**
  Changing them means a new Initialize, so a new layout and a new chain.
  The old one stays saved in its session folder.
- **One format is open at a time.** A brand change reaches each format
  when that format is initialized.

**Fix (suggested):** name what the system did.
- p.5: "typography updates and manual refinements were synchronized
  without data loss".
- p.27: "survive typography updates and every later re-solve".
- p.28: "persist through every later re-solve".
- p.57: "during later re-solves".
- p.4: "brand updates reach every format initialized from the master".
- **Anywhere it fits:** no update erased an edit, since every earlier
  state stayed in the chain and could be restored.

**Not changed in the code:** carrying Hard nodes onto a newly selected
candidate would add a re-solve to candidate selections. Chapter 4 timed
those as re-draws (Table 12, Figure 7).

**For a demo:** move an element, then change the typography. The edit
stays.

### H2 🟡 p.40 and p.44: a re-solve "on every terminal user event"

**Now:**
- p.40: "the whole layout was re-solved on every terminal user event";
- p.44: e_t includes "direct text edits", and δ triggers "the Cassowary
  recalculation".

**Fact:**
- **Only moves, resizes and locks re-solve** (`pipeline.apply_event`).
- **Text edits, typography changes, undo, redo, restore and candidate
  selections only re-draw.** The boxes don't change; the renderer fits the
  new words to their box (`edit_text`).
- p.59 and p.89 already say so.

**Fix:**
- p.40: "on every terminal move, resize, or lock".
- p.44: "… to trigger the Cassowary recalculation for a move, resize, or
  lock; a text edit was re-validated against the content schema and
  re-drawn in its box".

### H3 🟡 p.10, the Project Dictionary: "the rule of thirds"

**Now:** the Fitness Function checks "design rules such as the rule of
thirds and the ratio of whitespace".

**Fact:** Formula 3.13's grid is the content area's margins, quarters and
centre (p.48, `optimization_engine.calculate_alignment_penalty`). No term
uses thirds.

**Fix:** "such as alignment to a structural grid and the ratio of
whitespace to other elements".

### H4 🟡 p.66 promises mean ± SD for fitness and latency; Chapter 4 no longer gives them

**Now:** Statistical Treatment item 6 says the fitness, latency, F1 and
IoU "were summarized by their mean and standard deviation". 1010.1's
Chapter 4 reported all of them; 1210.1's rewrite dropped those for the
fitness (Table 13 gives means only) and the latency (Table 12 gives
medians).

**The numbers** (`results/phase4_analysis.json`, `q11_phase3`):

| Measure | Structure mapping + GNN | Baseline |
|---|---|---|
| Fitness, both formats | 0.0879 (SD 0.0791) | 0.0855 (SD 0.0766) |
| Fitness, certificate | 0.0125 (SD 0.0250) | 0.0126 (SD 0.0251) |
| Fitness, event ID | 0.1633 (SD 0.0133) | 0.1583 (SD 0.0135) |

- **Latency:**
  - constraint recalculation: 0.53 ms (SD 3.01, inflated by the one solve
    the operating system paused);
  - full edit: 90.6 ms (SD 57.5).
- **F1:** 1.0 (SD 0).
- **IoU:** 0.644 (SD 0.351), already on p.79.

**Fix:** either add the mean ± SD as a note line under Tables 12 and 13
(no extra page), or reword item 6: "the fitness was summarized by its mean
and SD, the latency by its median and 95th percentile".

### H5 ⚪ p.56: logos and markers "each of which the designer could keep, remove, or replace"

**Fact:**
- Logos can be added by upload, and the title artwork replaced.
- The background and the motifs can only be kept or removed.

**Fix (optional):** "kept or removed, with uploads for missed logos and a
replacement title artwork".

### Checked and correct

- **Sections E–G are applied:**
  - E1 (p.80, "except on ANTI HAZING LAW");
  - E3 (RTX A5000, p.90);
  - E5 and E6 (pp.27–28);
  - E7, E8 and E9;
  - SIFT only, the CNN removed, c_i and s_i per layout;
  - the cover month, October 2026.
- **The text is clean:** no raw citation keys, "PENDING", "??" or "et al.".
- **Chapter 3 matches the code:**
  - **Extraction:** K-Means (k = 2 to 6, best of five seeded runs, the
    elbow); SIFT's ranking and saliency map; the background rebuilt from
    the borders.
  - **The GNN and the state chain:** Formulas 3.6–3.8 (MLP message, mean
    aggregation, GRU update, four edge features); the append-only chain
    with undo and redo as new states; Formula 3.10.
  - **Validation and scoring:** the schema (Draft 2020-12, weights 100 to
    900, 8 px to 15% of the shorter side, max_characters); Formulas
    3.11–3.15 with their exclusions, the content region and R_target 0.65.
  - **Candidates:** six per format (archetype, margin, gap, motif
    arrangement); the archetype from the master's composition, and the
    lowest fitness without a master.
  - **The dashboard:** Figures 2–4's descriptions, apart from H5; the
    Step 3 report's six items.
  - **Phase 4:** the packets (random codes, a page order per expert, no
    two pages of one poster adjacent); the statistical treatment,
    including the identical-pair check and the fitness Wilcoxon.
  - **Appendices:** A (the record's fields) and B (identical to
    `data/raw/academic_payload.json`); the event ID's A6 page and indices
    0 to 5.
- **Chapter 4:** Figure 6's ranges (0.023–0.037 and 0.043–0.087 reduction;
  0.008–0.118 and 0.000–0.115 remaining), Table 9's means, Tables 5 and 12,
  the 348 re-draws, and 10,788 elements (23% unmapped) all match.
- **Chapter 5's** numbers are Chapter 4's (0.0879 against 0.0855 is the
  mean of Table 13's two formats).

---

## I. Five dashboard features added after Manu 1210.1 — 2026-10-13

The user asked for five dashboard features the night before the pre-oral
defense; they're in notes §3.53. **Nothing in the manuscript has to
change:**
- None of them changes how a layout is generated, solved or scored.
- The rated layouts and every Chapter 4 number stand.
- Without a style, the renderer's output is byte-identical to before.

"p." is Manu 1210.1's page unless the table says 1210.2 (`5825b47`, which
applied H1 and H5).

### What was added

1. **Fonts that exist everywhere.**
   - **The bug fixed:** Step 1 offered six fonts, but only Montserrat
     existed; the other choices silently fell back to another font.
   - **Now:** Lato, Open Sans, Playfair Display and Merriweather ship with
     the system, and Tinos replaces Times New Roman. They render the same
     on the server and on Windows.
   - **The picker:** in Steps 1 and 2, each font is shown in its own
     typeface. Step 2's free-text "Font family stack" field is gone.
2. **Mail merge.**
   - Step 1 takes a CSV whose columns name content fields (names, roles,
     anything else).
   - Each row is checked against the content schema, and failing rows are
     left out.
   - The designer edits one layout, with placeholders such as «Participant
     Name».
   - Step 2's Download menu gives a ZIP with one PNG or PDF per row.
3. **Style tools in Step 2's right panel.**
   - **For text:** colour (the poster's palette first), bold, italic and
     alignment, with a contrast warning.
   - **For pictures:** replace, flip and opacity.
   - **Each change is one state in the chain** (a re-draw, like a
     typography change), so undo and the State Timeline cover it.
4. **Drop an image on a Step 1 tile to replace it:** logos, the
   background, the title artwork and motifs.

### Where the manuscript touches them (all optional)

| Page | Now | Note |
|---|---|---|
| 1210.2 p.56 (Figure 2's text) | logos and markers "each of which the designer could keep or remove, with uploads for missed logos and a replacement title artwork" (H5 applied) | Now every tile can be replaced by dropping an image on it. The background could never be removed: it has no tick box. Exact: "each of which the designer could keep or replace by dropping an image on it, and remove, except the background". |
| p.58 (Figure 3; 1210.2 p.59) | the screenshot shows the typography box open, with "Font family stack" | That control is now a font picker, and a Style section sits under the selected element. p.59's text stays true. A retake is optional. |
| p.59 (Figure 3's text) | the right panel's controls | Doesn't mention the Style tools. Optional: "…a control for editing its text, its style (colour, weight, alignment; for pictures, replace, flip and opacity), and the choice between…" |
| p.44 (Formula 3.9) | e_t "includes" moves, resizes, locks and text edits | A style change is another terminal event; "includes" already allows it. |
| p.8 (Scope) | "merge … with external administrative datasets … to generate fully populated, variable-driven documents" | The CSV mail merge does this literally. It could be named here or under Phase 2. |
| H1 (sent 2026-10-12) | edits survive "global theme updates" | Styles, like typography, now survive candidate switches. Moves and resizes still don't carry over to another candidate. |

**For the defense:** these features came after the evaluation. If the
panel asks why the manuscript doesn't describe them, that's the answer.
The experts rated layouts made without them.
