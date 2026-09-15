# Annotation Guidelines — Master-Layout Images

For the feasibility batch fine-tuning `themesync_yolo_v1.pt` on real
master-layout images (see `notes/gnn_fixes_and_methodology_notes.md`
section 3.6 and `notes/adviser_consultation_checklist.md` item A). Read this
before annotating so everyone in the group draws boxes the same way —
inconsistent labeling between annotators is a common, easy-to-miss source of
bad fine-tuning results.

## What counts as a "master layout" (clarified 2026-09-10)

A master layout is **any generic branded design** a user uploads to
ThemeSync — an event poster, banner, letterhead, social-media announcement
graphic. YOLO (`layout_extractor.py`) parses it purely to extract a visual
**theme** (colors, logo placement/style, decorative motifs), which then gets
synced onto a certificate or ID layout generated separately from the
existing JSON schema payload. **It is not a certificate or ID design
itself** — those are a different, already-working path
(`dynamic_instantiation.py`) that YOLO never touches.

This means `YOUR_TEMPLATE.png`, `YOUR_TEMPLATE2.jpg`, `YOUR_TEMPLATE3.jpg`,
and `YOUR_TEMPLATE4.jpg` (the CSPC Supreme Student Council event posters
already in `data/raw/`) **are exactly the right kind of image** — the
annotation batch should be more images like those, not certificate/ID
designs. (An earlier draft of these notes said the opposite — that was
based on a wrong assumption about what "master layout" means in this
system, corrected directly by the group lead. `sample_template.png` is
still not useful either way — it's a synthetic placeholder mockup with no
real content.)

## Sourcing images

Gather 20–30 more images in the same genre as the 4 existing poster files:
event posters, org announcement graphics, banners, letterheads — anything a
student org, department, or school might realistically upload as a branding
reference. Good sources:
1. **CSPC SSC's own past event posters/graphics** (Facebook page, Canva
   drafts, past announcements) — same org, same designer style as the 4
   already in hand, quick to gather in bulk.
2. **Other CSPC departments'/orgs' posters and banners** — widens visual
   diversity (different colors/logos/layouts) beyond one org's house style.
3. **Stock poster/flyer templates** (Canva, Freepik, Vecteezy free tiers) to
   pad out diversity if 1–2 don't reach the target alone — disclose in
   Chapter 4/Annex which images are real CSPC materials vs. generic stock,
   same as for any other data-composition detail.

Put gathered images into `data/raw/master_layout_batch/images/`.

## Tooling

Two options — pick based on whether multiple people annotate at once:

- **Roboflow** (roboflow.com, free tier) — browser-based, no install,
  supports several people annotating the same project concurrently, exports
  directly to YOLOv8 `.txt` format. Recommended if more than one group
  member is annotating in parallel.
- **LabelImg** (already installed into `themesync_env` this session via
  `pip install labelImg`) — fully offline, no third-party upload. Run
  locally (needs a display, so on your own machine, not a headless server):
  ```
  conda activate themesync_env
  labelImg data/raw/master_layout_batch/images data/raw/master_layout_batch/classes.txt data/raw/master_layout_batch/labels
  ```
  Set the save format to **YOLO** in LabelImg's UI (View → Auto Save Mode,
  and confirm the format toggle button reads "YOLO" not "PascalVOC") before
  you start, so output lands as `.txt` files directly compatible with the
  rest of the pipeline.

Either way, output must end up as one `.txt` per image in
`data/raw/master_layout_batch/labels/`, same basename as the image, in
`class_id cx cy w h` normalized format — matching what
`prepare_yolo_dataset.py` already produces for the CGL export.

## Class definitions (reuse CGL's 4-class taxonomy, in this fixed order)

**Verified against real CGL-Dataset ground truth (2026-09-11), not just
recollection** — pulled actual bounding boxes from the training split to
check what "underlay" and "embellishment" really look like in practice,
because an earlier draft of this file gave wrong guidance (see the note
under `underlay` below). Key finding: **the full background image/
illustration is never boxed as anything, in any real CGL example checked.**
Only small-to-medium overlay elements get boxes — logo, text, underlay
panels, embellishment accents — never the base artwork itself, no matter
how large or visually prominent a background illustration/character is.

| id | class | what to box |
|---|---|---|
| 0 | `logo` | The institutional/org seal, crest, or logo graphic itself — tight box around the visible graphic, not the whitespace padding around it. Box each logo separately if a poster has more than one (e.g. a school seal plus an SSC logo, as in the existing 4 posters). |
| 1 | `text` | One box per **semantically distinct text unit** — not per character, not per line, not the whole page. E.g. on an event poster: the org header line ("Camarines Sur Polytechnic Colleges"), the sub-header ("Supreme Student Council"), the event title (often large stylized text, e.g. "TAN-AW"), the subtitle/tagline, any date/venue callout box, the footer social-handle/email line — each is its own box. |
| 2 | `underlay` | A small-to-medium colored/shaded **panel or bar placed directly behind a specific text or logo element**, to improve contrast/legibility — e.g. the dark rounded-rectangle panel behind a tagline. In real CGL ground truth these cover roughly 1–18% of canvas area and are consistently panel/bar-shaped (wide, short). **Not** the full background photo or illustration, no matter how large, busy, or thematically central it is (a big illustrated robot/character/scene is still just the base artwork — leave it unboxed, same as a plain flat background). |
| 3 | `embellishment` | Small decorative accents — real CGL examples are consistently under 1% of canvas area: thin decorative lines, tiny dots/icons, small corner flourishes, social-media platform icons next to a handle. **Per the group's decision, don't go out of your way to find these** — box one if it's obvious and quick, but don't spend extra time hunting; this class is expected to stay small this round and that's already accounted for in the plan. |

**If you already added a full-canvas or near-full-canvas underlay box on
any image** (this happened on `YUGTO_2026.jpg`'s aurora/forest background
before this was caught), delete it. Keep only genuine panel-behind-text
underlay boxes.

## Consistency rules

- **Tight boxes.** Box edges should touch the actual visible content, not
  include extra margin "for safety."
- **Don't skip an element because it's small.** A missed box is worse than
  an approximate one — the model learns "this isn't an object" from every
  unlabeled pixel region.
- **When two people annotate different images, spot-check each other's
  first 2–3 images against this table before doing the rest** — cheaper to
  catch a systematic disagreement (e.g. one person boxing an org header +
  sub-header as one text box, another boxing them as two) early than to
  redo a whole batch.

## After annotating

Once you have a batch in `data/raw/master_layout_batch/images/` +
`data/raw/master_layout_batch/labels/`, let me know and I'll write the
train/val-split + fine-tuning script (loading `themesync_yolo_v1.pt` as the
base checkpoint rather than starting over from COCO weights, per the
"transfer learning from a reasonable starting point" plan already noted in
the audit file).
