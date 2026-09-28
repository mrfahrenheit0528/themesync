# Adviser Consultation Checklist

Running list of things to raise with your adviser/instructor. Kept separate
from `gnn_fixes_and_methodology_notes.md` (which is the technical audit
trail) so you have one short, meeting-ready list instead of having to
re-derive it from a 400+ line file each time. Update this as new items come
up; check items off (or move them to "resolved," with the adviser's answer
noted) once discussed.

---

## A. Decisions already acted on WITHOUT adviser consult yet

These are things the group (you, as lead) decided to proceed with during
development. Code/data work may already be underway or done — that's fine,
but the adviser hasn't signed off on the decision itself, so be ready to
explain and defend it, or roll it back if they push back.

- [ ] **Annotated 65 real master-layout images and fine-tuned YOLOv8 —
  DONE, with a real result, still not run past the adviser.** Clarified
  this session with you directly: a "master layout" in ThemeSync is any
  generic branded design a user uploads (poster, banner, letterhead) — YOLO
  extracts its logo/text/underlay structure purely to derive a visual
  *theme*, which then gets synced onto a certificate/ID layout generated
  separately by the existing JSON schema payload. So the batch targeted more
  images like the CSPC SSC event posters already in `data/raw/`
  (`YOUR_TEMPLATE*.png/jpg`), not certificate/ID designs. This reasoning is
  squarely within the manuscript's own commitment (p. 50) rather than a
  scope addition.
  **Result (2026-09-15):** fine-tuning `themesync_yolo_v1.pt` on the 65-image
  batch (`themesync_yolo_v2.pt`) raised held-out validation mAP50 from
  functionally zero to 0.325. On 3 genuinely unseen poster images, top
  detection confidence rose from 0.20–0.46 to 0.69–0.74. Full numbers in
  `notes/gnn_fixes_and_methodology_notes.md` section 3.7.
  **Updated (2026-09-22): batch scaled to 124 images, `themesync_yolo_v3.pt`
  fine-tuned from v2.** Held-out mAP50 rose again, 0.320 → 0.370 (v2 → v3);
  logo 0.515 → 0.620, text 0.538 → 0.595. A real annotation-export bug was
  also caught and fixed along the way (mixed polygon/box label formats
  silently dropping ~23% of images, plus a class-index reorder that would
  have corrupted the continued fine-tune) — worth mentioning as a
  verification-discipline point, not hiding. Full numbers in section 3.12 of
  the same file. This is a real, positive result worth presenting, not just a
  decision needing retroactive justification — but still worth telling your
  adviser *how* it came about:
  the YOLO model trained cleanly on CGL-Dataset (mAP50 0.539) but produced
  near-zero-confidence detections (0.03–0.11) on the 4 real CSPC posters
  originally — a real, measured domain gap between the public training
  corpus (photographic e-commerce/ad imagery) and ThemeSync's actual
  master-layout uploads (stylized, illustrated event-poster/branding
  graphics), which this fine-tune then closed.
  Ask about:
  - Whether they're fine with a "train on public dataset → measure domain
    gap → fine-tune on small real-annotated set → gap closes" narrative for
    Chapter 4, since that's what actually happened, evidence and all.
  - ~~Whether 65 images is enough to call this result defensible~~ —
    **overtaken by events**: the group scaled to 124 on its own initiative,
    past the 80–120 stretch-goal range originally discussed. Worth a
    one-line mention rather than an open question now.
  - **Underlay detection is still weak** (mAP50 0.050 on held-out data as of
    v3 — 44 validation instances now, up from 17, better but still not
    enough) and `embellishment` stayed flat despite the batch nearly
    doubling (intentionally not prioritized during annotation — already
    failed on CGL's own data at 2.5% of instances, and is the least
    structurally important class for this genre — decorative flourishes/
    stickers, not load-bearing content). Confirm the adviser is fine with
    both being reported as residual limitations rather than further
    remediated before defense.
  - Who did the annotation (whole group vs. you) and what tool
    (CVAT/Roboflow/LabelImg — the latter two already set up this session) —
    logistics your adviser may want a say in if it's being treated as a
    formal data-collection step of the study.
  - **Two rounds of correction happened before landing on the above** — first
    the 4 CSPC posters were assumed to be certificates/IDs (wrong), then
    assumed to be the *wrong* test images entirely because they weren't
    certificates/IDs (also wrong). Worth flagging to your adviser as an
    example of a scope misunderstanding caught and corrected through direct
    back-and-forth with you, in case it comes up as a process question.

## B. Open design questions (not yet decided by anyone)

- [x] ~~Does `layout_extractor.py` (YOLO/OCR) replace the hand-authored JSON
  schema payload, or run alongside it?~~ **Resolved with you directly this
  session:** alongside, by design — YOLO/OCR extracts a visual theme from
  the master-layout upload (a generic branded design), the schema payload
  still handles certificate/ID structural generation and per-record dynamic
  content. Not two competing implementations of the same thing. **Now
  actually implemented too (2026-09-15)** — `pipeline.py` runs a new Stage
  0b that detects nodes on the uploaded master layout and reports them
  (persisted to a JSON file per run), independent of the certificate/ID
  structure generation. Verified end-to-end on a real, unseen poster;
  existing test suites still pass. Just a one-line mention to your adviser
  needed now, not a pending build.

- [ ] **Is the "unified cross-cutting limitation" framing acceptable**, i.e.
  presenting the GNN's and YOLO's domain-mismatch findings as one combined
  Chapter 4 limitation ("both learned components share a training corpus
  that doesn't represent the deployment domain") rather than requiring both
  to be fully remediated before defense.

- [ ] **CNN aesthetic evaluator (`aesthetic_cnn.py`) is built via heuristic
  distillation (no human MOS labels yet), with MOS-based retraining planned
  for later once enough survey ratings exist.** Confirm this phased approach
  (ship distilled version now, retrain on MOS later, same architecture) is
  acceptable, and ask whether MOS-retraining is a hard requirement before
  defense or can be reported as a forward step.

- [ ] **GNN training data has no real per-node color/saliency/typography
  features — confirmed by the 2026-09-15 audit, worse than previously
  tracked.** `graph_builder.py` broadcasts one global color centroid + one
  global saliency scalar into *every* node's feature vector when preparing
  CGL-Dataset training examples; there's no per-node `node_id`, and
  `text_features` (font size / alignment) is dropped entirely during
  preprocessing. Full evidence in `gnn_fixes_and_methodology_notes.md`
  §3.10 (Finding 3). This absorbs and sharpens the older saliency-only item
  below — ask the adviser whether full Table 1/Appendix A per-node fidelity
  here is expected before defense, or reportable as a forward-work
  limitation like the domain-gap finding in section A.

## C. Smaller follow-ups — mention, but low priority

- [x] ~~MOS collector's 4 rating dimensions don't match the manuscript's 3
  named ones, and Table 2's descriptive rubric is never shown to the
  evaluator.~~ **Fixed 2026-09-26** (`gnn_fixes_and_methodology_notes.md`
  §3.13): code changed to match the manuscript, not the other way round —
  the 3 named parameters verbatim, Table 2 shown to the evaluator, layouts
  presented in a seeded random order per p.57's "randomized sample." Zero
  real ratings existed, so nothing to migrate. Just a one-line mention to
  your TA now — no decision needed unless she'd have preferred rewording
  the manuscript instead.
- [ ] Manuscript says SIFT **and** SURF for stylistic markers; code only
  actually invokes SIFT. Ask if this discrepancy needs a manuscript wording
  fix or a code fix, or is fine as-is.
- [ ] GNN's own `s_i` saliency input feature is still one global scalar per
  template (Table 1 implies it should be per-node, same as the legibility
  penalty now is). **See section B for the sharpened version of this item**
  (color centroids have the same problem, plus `node_id`/`text_features`
  are absent entirely) — kept here as a pointer so this line isn't mistaken
  for a separate, smaller issue.
- [ ] Grayscale/degenerate-image K-Means fallback path still uses a fixed
  `n_colors=3` — the Elbow Method k-selection fix (gap 4) wasn't extended to
  this fallback path. Likely low priority (rare fallback case) — confirm.
  **She raised "elbow method" herself in conversation (2026-09-15)** — worth
  confirming this is what she meant (the k-selection already implemented in
  section 3.3 of the methodology notes) and asking directly whether this
  specific fallback-path gap needs fixing before defense, since she brought
  it up unprompted.

## D2. Raised by the Thesis Subject Adviser (TSA), 2026-09-22 — a separate role from your TA

TSA (distinct from TA and from your consultant) asked, in her own
consultation: whether Table 2's Likert scale, the 3 named MOS dimensions,
and the domain-expert evaluator concept are each "backed with study," and
whether the annotated dataset has been checked by anyone besides the
group. Checked the manuscript's actual text rather than assuming — its
*only* citation anywhere for MOS is [18], a Twilio marketing-glossary page
(Chapter 1, Definition of Terms); Chapter 3's own Table 2/Phase 4 text has
no citation at all, and the 124-image annotated batch isn't mentioned in
Chapter 3's prose whatsoever (only CGL-Dataset is described as a Research
Instrument there).

- [x] ~~Citations identified but unverified.~~ **Verified 2026-09-28**
  against the primary sources; see `notes/mos_parameter_grounding.md`.
  - Each of the 3 MOS parameters now has an internal counterpart (Formulas
    12/14, the Visual DNA, the hierarchy sizing) and external sources:
    O'Donovan et al. 2014, Wheeler 2013 and CGL-GAN 2022, with quotes.
  - Table 2 is an adaptation of ITU-T P.800's 5-point ACR scale, which
    should replace the Twilio [18] citation.
  - CGL-Dataset V2's source (Li et al. 2023, CIKM) was found for Ch.3 p.46.
  - Still not added to the manuscript; that needs your explicit go-ahead.
- [ ] **New issue these sources raised (ask the TA): single expert vs.
  3–5.**
  - The manuscript specifies one designated expert (p.54, p.57).
  - Nielsen & Molich (1990) found that single evaluators catch only
    20–51% of problems, and aggregates of 3–5 do well.
  - Both CGL-Dataset papers used 5 professional + 20 novice designers.
  - So citing these sources *for a single expert* contradicts them.
  - Ask whether to revise Phase 4 to 3–5 professional designers, with
    inter-rater agreement reported. That is a Chapter 3 change, so it
    needs her sign-off. The code already handles multiple evaluators.
- [ ] **Expert validation of the annotated dataset arranged** — a sample of
  15 images sent to a graphic design/layout expert for review against the
  annotation class definitions, separate from Phase 4's expert-evaluates-
  *outputs* step. Update this line once the review comes back.
- [ ] Once both land, Chapter 3 should get a new subsection describing the
  124-image master-layout batch as its own Research Instrument (parallel
  to how CGL-Dataset is already described) — currently the manuscript
  doesn't document this dataset's existence at all.

## D. Audited (2026-09-15) — Chapter 3 p.49+

- [x] ~~Chapter 3 past p. 49: Materials/Evaluation Methods, statistical
  tools, MOS protocol wording, Annexes A & B.~~ **Done.** Full findings in
  `gnn_fixes_and_methodology_notes.md` §3.10; actionable items moved to
  sections B (GNN per-node feature gap) and C (MOS rubric mismatch) above.
  Summary: MOS collector's dimensions/rubric don't match the manuscript
  (now tracked in C), Appendix A's per-node feature schema doesn't match
  the GNN training pipeline (now tracked in B, sharper than the old
  saliency-only item), Appendix B's payload schema matches the real code
  exactly (no action needed), and no separate "statistical treatment"
  section exists to further cross-check (Evaluation Metrics, pp.55-58,
  appears to be the complete content).

---

**How to use this:** before any adviser meeting, skim section A first (things
you need to justify or get retroactive sign-off on), then B (things nobody
has decided yet and you should ask directly), then C/D if time allows. Full
technical detail/evidence for every item here lives in
`gnn_fixes_and_methodology_notes.md`.
