"""
ThemeSync — YOLOv8 Layout-Element Detector Training
======================================================
Fine-tunes a pretrained YOLOv8n checkpoint on CGL-Dataset's own 4-class
annotation taxonomy (logo / text / underlay / embellishment), prepared by
prepare_yolo_dataset.py. Implements Chapter 3, p. 50's "YOLOv8 for object
bounding box detection" as part of Semantic Layout Parsing.

Usage:
  python src/models/train_yolo_extractor.py
  python src/models/train_yolo_extractor.py --epochs 30 --imgsz 640
"""

import argparse
import os

from ultralytics import YOLO

_THIS = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_THIS)
_ROOT = os.path.dirname(_SRC)

DATA_YAML = os.path.join(_ROOT, "data", "processed", "yolo_dataset", "data.yaml")
PRETRAINED_BASE = os.path.join(_ROOT, "yolov8n.pt")
RUN_NAME = "themesync_layout_yolo"


def train(epochs=30, imgsz=640, batch=16):
    if not os.path.exists(DATA_YAML):
        raise FileNotFoundError(
            f"No dataset config at {DATA_YAML}. "
            "Run src/data_preprocessing/prepare_yolo_dataset.py first."
        )

    base = PRETRAINED_BASE if os.path.exists(PRETRAINED_BASE) else "yolov8n.pt"
    model = YOLO(base)

    results = model.train(
        data=DATA_YAML,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        project=os.path.join(_ROOT, "runs", "yolo"),
        name=RUN_NAME,
        exist_ok=True,
        patience=10,
        amp=False,  # skips ultralytics' AMP sanity-check reference-model download
    )

    best_weights = os.path.join(_ROOT, "runs", "yolo", RUN_NAME, "weights", "best.pt")
    target_path = os.path.join(_ROOT, "themesync_yolo_v1.pt")
    if os.path.exists(best_weights):
        import shutil
        shutil.copy(best_weights, target_path)
        print(f"\nBest weights copied -> {target_path}")
    else:
        print(f"\nWARNING: expected weights not found at {best_weights}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Fine-tune YOLOv8 on CGL-Dataset layout categories")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    args = parser.parse_args()
    train(args.epochs, args.imgsz, args.batch)


if __name__ == "__main__":
    main()
