"""
ThemeSync — YOLO Domain-Gap Check (Stage 0b)
==============================================
Measures how well each YOLO checkpoint generalises to real poster images it
never saw during training or validation: the CGL-to-real-poster domain gap
first found in notes/gnn_fixes_and_methodology_notes.md §3.5.

For each checkpoint (v1 CGL-only, v2 65-image fine-tune, v3 124-image
fine-tune) and each unseen poster, records:
  - top_conf : highest detection confidence (predict floor conf=0.01)
  - n_ge_025 : number of detections at conf >= 0.25 (a usable threshold)

The three posters (La Serata, TAN-AW, LODT) are the CSPC samples that were
never in the annotation batch. YOUR_TEMPLATE2.jpg (YUGTO 2026) is excluded
on purpose: it *was* one of the annotated training images (§3.7).

Writes results/yolo_domain_gap_check.json (read by
notebooks/results_analysis.ipynb).

Usage:
  python src/evaluation/yolo_domain_gap_check.py
"""

import json
import os

from ultralytics import YOLO

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

UNSEEN_POSTERS = {
    "La Serata": "data/raw/YOUR_TEMPLATE.png",
    "TAN-AW":    "data/raw/YOUR_TEMPLATE3.jpg",
    "LODT":      "data/raw/YOUR_TEMPLATE4.jpg",
}
CHECKPOINTS = {
    "v1": "themesync_yolo_v1.pt",
    "v2": "themesync_yolo_v2.pt",
    "v3": "themesync_yolo_v3.pt",
}
PREDICT_CONF_FLOOR = 0.01
USABLE_CONF = 0.25


def run_check() -> dict:
    results = {}
    for version, weights in CHECKPOINTS.items():
        model = YOLO(os.path.join(_ROOT, weights))
        results[version] = {}
        for name, rel_path in UNSEEN_POSTERS.items():
            pred = model.predict(os.path.join(_ROOT, rel_path), conf=PREDICT_CONF_FLOOR, verbose=False)[0]
            confs = sorted((float(c) for c in pred.boxes.conf), reverse=True)
            results[version][name] = {
                "top_conf": round(confs[0], 3) if confs else 0.0,
                "n_ge_025": sum(c >= USABLE_CONF for c in confs),
            }
            print(f"  {version}  {name:<10} top_conf={results[version][name]['top_conf']:.3f}  "
                  f"n>={USABLE_CONF}: {results[version][name]['n_ge_025']}")

    output = {
        "posters": UNSEEN_POSTERS,
        "checkpoints": CHECKPOINTS,
        "metric": (f"top detection confidence, and count of detections >= {USABLE_CONF} "
                   f"(predict conf floor {PREDICT_CONF_FLOOR})"),
        "results": results,
    }
    out_path = os.path.join(_ROOT, "results", "yolo_domain_gap_check.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Saved → {out_path}")
    return output


if __name__ == "__main__":
    run_check()
