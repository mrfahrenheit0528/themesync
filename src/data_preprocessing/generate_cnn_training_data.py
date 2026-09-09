"""
ThemeSync — Aesthetic CNN Training Data Generator
====================================================
Generates (rasterized layout image, F_layout label) pairs to train
AestheticCNN via distillation from the heuristic fitness function
(HeuristicEvaluator / Formula 3.11) — no human labels required for this
first pass. See notes/gnn_fixes_and_methodology_notes.md, gap 5.

For each domain, samples many CSP margin/vgap configurations (matching the
same parametric space AAPA explores), plus randomly jittered variants to
widen the label distribution beyond "always CSP-valid, near-optimal"
layouts — a regressor needs bad examples too, not just good ones.

Usage:
  python src/data_preprocessing/generate_cnn_training_data.py
  python src/data_preprocessing/generate_cnn_training_data.py --samples_per_domain 400
"""

import argparse
import copy
import json
import os
import random
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_THIS)
_ROOT = os.path.dirname(_SRC)
for _sub in ("models", "solvers"):
    _p = os.path.join(_SRC, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dynamic_instantiation import NodeInstantiator
from cassowary_engine import ConstraintSolverEngine
from optimization_engine import HeuristicEvaluator
from aesthetic_cnn import rasterize_layout

OUT_DIR = os.path.join(_ROOT, "data", "processed", "cnn_training")
IMG_DIR = os.path.join(OUT_DIR, "images")
MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.json")

DOMAINS = {
    "certificate": {
        "payload":  os.path.join(_ROOT, "data", "raw", "academic_payload.json"),
        "canvas_w": 1200,
        "canvas_h": 900,
    },
    "id": {
        "payload":  os.path.join(_ROOT, "data", "raw", "id_payload.json"),
        "canvas_w": 638,
        "canvas_h": 1014,
    },
}


def _random_jitter(nodes, canvas_w, canvas_h, max_shift):
    """Perturbs each node's position independently — deliberately allowed to
    push nodes toward overlap/off-canvas, to generate poor-quality labeled
    examples the regressor needs to see."""
    jittered = []
    for n in nodes:
        x, y, w, h = n["bbox"]
        dx = random.uniform(-max_shift, max_shift)
        dy = random.uniform(-max_shift, max_shift)
        nx = max(-w * 0.3, min(canvas_w - w * 0.7, x + dx))
        ny = max(-h * 0.3, min(canvas_h - h * 0.7, y + dy))
        jn = dict(n)
        jn["bbox"] = [round(nx, 2), round(ny, 2), w, h]
        jittered.append(jn)
    return jittered


def generate(samples_per_domain=250, jitter_fraction=0.4, seed=42):
    random.seed(seed)
    os.makedirs(IMG_DIR, exist_ok=True)
    manifest = []
    idx = 0

    for domain_name, cfg in DOMAINS.items():
        instantiator = NodeInstantiator(canvas_width=cfg["canvas_w"], canvas_height=cfg["canvas_h"])
        base_nodes = instantiator.instantiate_payload(cfg["payload"])
        evaluator = HeuristicEvaluator(canvas_width=cfg["canvas_w"], canvas_height=cfg["canvas_h"])

        for i in range(samples_per_domain):
            margin = random.uniform(30.0, 100.0)
            vgap = random.uniform(6.0, 40.0)
            engine = ConstraintSolverEngine(
                canvas_width=cfg["canvas_w"], canvas_height=cfg["canvas_h"],
                margin=margin, default_vgap=vgap,
            )
            resolved = engine.execute_relational_logic(copy.deepcopy(base_nodes))

            if random.random() < jitter_fraction:
                jitter_strength = random.uniform(10.0, 150.0)
                resolved = _random_jitter(resolved, cfg["canvas_w"], cfg["canvas_h"], jitter_strength)

            scores = evaluator.evaluate_layout(resolved)
            label = scores["Total_Cost"]

            img = rasterize_layout(resolved, cfg["canvas_w"], cfg["canvas_h"])
            img_name = f"{domain_name}_{i:04d}.png"
            img.save(os.path.join(IMG_DIR, img_name))

            manifest.append({"image": img_name, "domain": domain_name, "label": label})
            idx += 1

        print(f"  {domain_name}: {samples_per_domain} samples generated")

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    labels = [m["label"] for m in manifest]
    print(f"\nGenerated {idx} samples -> {MANIFEST_PATH}")
    print(f"Label range: [{min(labels):.4f}, {max(labels):.4f}]  mean={sum(labels)/len(labels):.4f}")
    return MANIFEST_PATH


def main():
    parser = argparse.ArgumentParser(description="Generate AestheticCNN training data")
    parser.add_argument("--samples_per_domain", type=int, default=250)
    parser.add_argument("--jitter_fraction", type=float, default=0.4)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    generate(args.samples_per_domain, args.jitter_fraction, args.seed)


if __name__ == "__main__":
    main()
