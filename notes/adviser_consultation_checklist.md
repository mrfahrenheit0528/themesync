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
  `notes/gnn_fixes_and_methodology_notes.md` section 3.7. This is a real,
  positive result worth presenting, not just a decision needing retroactive
  justification — but still worth telling your adviser *how* it came about:
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
  - **Whether 65 images is enough to call this result defensible**, or
    whether they'd want it scaled up toward the 80–120 range originally
    discussed as a stretch goal, given it's already past the 20–30
    feasibility-only floor and produced a real measured result.
  - **Underlay detection is still weak** (mAP50 0.029 on held-out data — only
    17 validation instances) and `embellishment` was intentionally not
    prioritized during annotation (already failed on CGL's own data at 2.5%
    of instances, and is the least structurally important class for this
    genre — decorative flourishes/stickers, not load-bearing content).
    Confirm the adviser is fine with both being reported as residual
    limitations rather than further remediated before defense.
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

## C. Smaller follow-ups — mention, but low priority

- [ ] Manuscript says SIFT **and** SURF for stylistic markers; code only
  actually invokes SIFT. Ask if this discrepancy needs a manuscript wording
  fix or a code fix, or is fine as-is.
- [ ] GNN's own `s_i` saliency input feature is still one global scalar per
  template (Table 1 implies it should be per-node, same as the legibility
  penalty now is). Ask if full Table 1 fidelity here is expected or optional.
- [ ] Grayscale/degenerate-image K-Means fallback path still uses a fixed
  `n_colors=3` — the Elbow Method k-selection fix (gap 4) wasn't extended to
  this fallback path. Likely low priority (rare fallback case) — confirm.
  **She raised "elbow method" herself in conversation (2026-09-15)** — worth
  confirming this is what she meant (the k-selection already implemented in
  section 3.3 of the methodology notes) and asking directly whether this
  specific fallback-path gap needs fixing before defense, since she brought
  it up unprompted.

## D. Not yet audited — do before claiming full Ch.3 alignment

- [ ] Chapter 3 past p. 49: Materials/Evaluation Methods, statistical tools,
  MOS protocol wording, Annexes A & B. The MOS collector
  (`src/evaluation/mos_collector.py`) *looks* consistent (4 dimensions,
  1–5 scale) but hasn't been cross-checked word-for-word against the
  manuscript's actual Materials section yet.

---

**How to use this:** before any adviser meeting, skim section A first (things
you need to justify or get retroactive sign-off on), then B (things nobody
has decided yet and you should ask directly), then C/D if time allows. Full
technical detail/evidence for every item here lives in
`gnn_fixes_and_methodology_notes.md`.
