# Findings from system development, for the manuscript chat

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
5. **"the K-Means elbow graph"** in the Step 3 report (`chapter3.tex:417`,
   p.60). The report shows a table of WCSS per k; the development chat
   will add the chart, so this sentence can stay.
6. **The GNN–solver "Mean IoU"** ("Code before Chapter 4"): the
   development chat will rename it, or take it out of the notebook.

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

### D3. Latency over many edits (p.62; M26, A5) — 2026-10-09

`src/evaluation/latency_benchmark.py` → `results/latency_benchmark.json`;
notes §3.43.

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

| | edits | median | 95th percentile | max | within 0.1 s | within 1.0 s |
|---|---|---|---|---|---|---|
| solver | 1,012 | 0.4 ms | 0.8 ms | 1.8 ms | 100% | 100% |
| full edit | 1,360 | 157 ms | 338 ms | 393 ms | 22% | 100% |
| full edit, certificate | 680 | 220 ms | 370 ms | 393 ms | 19% | 100% |
| full edit, event ID | 680 | 143 ms | 223 ms | 298 ms | 25% | 100% |

**For the text (M26):**
- **The solver met the 0.1 s limit on every edit.**
- **A full edit met the 1.0 s limit on every edit,** but not 0.1 s:
  about 0.17 s for a move or resize on a poster's theme. The cost is
  re-drawing and re-scoring the poster's background. On the synthetic
  theme a full edit took 4 ms.
- **Suggested wording:** "constraint recalculation within 0.1 s, state
  synchronization within 1.0 s".
- **Not a per-edit figure:** opening a layout (Initialize, Stages 0–6)
  took a median of 3.6 s, once per layout.

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
