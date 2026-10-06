# Annotation Guidelines — Master-Layout Images (v2, 2026-09-29)

For the group's re-annotation pass on the 124 pubmats in the Roboflow
project `themesync-pubmat-annotation`, which will train
`themesync_yolo_v5.pt`. Read all of it before you start. Two annotators who
box the same poster differently teach the model two contradictory rules,
and that is the most common cause of a weak detector.

## Why a v2

The v4 detector (YOLOv8s, 1024 px) finds logos and text well (logo mAP50
0.818, text 0.682). Its weak spots trace back to the labels
(`methodology notes §3.25`):

1. **`embellishment` meant two different things.** Some annotators boxed a
   2% sparkle as embellishment, others a mascot filling 40% of the poster.
   The model can't learn one rule from both, so it recovers only 18% of
   the validation set's embellishments (v4 recall 0.18, mAP50 0.20). ThemeSync uses these boxes as the **motifs** it
   carries onto certificates and IDs, so this matters most.
2. **Full-poster boxes.** 60 boxes cover more than half their poster
   (e.g., `underlay` 100% on ARKI SEARCH and CELAKBO, `embellishment` 75%
   on BU). They tell the model that "the whole poster" is an object. v4 was
   trained on a copy with these deleted by script; v2 removes them at the
   source.

v2 fixes both. It adds a fifth class for the big art, keeps `embellishment`
for small accents only, and bans full-poster boxes.

## What counts as a master layout (unchanged)

Any branded design a user uploads: an event poster, banner, letterhead or
social-media announcement. YOLO parses it only to extract its **theme**
(palette, logos, motifs, title artwork). Those are projected onto a
certificate or event ID built from the JSON payload. YOLO never looks at a
certificate or ID.

## The five classes

| class | box this | don't box this |
|---|---|---|
| `logo` | Each institutional or org seal, crest or logo mark, **one box per logo**, tight around the visible graphic. A row of 3 logos is 3 boxes. | Social-media icons (Facebook "f", Instagram) are `embellishment`. A sponsor strip's logos are still `logo`, one box each. |
| `text` | One box per **semantically distinct text unit**: the org header line, the sub-header, the event title (however stylised: chrome, 3D, hand-lettered), the tagline, the date/venue line, the footer handle. A title set over two lines ("SIKLAB" / "CSPC INTRAMURALS") is one unit: **one box**. | Don't box each line of a paragraph separately, and don't box the whole page's text as one block. |
| `underlay` | A panel or bar placed **directly behind a specific text or logo** to make it readable: a dark rounded rectangle behind a tagline, a ribbon behind the date. Usually wide and short, 1–18% of the poster. | The poster's background, a photo backdrop, a gradient, a big shape the whole layout sits on: **never** an underlay. |
| `embellishment` | **Small** decorative accents, roughly under 3% of the poster: sparkles, stars, dots, thin lines and dividers, corner flourishes, small icons, social-media icons. | Anything you would call a character, a mascot, an emblem or an object: that's `illustration`. |
| `illustration` *(new)* | Standalone artwork that can be lifted off the poster and still makes sense on its own: characters and mascots, emblems and badges that aren't logos, objects (a trophy, a torch, a gear, a book, a laptop), a stylised plant or animal. Box the whole figure tightly. Typically 3–35% of the poster. | The background artwork the layout sits on (a landscape, a sky, a texture, a full-bleed photo); **photographs of real people** (leave them unboxed; ThemeSync must not copy students' faces onto other documents); text, however decorative. |

**Quick test for the last two:** if it would make sense as a sticker, it's
`illustration`. If it's a sparkle, a line or a small icon, it's
`embellishment`. If it's the page itself, box nothing.

## Rules (all classes)

- **No box over half the poster.** If a box covers more than 50% of the
  image, it's the background: delete it. The pre-flight check (below) lists
  every such box.
- **Tight boxes.** Edges touch the visible content; no safety margin.
- **Don't skip small things.** An unlabeled logo teaches the model "this is
  not a logo". Box every logo, however small.
- **People stay unboxed.** Real photographs of people are never
  `illustration` or `embellishment`. Drawn characters and mascots are
  `illustration`.
- **Overlaps are fine.** A logo on an underlay gets both boxes.
- **Spot-check each other first.** Before splitting the 124 images, two of
  you annotate the same 3 posters and compare against this table. Settle
  every disagreement in the group chat, then split the rest.

## Doing it in Roboflow

1. Open `themesync-pubmat-annotation` (workspace `guiller-angelo-hermoso`).
2. Add the class **`illustration`**, spelled exactly like that, lower case.
   The pipeline reads class names from the trained model, so the order of
   classes doesn't matter, but the spelling does: `logo`, `text`,
   `underlay`, `embellishment`, `illustration`.
3. Go through **all 124 images**, not only the new ones. For each image:
   - delete any box over half the poster;
   - re-class each big-art `embellishment` as `illustration`;
   - box any character, mascot, emblem or object that has no box yet as
     `illustration`;
   - check the title is one box per title unit, and each logo has its own
     box.
4. **Generate a new version:**
   - Keep the same train/valid split (don't re-split). That way v4 and v5
     are compared on the same images.
   - Preprocessing: *Auto-Orient* only. **Do not add Resize.** The current
     export keeps native sizes (646–2048 px), and v4/v5 train at 1024 px. A
     640 stretch squashes the small logos.
   - Augmentation: none. YOLO augments during training.
5. **Export** in *YOLOv8* format. Replace the `train/`, `valid/` and
   `data.yaml` in `data/raw/master_layout_batch/`. First move the current
   ones to `data/raw/master_layout_batch/_raw_v4_backup/`, as was done for
   v1–v3.

## After the export (Guiller or Claude)

```
conda activate themesync_env
# 1. check the labels: counts per class, unknown class ids, boxes over half the poster
python src/models/finetune_yolo_master_layout.py --check_only

# 2. train v5 with the v4 recipe (COCO YOLOv8s, 1024 px, whole network)
python src/models/finetune_yolo_master_layout.py --base_checkpoint yolov8s.pt \
    --imgsz 1024 --epochs 120 --patience 25 --freeze 0 --seed 0 \
    --output_checkpoint themesync_yolo_v5.pt --run_name themesync_master_layout_v5
```

The check must show zero "boxes cover more than half their image" and zero
unknown class ids before training. The same recipe as v4 means a v4 → v5
difference comes from the new labels, not the training.

Once `themesync_yolo_v5.pt` exists, the pipeline and dashboard use it
automatically (`pipeline.DEFAULT_YOLO_WEIGHTS`). Stage 0c then takes motifs
from `illustration` detections first, falling back to `embellishment`
(`stylistic_markers.MOTIF_CLASSES`).

**Evaluating v5 against v4:**

- mAP on each model's own validation labels. Only logo, text and underlay
  are directly comparable, since embellishment changed meaning.
- The downstream checks on the 15 unseen Phase 4 posters:
  - the automatic logo row (15/15 with v4);
  - the title artwork (with v4, found on 13 posters and cut whole on 12);
  - which motifs Stage 0c extracts, compared side by side.

The second set is what an expert rater will actually see.
