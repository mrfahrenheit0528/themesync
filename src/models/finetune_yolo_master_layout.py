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

v5 (the group's 200-image re-annotation, 2026-10-06; it kept the 4 classes):
the v4 recipe — COCO YOLOv8s at 1024 px, whole network, AMP on — on the new
labels. The export mixes polygon and box rows, so convert it first:
  python src/data_preprocessing/prepare_master_layout_dataset.py
  python src/models/finetune_yolo_master_layout.py --data data/processed/yolo_master_v5/data.yaml \
      --base_checkpoint yolov8s.pt --imgsz 1024 --epochs 120 --patience 25 --freeze 0 --seed 0 --amp \
      --output_checkpoint themesync_yolo_v5_candidate.pt --run_name themesync_master_layout_v5
(The pipeline switches to themesync_yolo_v5.pt as soon as that file exists,
so train to a candidate name and promote it only after comparing with v4.)

Every run first checks the export's labels (check_labels): per-class counts,
class ids outside data.yaml's names (refused), and boxes covering more than
half their image (the full-poster boxes guidelines v2 removes; warned).
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


def _split_dir(base: str, rel: str) -> str:
    """A data.yaml split path, resolved like Ultralytics does (Roboflow
    exports write '../train/images' for a folder next to data.yaml)."""
    path = rel if os.path.isabs(rel) else os.path.normpath(os.path.join(base, rel))
    if not os.path.exists(path) and rel.startswith("../"):
        path = os.path.normpath(os.path.join(base, rel[3:]))
    return path


def row_box(parts: list) -> tuple:
    """(class id, w, h) of one label row: a box row (class cx cy w h), or a
    polygon row (class x1 y1 x2 y2 ...) measured by its enclosing box."""
    cid = int(float(parts[0]))
    if len(parts) == 5:
        return cid, float(parts[3]), float(parts[4])
    xs, ys = [float(v) for v in parts[1::2]], [float(v) for v in parts[2::2]]
    return cid, max(xs) - min(xs), max(ys) - min(ys)


def check_labels(data_yaml: str = DATA_YAML, max_area: float = 0.5) -> dict:
    """
    Pre-flight check of a YOLO export against the annotation guidelines:
    box counts per class and split, class ids outside data.yaml's `names`,
    boxes covering more than `max_area` of their image (guidelines v2:
    never box the poster's whole artwork), and files that mix polygon rows
    with box rows, which Ultralytics drops whole (notes §3.12; convert them
    with prepare_master_layout_dataset.py). Returns the findings.
    """
    import yaml

    with open(data_yaml) as f:
        cfg = yaml.safe_load(f)
    names = cfg["names"]
    names = [names[k] for k in sorted(names)] if isinstance(names, dict) else list(names)
    base = os.path.dirname(os.path.abspath(data_yaml))
    if cfg.get("path"):
        base = cfg["path"] if os.path.isabs(cfg["path"]) else os.path.join(base, cfg["path"])
    report = {"names": names, "counts": {}, "images": {}, "large_boxes": [], "unknown_class_ids": [],
              "polygon_files": []}
    for split in ("train", "val", "test"):
        if not cfg.get(split):
            continue
        labels = _split_dir(base, cfg[split]).replace(os.sep + "images", os.sep + "labels")
        if not os.path.isdir(labels):
            continue
        counts = {n: 0 for n in names}
        files = sorted(f for f in os.listdir(labels) if f.endswith(".txt"))
        for fn in files:
            with open(os.path.join(labels, fn)) as f:
                rows = [line.split() for line in f if len(line.split()) >= 5]
            if any(len(parts) > 5 for parts in rows):
                report["polygon_files"].append((split, fn))
            for parts in rows:
                cid, w, h = row_box(parts)
                if not 0 <= cid < len(names):
                    report["unknown_class_ids"].append((split, fn, cid))
                    continue
                counts[names[cid]] += 1
                if w * h > max_area:
                    report["large_boxes"].append((split, fn, names[cid], round(w * h, 2)))
        report["counts"][split] = counts
        report["images"][split] = len(files)
    return report


def print_label_report(report: dict) -> None:
    print(f"Classes: {report['names']}")
    for split, counts in report["counts"].items():
        print(f"  {split:<5} {report['images'][split]:>4} images  "
              + "  ".join(f"{k} {v}" for k, v in counts.items()))
    if report["unknown_class_ids"]:
        print(f"  ✗ {len(report['unknown_class_ids'])} boxes use a class id outside `names`:")
        for split, fn, cid in report["unknown_class_ids"][:10]:
            print(f"      {split}/{fn}: class {cid}")
    if report["polygon_files"]:
        print(f"  ✗ {len(report['polygon_files'])} label files contain polygon rows; Ultralytics drops a "
              "file that mixes them with boxes. Convert first: "
              "python src/data_preprocessing/prepare_master_layout_dataset.py")
    if report["large_boxes"]:
        print(f"  ! {len(report['large_boxes'])} boxes cover more than half their image "
              "(guidelines v2: delete full-poster boxes):")
        for split, fn, name, frac in report["large_boxes"][:10]:
            print(f"      {split}/{fn}: {name} covering {frac:.0%}")


def finetune(epochs=80, imgsz=640, batch=8, freeze=10, patience=15,
             base_checkpoint=DEFAULT_BASE_CHECKPOINT,
             output_checkpoint=DEFAULT_OUTPUT_CHECKPOINT,
             run_name=DEFAULT_RUN_NAME, data_yaml=DATA_YAML, seed=0, amp=False):
    """
    `base_checkpoint`/`output_checkpoint`/`run_name` default to the original
    v1->v2 stage, but are overridable so a later re-annotation batch (e.g.
    the 124-image superset of the original 65) can continue from the
    *previous* fine-tune rather than always restarting from the CGL-only
    checkpoint, while writing to a new run/output name so the prior stage's
    results.csv and checkpoint aren't overwritten -- both stay comparable.
    """
    if not os.path.exists(data_yaml):
        raise FileNotFoundError(
            f"No dataset config at {data_yaml}. "
            "Annotate and export the master-layout batch first — see "
            "notes/annotation_guidelines.md."
        )

    if not os.path.exists(base_checkpoint):
        raise FileNotFoundError(
            f"Base checkpoint not found at {base_checkpoint}. "
            "This script fine-tunes ON TOP of an existing checkpoint — run "
            "src/models/train_yolo_extractor.py first if it's missing."
        )

    report = check_labels(data_yaml)
    print_label_report(report)
    if report["unknown_class_ids"]:
        raise ValueError("Labels use class ids that data.yaml doesn't name — fix the export first.")
    if report["polygon_files"]:
        raise ValueError("Polygon label rows would make Ultralytics drop those files — convert the "
                         "export with prepare_master_layout_dataset.py and train on its data.yaml.")

    print(f"Loading base checkpoint: {base_checkpoint}")
    model = YOLO(base_checkpoint)

    freeze_arg = list(range(freeze)) if freeze > 0 else None
    print(f"Freezing first {freeze} layers (backbone)" if freeze > 0
          else "No layers frozen — fine-tuning the full network")

    results = model.train(
        data=data_yaml,
        seed=seed,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        freeze=freeze_arg,
        project=os.path.join(_ROOT, "runs", "yolo"),
        name=run_name,
        exist_ok=True,
        patience=patience,
        amp=amp,  # off by default: skips Ultralytics' AMP check download (v4 and v5 ran with it on)
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
    parser.add_argument("--data", type=str, default=DATA_YAML,
                         help="The export's data.yaml (default: the Roboflow batch "
                              "in data/raw/master_layout_batch/).")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--amp", action="store_true",
                         help="Mixed-precision training, as v4 was trained (default off).")
    parser.add_argument("--check_only", action="store_true",
                         help="Only check the labels (counts, unknown class ids, "
                              "full-poster boxes) and exit.")
    args = parser.parse_args()
    if args.check_only:
        print_label_report(check_labels(args.data))
        return
    finetune(args.epochs, args.imgsz, args.batch, args.freeze, args.patience,
              base_checkpoint=args.base_checkpoint,
              output_checkpoint=args.output_checkpoint,
              run_name=args.run_name, data_yaml=args.data, seed=args.seed, amp=args.amp)


if __name__ == "__main__":
    main()
