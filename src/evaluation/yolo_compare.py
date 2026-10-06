"""
ThemeSync — Compare YOLO checkpoints on the same validation labels
===================================================================
Scores several Stage 0b checkpoints on one validation set, each at the
image size it was trained at, leaving out every validation image that any
of the compared checkpoints trained on (poster_overlap.TRAINING_IMAGES), so
no model is scored on images it has seen. Labels are rewritten into each
model's own class order by name (exports differ: v4 is logo, text,
underlay, embellishment; the 2026-10-06 export is alphabetical).

Usage:
  python src/evaluation/yolo_compare.py \\
      --data data/processed/yolo_master_v5/data.yaml \\
      --models v4=themesync_yolo_v4.pt,v5=themesync_yolo_v5_candidate.pt \\
      --out results/yolo_v5_comparison.json
"""

import argparse
import glob
import json
import os
import sys
import tempfile

import yaml

_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_EVAL_DIR))
sys.path.insert(0, _EVAL_DIR)
import poster_overlap as po  # noqa: E402


def fair_val_list(data_yaml: str, versions: list) -> tuple:
    """Validation images none of `versions` trained on, and the excluded ones."""
    with open(data_yaml) as f:
        cfg = yaml.safe_load(f)
    base = cfg.get("path") or os.path.dirname(os.path.abspath(data_yaml))
    images = sorted(glob.glob(os.path.join(base, cfg["val"], "*")))
    seen_by = {v: po.training_images(v) for v in versions}
    keep, excluded = [], []
    for img in images:
        hits = [v for v, train in seen_by.items() if train and po.find_match(img, train)]
        (excluded if hits else keep).append((img, hits))
    return [k for k, _ in keep], [(os.path.basename(i), h) for i, h in excluded], cfg


def main():
    from ultralytics import YOLO

    parser = argparse.ArgumentParser(description="Compare YOLO checkpoints on the same validation labels")
    parser.add_argument("--data", required=True)
    parser.add_argument("--models", required=True, help="name=path pairs, comma-separated; names are "
                                                        "poster_overlap versions (v3, v4, v5...)")
    parser.add_argument("--out", default=os.path.join(_ROOT, "results", "yolo_comparison.json"))
    args = parser.parse_args()
    models = dict(pair.split("=", 1) for pair in args.models.split(","))

    keep, excluded, cfg = fair_val_list(args.data, list(models))
    print(f"Validation images: {len(keep)} kept, {len(excluded)} left out (seen in training): "
          + ", ".join(f"{n} ({'/'.join(h)})" for n, h in excluded))
    tmp = tempfile.mkdtemp(prefix="yolo_compare_")
    data_names = cfg["names"] if isinstance(cfg["names"], list) else [cfg["names"][k] for k in sorted(cfg["names"])]

    def dataset_for(name: str, model_names: dict) -> str:
        """The kept images with labels in this model's class order."""
        index = {n: i for i, n in model_names.items()}
        root = os.path.join(tmp, name)
        os.makedirs(os.path.join(root, "images"), exist_ok=True)
        os.makedirs(os.path.join(root, "labels"), exist_ok=True)
        for img in keep:
            os.symlink(img, os.path.join(root, "images", os.path.basename(img)))
            src = os.path.splitext(img.replace(os.sep + "images" + os.sep, os.sep + "labels" + os.sep))[0] + ".txt"
            rows = []
            if os.path.exists(src):
                with open(src) as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) == 5 and data_names[int(parts[0])] in index:
                            rows.append(" ".join([str(index[data_names[int(parts[0])]])] + parts[1:]))
            with open(os.path.join(root, "labels", os.path.basename(src)), "w") as f:
                f.write("\n".join(rows) + ("\n" if rows else ""))
        path = os.path.join(root, "data.yaml")
        with open(path, "w") as f:
            yaml.safe_dump({"path": root, "train": "images", "val": "images",
                            "names": {int(i): n for i, n in model_names.items()}}, f)
        return path

    results = {"data": os.path.relpath(args.data, _ROOT), "val_images": len(keep),
               "left_out": excluded, "models": {}}
    for name, path in models.items():
        model = YOLO(path)
        imgsz = int((getattr(model, "ckpt", None) or {}).get("train_args", {}).get("imgsz", 640))
        r = model.val(data=dataset_for(name, model.names), imgsz=imgsz, batch=8, verbose=False, plots=False,
                      project=tmp, name=name, exist_ok=True)
        per_class = {}
        for i, cls in model.names.items():
            p, rec, ap50, ap = r.box.class_result(i)
            per_class[cls] = {"precision": round(float(p), 3), "recall": round(float(rec), 3),
                              "mAP50": round(float(ap50), 3), "mAP50-95": round(float(ap), 3)}
        results["models"][name] = {"checkpoint": path, "imgsz": imgsz, "mAP50": round(float(r.box.map50), 3),
                                   "mAP50-95": round(float(r.box.map), 3), "precision": round(float(r.box.mp), 3),
                                   "recall": round(float(r.box.mr), 3), "per_class": per_class}
    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{'model':<6} {'mAP50':>6} {'mAP50-95':>9} " + " ".join(f"{c[:12]:>13}" for c in data_names))
    for name, m in results["models"].items():
        print(f"{name:<6} {m['mAP50']:>6.3f} {m['mAP50-95']:>9.3f} "
              + " ".join(f"{m['per_class'][c]['mAP50']:>6.3f}/R{m['per_class'][c]['recall']:.2f}"
                         for c in data_names))
    print(f"Saved → {args.out}")


if __name__ == "__main__":
    main()
