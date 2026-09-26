"""
ThemeSync — YOLOv8 Fine-Tuning on Real Master-Layout Images
================================================================
Second-stage fine-tune, on top of the CGL-Dataset-trained checkpoint
(`themesync_yolo_v1.pt`, see train_yolo_extractor.py), using a small batch
of real, hand-annotated master-layout images (event posters / branding
assets — see notes/annotation_guidelines.md) instead of synthetic/public
data.

Why a second stage rather than training from scratch: `themesync_yolo_v1.pt`
already generalizes mAP50=0.539 within CGL-Dataset's own domain (real-world
ad/poster imagery), but was measured at near-zero confidence (0.03-0.11) on
ThemeSync's actual master-layout uploads — see
notes/gnn_fixes_and_methodology_notes.md section 3.5's "CRITICAL finding."
Starting from that checkpoint rather than from COCO weights gives the
model a real head start (it already knows what logos/text/underlays look
like in general), so this stage only has to close the remaining domain
gap, not learn object detection from zero on a 65-image dataset.

Backbone freezing: with only 50 training images, fine-tuning the entire
network risks catastrophic forgetting of what v1 already learned and
overfitting to this small batch. `--freeze N` freezes the first N layers
(default 10, YOLOv8n's backbone) so only the head and later layers adapt to
the new domain, a standard low-data transfer-learning mitigation. Pass
`--freeze 0` to fine-tune the whole network if you want to compare.

Usage:
  python src/models/finetune_yolo_master_layout.py
  python src/models/finetune_yolo_master_layout.py --epochs 80 --freeze 0
"""

import argparse
import os

from ultralytics import YOLO

_THIS = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_THIS)
_ROOT = os.path.dirname(_SRC)

DATA_YAML = os.path.join(_ROOT, "data", "raw", "master_layout_batch", "data.yaml")
DEFAULT_BASE_CHECKPOINT = os.path.join(_ROOT, "themesync_yolo_v1.pt")
DEFAULT_OUTPUT_CHECKPOINT = os.path.join(_ROOT, "themesync_yolo_v2.pt")
DEFAULT_RUN_NAME = "themesync_master_layout_finetune"


def finetune(epochs=80, imgsz=640, batch=8, freeze=10, patience=15,
             base_checkpoint=DEFAULT_BASE_CHECKPOINT,
             output_checkpoint=DEFAULT_OUTPUT_CHECKPOINT,
             run_name=DEFAULT_RUN_NAME):
    """
    `base_checkpoint`/`output_checkpoint`/`run_name` default to the original
    v1->v2 stage, but are overridable so a later re-annotation batch (e.g.
    the 124-image superset of the original 65) can continue from the
    *previous* fine-tune rather than always restarting from the CGL-only
    checkpoint, while writing to a new run/output name so the prior stage's
    results.csv and checkpoint aren't overwritten -- both stay comparable.
    """
    if not os.path.exists(DATA_YAML):
        raise FileNotFoundError(
            f"No dataset config at {DATA_YAML}. "
            "Annotate and export the master-layout batch first — see "
            "notes/annotation_guidelines.md."
        )

    if not os.path.exists(base_checkpoint):
        raise FileNotFoundError(
            f"Base checkpoint not found at {base_checkpoint}. "
            "This script fine-tunes ON TOP of an existing checkpoint — run "
            "src/models/train_yolo_extractor.py first if it's missing."
        )

    print(f"Loading base checkpoint: {base_checkpoint}")
    model = YOLO(base_checkpoint)

    freeze_arg = list(range(freeze)) if freeze > 0 else None
    print(f"Freezing first {freeze} layers (backbone)" if freeze > 0
          else "No layers frozen — fine-tuning the full network")

    results = model.train(
        data=DATA_YAML,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        freeze=freeze_arg,
        project=os.path.join(_ROOT, "runs", "yolo"),
        name=run_name,
        exist_ok=True,
        patience=patience,
        amp=False,  # skips ultralytics' AMP sanity-check reference-model download
    )

    best_weights = os.path.join(_ROOT, "runs", "yolo", run_name, "weights", "best.pt")
    if os.path.exists(best_weights):
        import shutil
        shutil.copy(best_weights, output_checkpoint)
        print(f"\nBest weights copied -> {output_checkpoint}")
        print(f"(base checkpoint at {base_checkpoint} left untouched for comparison)")
    else:
        print(f"\nWARNING: expected weights not found at {best_weights}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Fine-tune themesync_yolo_v1.pt on real master-layout images"
    )
    parser.add_argument("--epochs", type=int, default=80,
                         help="Higher default than the CGL stage (30) since this "
                              "run relies on early stopping (--patience) rather "
                              "than a fixed budget, given the small dataset.")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8,
                         help="Smaller default than the CGL stage (16) — only "
                              "50 training images this round.")
    parser.add_argument("--freeze", type=int, default=10,
                         help="Freeze the first N layers (backbone). 0 = fine-tune "
                              "the whole network.")
    parser.add_argument("--patience", type=int, default=15,
                         help="Early-stopping patience (epochs without val "
                              "improvement).")
    parser.add_argument("--base_checkpoint", type=str, default=DEFAULT_BASE_CHECKPOINT,
                         help="Checkpoint to continue fine-tuning from "
                              "(default: v1, the CGL-only checkpoint).")
    parser.add_argument("--output_checkpoint", type=str, default=DEFAULT_OUTPUT_CHECKPOINT,
                         help="Where to copy the best weights to when done "
                              "(default: themesync_yolo_v2.pt).")
    parser.add_argument("--run_name", type=str, default=DEFAULT_RUN_NAME,
                         help="Subdirectory name under runs/yolo/ for this "
                              "run's logs/results.csv (default: "
                              f"'{DEFAULT_RUN_NAME}').")
    args = parser.parse_args()
    finetune(args.epochs, args.imgsz, args.batch, args.freeze, args.patience,
              base_checkpoint=args.base_checkpoint,
              output_checkpoint=args.output_checkpoint,
              run_name=args.run_name)


if __name__ == "__main__":
    main()
