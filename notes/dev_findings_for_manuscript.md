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
2. **The stress test** (p.55; M3). The development chat will build it
   unless the group drops the claim. Tell it if you do.
3. **The latency benchmark** (p.62; A5 above): solver and full-edit
   timings over many edits, against 0.1 s and 1.0 s.
4. **F1 over the 64 rated layouts in the results files** ("Code before
   Chapter 4").
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
