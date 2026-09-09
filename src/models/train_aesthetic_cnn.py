"""
ThemeSync — Aesthetic CNN Training
=====================================
Trains AestheticCNN to regress F_layout (Formula 3.11) directly from a
rasterized layout image, distilling the heuristic fitness function into a
learned, image-based "quantitative aesthetic evaluation" component (Ch. 3,
p. 36). Data comes from generate_cnn_training_data.py.

This is a first pass, trained on heuristic-computed labels since no
human-labeled dataset exists yet. Intended to be retrained later on MOS
survey scores (same architecture, different label source) once enough have
been collected — see notes/gnn_fixes_and_methodology_notes.md, gap 5.

Usage:
  python src/models/train_aesthetic_cnn.py
"""

import json
import os
import random
import sys

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from PIL import Image
from torch.utils.data import DataLoader, Dataset

_THIS = os.path.dirname(os.path.abspath(__file__))
if _THIS not in sys.path:
    sys.path.insert(0, _THIS)
from aesthetic_cnn import AestheticCNN

_ROOT = os.path.dirname(os.path.dirname(_THIS))
DATA_DIR = os.path.join(_ROOT, "data", "processed", "cnn_training")
MANIFEST_PATH = os.path.join(DATA_DIR, "manifest.json")
IMG_DIR = os.path.join(DATA_DIR, "images")
WEIGHTS_PATH = os.path.join(_ROOT, "themesync_cnn_v1.pth")


class LayoutAestheticDataset(Dataset):
    def __init__(self, manifest, img_dir, mean, std):
        self.manifest = manifest
        self.img_dir = img_dir
        self.mean = mean
        self.std = std

    def __len__(self):
        return len(self.manifest)

    def __getitem__(self, idx):
        entry = self.manifest[idx]
        img = Image.open(os.path.join(self.img_dir, entry["image"])).convert("RGB")
        arr = np.asarray(img, dtype=np.float32) / 255.0
        tensor = torch.from_numpy(arr).permute(2, 0, 1)
        label = (entry["label"] - self.mean) / self.std
        return tensor, torch.tensor(label, dtype=torch.float32)


def train(epochs=40, batch_size=32, lr=1e-3, val_fraction=0.15, seed=42):
    if not os.path.exists(MANIFEST_PATH):
        raise FileNotFoundError(
            f"No training manifest at {MANIFEST_PATH}. "
            "Run src/data_preprocessing/generate_cnn_training_data.py first."
        )

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    labels = [m["label"] for m in manifest]
    mean, std = float(np.mean(labels)), float(np.std(labels) or 1.0)

    random.seed(seed)
    shuffled = manifest[:]
    random.shuffle(shuffled)
    n_val = max(1, int(val_fraction * len(shuffled)))
    val_set, train_set = shuffled[:n_val], shuffled[n_val:]

    train_ds = LayoutAestheticDataset(train_set, IMG_DIR, mean, std)
    val_ds = LayoutAestheticDataset(val_set, IMG_DIR, mean, std)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training AestheticCNN on {device} | train={len(train_ds)} val={len(val_ds)} "
          f"| label mean={mean:.4f} std={std:.4f}")

    model = AestheticCNN().to(device)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()

    best_val = float("inf")
    for epoch in range(epochs):
        model.train()
        total_loss = 0.0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            pred = model(x)
            loss = criterion(pred, y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * x.size(0)
        train_loss = total_loss / len(train_ds)

        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.to(device)
                val_loss += criterion(model(x), y).item() * x.size(0)
        val_loss /= max(1, len(val_ds))

        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"  Epoch [{epoch+1}/{epochs}] train_mse={train_loss:.4f} val_mse={val_loss:.4f}")

        if val_loss < best_val:
            best_val = val_loss
            torch.save({
                "model_state_dict": model.state_dict(),
                "label_mean": mean,
                "label_std": std,
            }, WEIGHTS_PATH)

    print(f"\nTraining complete. Best val_mse={best_val:.4f}. Weights saved -> {WEIGHTS_PATH}")


if __name__ == "__main__":
    train()
