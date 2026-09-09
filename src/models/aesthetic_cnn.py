"""
ThemeSync — Aesthetic CNN
==========================
Formalizes the "Convolutional Neural Networks (CNN) deployed for
quantitative aesthetic evaluation" component described in Chapter 3 (p. 36).

Regresses a scalar aesthetic-quality score directly from a rasterized layout
image. Trained by distillation from the heuristic fitness function
(HeuristicEvaluator / Formula 3.11) for now, since no human-labeled dataset
exists yet — see train_aesthetic_cnn.py. Intended to later be retrained (same
architecture, different label source) on collected MOS scores once enough
have been gathered.

This module is intentionally independent of the live AAPA ranking pipeline
(pipeline.py / candidate_generator.py) — it does not replace the heuristic
as the ranking mechanism. It's exposed as a standalone evaluator.
"""

import numpy as np
import torch
import torch.nn as nn
from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Rasterization — abstract, dependency-free layout -> image
# ---------------------------------------------------------------------------

_CLASS_COLORS = {
    "text_node":       (66, 133, 244),   # blue
    "image_node":      (52, 168, 83),    # green
    "repeating_group": (251, 140, 0),    # orange
}
_DEFAULT_COLOR = (120, 120, 120)


def rasterize_layout(nodes, canvas_w, canvas_h, out_size=(128, 128)):
    """
    Renders each node's bbox as a filled, outlined, colour-coded rectangle on
    a blank canvas — an abstract "spatial arrangement" view rather than a
    fully-styled render (no SVG rasterization library is available in this
    project). Sufficient for a CNN whose target label (F_layout) is itself a
    purely geometric function of node positions/sizes.
    """
    img = Image.new("RGB", (max(1, int(canvas_w)), max(1, int(canvas_h))), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    for node in nodes:
        x, y, w, h = node["bbox"]
        color = _CLASS_COLORS.get(node.get("structural_class"), _DEFAULT_COLOR)
        draw.rectangle([x, y, x + w, y + h], fill=color, outline=(30, 30, 30))
    return img.resize(out_size, Image.BILINEAR)


def layout_to_tensor(nodes, canvas_w, canvas_h, out_size=(128, 128)):
    img = rasterize_layout(nodes, canvas_w, canvas_h, out_size=out_size)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return torch.from_numpy(arr).permute(2, 0, 1)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class AestheticCNN(nn.Module):
    def __init__(self, in_channels=3):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(in_channels, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
        )
        self.regressor = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128, 64), nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, x):
        x = self.features(x)
        return self.regressor(x).squeeze(-1)


# ---------------------------------------------------------------------------
# Inference helper
# ---------------------------------------------------------------------------

def load_evaluator(weights_path, device=None):
    """Loads a trained AestheticCNN plus the label mean/std used to
    denormalize its raw output back into F_layout's own scale."""
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(weights_path, map_location=device, weights_only=True)
    model = AestheticCNN().to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model, checkpoint["label_mean"], checkpoint["label_std"], device


def predict_score(model, mean, std, device, nodes, canvas_w, canvas_h):
    """Predicts F_layout (lower = better) directly from a resolved node list."""
    tensor = layout_to_tensor(nodes, canvas_w, canvas_h).unsqueeze(0).to(device)
    with torch.no_grad():
        pred = model(tensor).item()
    return pred * std + mean
