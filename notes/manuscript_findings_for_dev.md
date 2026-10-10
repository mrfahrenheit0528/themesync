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
