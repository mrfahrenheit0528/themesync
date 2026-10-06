# Master-Layout Annotation Batch

**Scope, clarified with the group lead (2026-09-10):** a "master layout" in
ThemeSync is **any generic branded design** a user uploads — an event
poster, banner, letterhead, social-media graphic — not specifically a
certificate or ID card. YOLO's job (`layout_extractor.py`) is to parse
*this* image for its logo/text/underlay/embellishment structure, purely to
extract a visual **theme** (colors, logo placement, decorative style). That
theme is then synced onto a certificate or ID layout generated separately by
the existing hand-authored JSON schema path (`dynamic_instantiation.py` +
`academic_payload.json`/`id_payload.json`) — YOLO never processes a
certificate/ID image directly.

So: **`YOUR_TEMPLATE*.jpg`/`.png` in `data/raw/` (the CSPC SSC event posters)
are exactly the right genre** — the annotation batch should gather *more*
images like those (posters, banners, org branding/promotional graphics),
not certificate or ID template designs.

Drop master-layout images into `images/`. Annotate each with a YOLO-format
label file of the same basename in `labels/`, using the 4 classes in
`classes.txt` (order matches `themesync_yolo_v1.pt`'s existing class ids —
logo=0, text=1, underlay=2, embellishment=3 — don't reorder that file).

See `notes/annotation_guidelines.md` (repo root `notes/`) for what counts as
each class and how to box it consistently across annotators.

Feasibility batch target: 20–30 images. Once annotated, run the
(to-be-written) fine-tuning script to test whether it closes the domain-gap
finding from this session (CGL-Dataset's photographic/e-commerce ad
imagery vs. this stylized, illustrated event-poster/branding-graphic genre).
