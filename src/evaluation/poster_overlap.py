"""
ThemeSync — Poster Overlap Check
=================================
Detects whether a poster image is (a near-duplicate of) one already in an
annotated YOLO training/validation set, even when Roboflow has renamed and
re-encoded it (e.g. YOUR_TEMPLATE3.jpg ↔ TAN-AW_jpg.rf.1169….jpg).

Used by yolo_domain_gap_check.py (to know which "unseen" posters a given
checkpoint actually trained on) and phase4_packet.py (Phase 4 needs posters
no model has seen).
"""

import glob
import os

from PIL import Image

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BATCH_DIR = os.path.join(_ROOT, "data", "raw", "master_layout_batch")

# Training images behind each YOLO checkpoint (v1 was CGL-Dataset only).
TRAINING_IMAGES = {
    "v2": os.path.join(BATCH_DIR, "_raw_v2_backup", "train", "images"),  # 65-image batch
    "v3": os.path.join(BATCH_DIR, "train", "images"),                     # 124-image batch
}


def dhash(path: str, size: int = 8) -> int:
    """64-bit difference hash, robust to resizing and re-encoding."""
    with Image.open(path) as img:
        gray = img.convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(gray.tobytes())
    bits = 0
    for row in range(size):
        for col in range(size):
            left, right = px[row * (size + 1) + col], px[row * (size + 1) + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return bits


def find_match(path: str, candidates: list, max_distance: int = 8) -> str:
    """Basename of the closest candidate within `max_distance` bits, else None."""
    h = dhash(path)
    best, best_d = None, max_distance + 1
    for c in candidates:
        d = bin(h ^ dhash(c)).count("1")
        if d < best_d:
            best, best_d = c, d
    return os.path.basename(best) if best else None


def annotated_images() -> list:
    """Every image in the current annotated batch (train + valid + test)."""
    return glob.glob(os.path.join(BATCH_DIR, "*", "images", "*"))


def training_images(version: str) -> list:
    folder = TRAINING_IMAGES.get(version)
    return glob.glob(os.path.join(folder, "*")) if folder else []
