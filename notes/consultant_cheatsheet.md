# Consultant Chat Cheatsheet

Revised 2026-09-22: consultation is happening over **Google Chat**, not live,
so this is no longer a presentation script — it's ready-to-send message
text. Copy each block below as its own chat message (or combine a few if
that reads better to you); nothing here assumes she's watching a screen
share or hearing you talk, so anywhere the old version said "show her the
diagram," this version either describes it in words or tells you to attach
a screenshot instead.

**Status check before you send anything — read this first:**
- [x] YOLO dataset fix applied and re-verified, **and the real retrain is done** — `themesync_yolo_v3.pt`, mAP50 0.370 (up from v2's 0.320). Full numbers: `gnn_fixes_and_methodology_notes.md` §3.12.
- [x] `mos_collector.py`'s dimensions fixed to match the manuscript's 3 named parameters, with Table 2 shown to the evaluator (fixed 2026-09-26, `gnn_fixes_and_methodology_notes.md` §3.13). Message 6 is now safe to send.
- [x] Citations verified against primary sources (2026-09-28): `notes/mos_parameter_grounding.md`. They're verified but **not yet in the manuscript**, so present them in chat as sources you're adding.
- [ ] Ask the TA about 1 expert vs. 3–5 before sending Message 3.5's evaluator line (see `adviser_consultation_checklist.md` §D2).

---

## Message 1 — Open

> ThemeSync takes a poster's visual identity — its colors, logo, style —
> and automatically reapplies it onto a different document, like a
> certificate or ID, using AI to keep the result legible and balanced, then
> has a real design expert confirm the output is genuinely good, not just
> mathematically valid. I'd like to walk you through how we're validating
> the data and instruments behind it.

## Message 2 — The 4 phases, one theory each

> The system is built in 4 phases, each grounded in its own theory (Figure
> 4 in the manuscript, p. 59 — happy to send a screenshot if useful):
> 1. Phase 1 (Graph Theory) — turns the poster into a structured graph:
>    K-Means + SIFT/SURF for style, YOLOv8 + OCR for elements, a GNN
>    trained on CGL-Dataset for spatial relationships.
> 2. Phase 2 (CSP / Automata Theory) — solves the real layout in real time
>    without breaking manual edits.
> 3. Phase 3 (Optimization Theory) — generates candidates, scores them
>    with a fitness function, renders the winner.
> 4. Phase 4 (HCI Theory) — a real design expert rates the output, since
>    math alone can't confirm something looks good.

*(Optional attachment: a screenshot of manuscript p. 59's Figure 4.)*

## Message 3 — Defending the CGL-Dataset (public training data)

> Our GNN's training data is CGL-Dataset, a public benchmark built
> specifically for content-aware graphic layout generation — the same
> problem our Phase 1 solves, not a general-purpose scrape. It's already
> named as a formal research instrument in our Chapter 3 (p. 46).

> It's peer-reviewed. CGL-Dataset V2 was published by Li et al. at CIKM
> 2023 (an ACM conference). It extends the original CGL-Dataset from Zhou et
> al. at IJCAI 2022, which introduced the logo/text/underlay/embellishment
> classes we also use for our own annotations. It has 60,548 annotated
> training posters. Chapter 3 names the dataset but doesn't cite it yet;
> we're adding both references.

## Message 3.5 — Update from our TSA consultation

> Quick update: our Thesis Subject Adviser raised similar grounding
> questions last week — whether our Phase 4 MOS scoring (the Likert scale,
> our 3 rating dimensions, and who evaluates) is backed by actual
> literature, and whether our annotated dataset has been checked by anyone
> besides our own group. We're addressing both.
>
> For the scale: Table 2 is adapted from ITU-T Recommendation P.800, the
> standard that defines MOS (its 5-point Excellent-to-Bad scale).
>
> For the 3 parameters: each maps to an established layout-quality
> criterion. Visual hierarchy and whitespace/overlap come from O'Donovan
> et al. 2014 (IEEE TVCG) and the CGL-GAN paper behind our dataset. Brand
> consistency comes from Wheeler's *Designing Brand Identity*.
>
> For the evaluator: our sources point to 3–5 expert raters rather than
> one (Nielsen & Molich 1990). We're raising that with our adviser now.
>
> We've also sent our annotated sample out for expert review.

## Message 4 — Defending the annotated master-layout batch (124 images)

> Our own annotated dataset (124 real event-poster images) is grounded in
> three ways: (1) it reuses CGL-Dataset's own 4-class taxonomy rather than
> inventing categories, (2) the annotation protocol is written down with
> thresholds calibrated against real CGL box statistics, not eyeballed,
> and annotators spot-checked each other's early work, and (3) most
> importantly, fine-tuning on it produced a measurable, real improvement
> on held-out images never seen during annotation — mAP50 rose from
> functionally zero to 0.325 on the first 65-image batch, and to 0.370
> after scaling to 124 images, with logo detection reaching 0.620 and text
> 0.595. Inconsistent labels don't produce a result like that. On top of
> that, we've sent a sample of 15 annotated images, along with our class
> definitions, to an outside graphic design expert for independent
> validation. We'll share the result once it's back.

## Message 5 — The data-quality catch (send this — it's a good story, not a confession)

> Worth mentioning: when we scaled the annotation batch to 124 images, we
> found and fixed a real export inconsistency before using it — some
> images had mixed annotation formats that would have silently dropped
> ~23% of the batch during training, and a class-index reordering that
> would have corrupted the model's existing learning. We caught both with
> an actual test run, fixed them, and re-verified before the real retrain.
> Wanted to be upfront about it as part of how we're validating our data
> pipeline, not just our final numbers.

## Message 6 — Defending the MOS scoring parameters

> Our expert-evaluation instrument (MOS) uses a 1–5 rating scale adapted
> from ITU-T P.800, the standard that defines Mean Opinion Score. Our 3
> rating dimensions — Visual Hierarchy Preservation, Brand & Typographic
> Consistency, Constraint & Whitespace Harmony — map onto standard graphic
> design evaluation principles rather than criteria we invented (visual
> hierarchy and whitespace/overlap: O'Donovan et al. 2014, IEEE TVCG; brand
> consistency: Wheeler, Designing Brand Identity), and each
> score level has a concrete written description (Table 2) so different
> raters apply it consistently. Our collection tool shows the evaluator
> Table 2 and each parameter's definition while they rate, and it presents
> the layouts in randomized order, as our Chapter 3 specifies.

## Message 7 — Where the real numbers live

> Happy to share the actual charts/numbers behind any of this —
> we have a notebook with results pulled directly from our training logs
> and experiment data, not summarized from memory.

*(Attach a screenshot of the relevant chart(s) from
`notebooks/results_analysis.ipynb`, or export a cell's output as an image,
rather than trying to describe the chart in text.)*

## Message 8 — Close, stated honestly

> One thing still pending: Phase 4 (a real design expert scoring our
> outputs) hasn't run yet. The collection tool is ready and now matches our
> Chapter 3 rubric exactly, but we haven't run a rating session with the
> evaluator yet. Wanted to flag that
> clearly rather than imply it's done.

---

## Quick-reference: if she pushes back on something

Not meant to be sent verbatim — these are for you to react with, since
real chat is back-and-forth, not a monologue:

| She might ask... | Point back to... |
|---|---|
| "Is this dataset peer-reviewed?" | Message 3's citation |
| "Who validated your annotations?" | Message 4: three-part chain + the outside expert review (15-image sample) |
| "Where did the MOS rubric come from?" | Message 6 |
| "Is 124 images enough?" | Started at 65 (past the feasibility floor), now 124 (past the original stretch goal) |
| "Show me the actual result" | Message 7 / the notebook |
