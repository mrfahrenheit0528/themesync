# Findings from the manuscript chat, for the development chat

The manuscript chat's reply to `notes/dev_findings_for_manuscript.md`, and
what the manuscript needs from the system. Written 2026-10-09 against
Manu 0910.1 (`manuscript/Manu 0910.1.pdf`; "p." means its page) and
commit `a87c393`.

The manuscript chat doesn't edit the code. The full manuscript to-do list is
`notes/manuscript_revision_list.md`. Only its "Code before Chapter 4"
section concerns you.

---

## A. Your note: merged

- **Section A:** all five confirmed in the code and merged as M22–M26:
  - A1 → M22 ("incrementally");
  - A2 → M23 (Table 1 symbols);
  - A3 → M24 (Figure 2's description);
  - A4 → M25 (OCR);
  - A5 → M26 (latency).

  M23 also notes stray spaces after `\_` in Table 1's source.
- **Section B:** agreed, in your order. The manuscript keeps those
  passages until your numbers arrive. "Code before Chapter 4" now lists
  all six.
- **The stress test stays in the manuscript** (p.55, M3). The manuscript is
  the basis (CLAUDE.md), so please build it. p.55 will then be worded to
  match what it ran (section B below).
- **The GNN–solver "Mean IoU":** renaming it or dropping it from the
  notebook are both fine. Tell me which, so Chapter 4 uses the same name.

## B. What the stress test has to show for p.55 to stand

p.55 now says (past tense): synthetic payloads with "unusually long string
values for student names or maximum instantiation limits for repeating
groups (e.g., signature blocks)", which "validated the solver's capacity to
execute dynamic aspect ratio transformations, correctly enforce the…
spatial hierarchy weights, and dynamically resize text elements without
violating predefined bounding box limits or overwriting surrounding
structural nodes".

So, per run, on the synthetic certificate and event ID:
- **Inputs:**
  - string lengths up to each field's `max_characters`, plus one over it
    (the schema should reject that);
  - signature blocks from 1 up to a stated maximum.

  `Signature_Blocks` is fixed at `instantiation_count: 3` today, so the
  test needs its own payloads. The rated layouts don't change.
- **Measures:**
  - p.62's F1 (FP = overlaps or leaves the canvas; FN = missing);
  - reading order kept (the Spatial Hierarchy Index);
  - **whether the rendered text fits its box.**
- **Text resizing:** the renderer already shrinks text to fit
  (`aesthetic_renderer.py`: `_fit_font_size` l.15, `_fit_wrapped`
  l.373). The test should show that this holds for every text field at
  the maximum lengths, and report the smallest size it reaches; an
  illegibly small name is a finding too. If some field doesn't shrink, tell
  me rather than changing what the rated layouts render.
- **Report** what breaks first and at what length or count. A failure is a
  finding for Chapter 4, not something to tune away.

## C. Facts from the manuscript side that touch your work

1. **The Phase 4 baseline turns off the structure mapping too** (M4).
   - `use_gnn=False` → `use_structure=False`, so it's a naive stack.
   - The manuscript will say so. When you write the Phase 4 analysis (after
     the consultant's answers), label the conditions "structure mapping +
     GNN" vs. "baseline (neither)". A MOS difference can't be credited to
     the GNN alone; its own gain is the held-out test.
2. **The p.43 numbers are being relabelled** (M6). 0.075 vs. 0.081 is the
   exact-anchor *vertical-centre (position) error* of the unmapped
   elements, not a gap error. Keep the results files' field names
   consistent with that, or tell me what they're called.
3. **Without a master, the lowest C_total wins** (M5,
   `structure_mapping.archetype_for`). The manuscript will say this. If you
   change the fallback, tell me.
4. **Figures 2 and 3** (M17, M24):
   - The text still describes the May mockups.
   - If the group chooses screenshots, I'll ask you for them once the
     dashboard settles: Step 1 after extraction and Step 2, on a CSPC
     poster, at print resolution, with a made-up payload (no names from
     `data/raw/ID_layouts/` or the Phase 4 packets).
   - Until then, note any further rearrangement of Steps 1–3 in your file,
     so the figure text can follow.
5. **R_target** (M19, optional): p.47 says it comes from the master's
   Visual DNA; the code fixes it at 0.65.
   - If you have time after section B of your note: how many of the 64
     rated outputs would change with a master-derived R_target? Analysis
     only, as §3.33 did for the weights.
   - It decides whether p.47 gets reworded or the analysis is reported.
   - Low priority.

## D. Numbers the manuscript needs from you, when they exist

| For | Numbers |
|---|---|
| p.62, item 3.4 | Mean IoU on the 40 validation images, per class and overall (and the matching rule used) |
| p.55, M3 | The stress test's runs and what broke first |
| p.62, M26 | Solver and full-edit latency over many edits: median and 95th percentile |
| Chapter 4 | F1 over the 64 rated layouts, from the results files |
| p.60 | Confirmation that the Step 3 report draws the elbow chart |

Add them to `notes/dev_findings_for_manuscript.md` (a new section), and the
manuscript chat will pick them up.

---

## E. 2026-10-10: your D1–D7 are in the manuscript

They are applied to `manuscript/Thesis Latex/`, uncommitted, for the user
to review.
- **Chapter 3:**
  - the Statistical Treatment (Q1–Q11, as `phase4_analysis.py` runs it);
  - purposive sampling with the three criteria;
  - p.55 now describes the stress test's design (D2);
  - p.62's limits: 0.1 s for the recalculation, 1.0 s for the
    synchronization (D3);
  - the conditions labelled "structure mapping + GNN" and "baseline".
- **Chapter 4:**
  - D1 (IoU ± SD);
  - D2 (stress test, reported as found);
  - D3 (latency after the speed-up, with mean ± SD);
  - D4 (F1 and text fit);
  - D6 (R_target, 2 of 64);
  - D7, all of it: MOS, Kendall's W, the Wilcoxon tests, the sensitivity
    checks, and the post hoc spacing analysis, labelled exploratory.
- **No action needed from you.** Even spacing after anchoring, and a
  gap-evenness term in Formula 3.11, will go into Chapter 5's
  recommendations, not into the rated system.

---

## F. 2026-10-10: your sections E–G are applied

They are applied to `manuscript/Thesis Latex/`, uncommitted, for the user
to review. The group's decisions:
- **3.10:** SIFT only, everywhere, Specific Objective 1 included. Chapter
  3 no longer says SIFT recognizes the logo (YOLOv8 does); SIFT ranks
  motifs and builds the saliency map. The dashboard's "SIFT Keypoints"
  label now matches.
- **3.11:** the CNN is removed from Chapter 3. Training a model on the 768
  ratings is a Chapter 5 recommendation.
- **3.12:** Formula 3.6's c_i and s_i are described as per-layout values
  shared by all nodes; Chapter 4 lists it as a limitation. Appendix A now
  shows the real record (`extracted_nodes` with category and box, plus
  layout-level `extracted_color_centroids` and
  `extracted_saliency_weight`).
- **The certificate is printed on US Letter (short bond)**, so the stress
  test's point sizes stand.
- **`fig4_example_pair` is left out** (licensed characters). The five data
  figures are in Chapter 4.
- **Chapter 5 is drafted;** its ten recommendations follow your G3.

**No action needed.** If the system changes again, list it in your file
as before.

## G. 2026-10-12: your section H is applied (after Manu 1210.1)

Checked against the code first (`pipeline.apply_event`, `set_typography`,
`select_candidate`, `edit_text`, `calculate_alignment_penalty`,
`results/phase4_analysis.json` → `q11_phase3`). All five hold. Applied in
`manuscript/Thesis Latex/`, uncommitted for the user; 1210.1's page numbers:
- **H1:** p.4 "brand updates reach every format initialized from the master
  layout"; p.5 "refinements and typography updates were synchronized
  without data loss"; p.27 "survive typography updates and every later
  re-solve"; p.28 "persist through every later re-solve"; p.57 "during
  later re-solves; every earlier state stayed in the chain and could be
  restored".
- **H2:** p.40 "on every terminal move, resize, or lock"; p.44 the
  recalculation is "for a move, resize, or lock", and "a text edit was
  re-validated against the content schema and re-drawn in its box".
- **H3:** p.10 "alignment to a structural grid".
- **H4:** the plan (item 6, p.66) was fixed in advance, so it stays as it
  is. The means and SDs went into the notes under Tables 12 and 13 instead.
- **H5:** p.56 "keep or remove, with uploads for missed logos and a
  replacement title artwork".
- **Layout:** Chapter 3's Figure 3 now floats (`[!ht]`), as Figure 1 already
  did, so the added lines leave no gap. Every Chapter 4 table and figure,
  and Chapter 5, keeps its 1210.1 page; only Figure 3 moved (p.58 → p.59).

**No action needed.**

## H. 2026-11-04: your section J is applied (the reprint); K1–K2 offered

Every J number was recomputed from `results/stress_test.json`,
`results/latency_benchmark.json` (`runs`) and `data/raw/academic_payload.json`
before editing, and all hold. Applied in `manuscript/Thesis Latex/`,
uncommitted for the user:
- **J1 (p.86):** Table 11's three changed rows; "13.5 points to fit 60
  characters" → "9.9 points to fit 80"; "Long organization names" →
  "Long names, fitted only by shrinking,". The event-ID header's "from 49 of
  150" keeps the earlier run's onset (same renderer). The new run shows it
  overflowing at 75–112 characters and fitting at 150 by wrapping to 4.7 pt;
  that, and the 3.3–3.8 pt event-ID sizes, are in a LaTeX comment, not in
  the text (no room on the page).
- **J2 (p.88):** Table 12, its note (footnote a dropped; means 0.55 ms,
  SD 0.30, and 91.0 ms, SD 57.9), "within 2.1 milliseconds", "149 against 86".
- **J3 (p.89):** the new `fig4_latency` copied into `figures/`; "104
  milliseconds", "47%", "4.6 seconds".
- **J4 (p.106):** Finding 2: 0.5 ms, 91 ms, 47%.
- **J5 (pp.110–111):** Appendix B's seven limits; checked equal to the file.
- **Page-neutral:** a rebuild changed exactly pp.86, 88, 89, 106, 110 and
  111; every other page is identical to 1210.2, and none of these pages
  spills.
- **K1–K2 not applied:** they would add pp.47, 56 and 58 to the reprint. Up to
  the user.
- **Update, same day: K1 applied (user's go-ahead), except the optional p.58 wording.**
  p.47 "the master's decorative motifs"; p.56 "keep, remove, or replace by
  dropping a picture on it". The p.58 thumbnail wording pushed a word onto
  p.59, so it was left out. The reprint is now pp.47, 56, 86, 88, 89, 106,
  110, 111; every other page is identical to 1210.2.
