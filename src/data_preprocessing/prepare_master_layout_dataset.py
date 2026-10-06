"""
ThemeSync — Prepare a Roboflow master-layout export for YOLO training
======================================================================
Turns the group's Roboflow export (data/raw/master_layout_batch/, YOLOv8
format) into a training-ready copy under data/processed/, without touching
the export itself:

  - polygon rows (class x1 y1 x2 y2 ...) become their enclosing boxes.
    Roboflow writes them for shapes drawn with the polygon tool, and
    Ultralytics drops any label file that mixes polygons with boxes (notes
    §3.12), which would silently lose most of the dataset;
  - boxes covering more than half their image are dropped (annotation
    guidelines v2: the poster's own artwork is never an object; the v4
    recipe, notes §3.25). --keep_large keeps them;
  - images are symlinked, and data.yaml gets an absolute path and the
    export's own class names.

Usage:
  python src/data_preprocessing/prepare_master_layout_dataset.py               # → yolo_master_v5
  python src/data_preprocessing/prepare_master_layout_dataset.py --out data/processed/yolo_master_v6
Then:
  python src/models/finetune_yolo_master_layout.py --data data/processed/yolo_master_v5/data.yaml --check_only
"""

import argparse
import os

import yaml

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_SRC = os.path.join(_ROOT, "data", "raw", "master_layout_batch")
DEFAULT_OUT = os.path.join(_ROOT, "data", "processed", "yolo_master_v5")
SPLITS = {"train": "train", "valid": "val", "test": "test"}


def to_box(parts: list) -> tuple:
    """(class id, cx, cy, w, h) for a box or polygon row, clipped to [0, 1]."""
    cid = int(float(parts[0]))
    if len(parts) == 5:
        cx, cy, w, h = (float(v) for v in parts[1:5])
        x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    else:
        xs, ys = [float(v) for v in parts[1::2]], [float(v) for v in parts[2::2]]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    x0, y0, x1, y1 = max(0.0, x0), max(0.0, y0), min(1.0, x1), min(1.0, y1)
    return cid, (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0


def prepare(src: str = DEFAULT_SRC, out: str = DEFAULT_OUT, max_area: float = 0.5,
            keep_large: bool = False) -> dict:
    with open(os.path.join(src, "data.yaml")) as f:
        names = yaml.safe_load(f)["names"]
    names = [names[k] for k in sorted(names)] if isinstance(names, dict) else list(names)
    stats = {"images": 0, "rows": 0, "polygons_converted": 0, "large_dropped": 0, "degenerate_dropped": 0}
    splits = {}
    for folder, key in SPLITS.items():
        images = os.path.join(src, folder, "images")
        labels = os.path.join(src, folder, "labels")
        if not os.path.isdir(images):
            continue
        os.makedirs(os.path.join(out, folder, "images"), exist_ok=True)
        os.makedirs(os.path.join(out, folder, "labels"), exist_ok=True)
        for name in sorted(os.listdir(images)):
            link = os.path.join(out, folder, "images", name)
            if not os.path.lexists(link):
                os.symlink(os.path.join(images, name), link)
            stats["images"] += 1
            label = os.path.splitext(name)[0] + ".txt"
            rows = []
            if os.path.exists(os.path.join(labels, label)):
                with open(os.path.join(labels, label)) as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) < 5:
                            continue
                        stats["rows"] += 1
                        stats["polygons_converted"] += len(parts) > 5
                        cid, cx, cy, w, h = to_box(parts)
                        if w <= 0 or h <= 0:
                            stats["degenerate_dropped"] += 1
                            continue
                        if w * h > max_area and not keep_large:
                            stats["large_dropped"] += 1
                            continue
                        rows.append(f"{cid} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
            with open(os.path.join(out, folder, "labels", label), "w") as f:
                f.write("\n".join(rows) + ("\n" if rows else ""))
        splits[key] = f"{folder}/images"
    with open(os.path.join(out, "data.yaml"), "w") as f:
        yaml.safe_dump({"path": os.path.abspath(out), **splits, "nc": len(names), "names": names},
                       f, sort_keys=False)
    return {"names": names, **stats}


def main():
    parser = argparse.ArgumentParser(description="Prepare a Roboflow master-layout export for YOLO training")
    parser.add_argument("--src", default=DEFAULT_SRC)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--max_area", type=float, default=0.5)
    parser.add_argument("--keep_large", action="store_true", help="keep boxes over --max_area")
    args = parser.parse_args()
    report = prepare(args.src, args.out, args.max_area, args.keep_large)
    print(f"Classes: {report['names']}")
    print(f"{report['images']} images, {report['rows']} label rows: {report['polygons_converted']} polygons → boxes, "
          f"{report['large_dropped']} over-half boxes dropped, {report['degenerate_dropped']} degenerate dropped")
    print(f"→ {os.path.join(args.out, 'data.yaml')}")


if __name__ == "__main__":
    main()
