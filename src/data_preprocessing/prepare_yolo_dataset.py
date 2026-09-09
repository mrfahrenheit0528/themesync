"""
ThemeSync — YOLO Dataset Preparation
=======================================
Exports a subset of CGL-Dataset V2 (already used for GNN training — see
build_feature_tensors.py) into the directory layout Ultralytics YOLO expects,
so YOLOv8 can be fine-tuned on the dataset's own 4-class annotation taxonomy
(logo / text / underlay / embellishment) instead of relying on its generic
pretrained COCO classes.

Implements Chapter 3, p. 50 ("Phase 1: Data Extraction and Graph
Construction") — "Semantic Layout Parsing utilizing YOLOv8 for object
bounding box detection."

Output layout:
  data/processed/yolo_dataset/
    images/train/*.jpg   images/val/*.jpg
    labels/train/*.txt   labels/val/*.txt   (YOLO format: class cx cy w h, normalized)
    data.yaml

Usage:
  python src/data_preprocessing/prepare_yolo_dataset.py
  python src/data_preprocessing/prepare_yolo_dataset.py --train_count 3000 --val_count 300
"""

import argparse
import os

import datasets as ds
import yaml

_THIS = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_THIS)
_ROOT = os.path.dirname(_SRC)

OUT_DIR = os.path.join(_ROOT, "data", "processed", "yolo_dataset")
IMAGES_DIR = os.path.join(OUT_DIR, "images")
LABELS_DIR = os.path.join(OUT_DIR, "labels")
DATA_YAML_PATH = os.path.join(OUT_DIR, "data.yaml")

# CGL-Dataset's own category_id (1-indexed) -> class name.
# category_id - 1 gives the 0-indexed YOLO class id.
CGL_CATEGORIES = {1: "logo", 2: "text", 3: "underlay", 4: "embellishment"}


def _export_split(dataset_split, split_name, count, start_idx=0):
    img_dir = os.path.join(IMAGES_DIR, split_name)
    lbl_dir = os.path.join(LABELS_DIR, split_name)
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(lbl_dir, exist_ok=True)

    n_written = 0
    n_skipped = 0
    for i, example in enumerate(dataset_split):
        if i < start_idx:
            continue
        if n_written >= count:
            break

        ann = example.get("annotations") or {}
        bboxes = ann.get("bbox", [])
        cat_ids = ann.get("category_id", [])
        if not bboxes:
            n_skipped += 1
            continue

        img = example["image"]
        w, h = example["width"], example["height"]
        if w <= 0 or h <= 0:
            n_skipped += 1
            continue

        lines = []
        for bbox, cid in zip(bboxes, cat_ids):
            if cid not in CGL_CATEGORIES:
                continue
            x, y, bw, bh = bbox
            # Clamp degenerate/out-of-frame boxes rather than emitting bad labels
            x = max(0.0, min(float(x), w))
            y = max(0.0, min(float(y), h))
            bw = max(1.0, min(float(bw), w - x))
            bh = max(1.0, min(float(bh), h - y))

            cx = (x + bw / 2.0) / w
            cy = (y + bh / 2.0) / h
            nw = bw / w
            nh = bh / h
            class_id = cid - 1
            lines.append(f"{class_id} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")

        if not lines:
            n_skipped += 1
            continue

        stem = f"{split_name}_{i:06d}"
        img.convert("RGB").save(os.path.join(img_dir, f"{stem}.jpg"), quality=90)
        with open(os.path.join(lbl_dir, f"{stem}.txt"), "w") as f:
            f.write("\n".join(lines))

        n_written += 1
        if n_written % 500 == 0:
            print(f"  [{split_name}] {n_written}/{count} written...")

    print(f"  [{split_name}] done: {n_written} written, {n_skipped} skipped (no usable annotations)")
    return n_written


def prepare(train_count=3000, val_count=300):
    print("Loading CGL-Dataset V2 (uses the same HF cache as GNN training data)...")
    dataset = ds.load_dataset("creative-graphic-design/CGL-Dataset-v2")

    # NOTE: CGL-Dataset-v2's own "test" split holds dummy placeholder
    # annotations (bbox=[1,2,3,4], area=12 for every example) — it withholds
    # real ground truth publicly, presumably for a held-out leaderboard.
    # Confirmed by direct inspection, not assumed. Both train and val must
    # come from CGL's "train" split instead, at disjoint index ranges.
    print(f"\nExporting train split ({train_count} target, from CGL train[0:{train_count}])...")
    _export_split(dataset["train"], "train", train_count, start_idx=0)

    print(f"\nExporting val split ({val_count} target, from CGL train[{train_count}:{train_count + val_count}])...")
    _export_split(dataset["train"], "val", val_count, start_idx=train_count)

    data_yaml = {
        "path": OUT_DIR,
        "train": "images/train",
        "val": "images/val",
        "names": {cid - 1: name for cid, name in CGL_CATEGORIES.items()},
    }
    with open(DATA_YAML_PATH, "w") as f:
        yaml.safe_dump(data_yaml, f, sort_keys=False)

    print(f"\ndata.yaml written -> {DATA_YAML_PATH}")
    return DATA_YAML_PATH


def main():
    parser = argparse.ArgumentParser(description="Export CGL-Dataset to YOLO format")
    parser.add_argument("--train_count", type=int, default=3000)
    parser.add_argument("--val_count", type=int, default=300)
    args = parser.parse_args()
    prepare(args.train_count, args.val_count)


if __name__ == "__main__":
    main()
