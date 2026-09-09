"""
ThemeSync — Template Ingestor
==============================
Runtime wrapper around VisionExtractor that accepts a real master design
image at inference time and extracts the same perceptual features that were
used during GNN training (LAB colour centroids + SIFT saliency weight).

This is the missing bridge between the offline training pipeline
(build_feature_tensors.py) and the live inference pipeline (pipeline.py).

Usage:
    from template_ingestor import TemplateIngestor

    result = TemplateIngestor().ingest("data/raw/my_template.png")
    centroids      = result["color_centroids"]   # [[L,a,b], [L,a,b], [L,a,b]]
    saliency       = result["saliency_weight"]   # float in [0.0, 1.0]
    canvas_w, canvas_h = result["image_wh"]      # native image dimensions
"""

import os
import sys
import cv2
import numpy as np

# Resolve sibling data_preprocessing directory for VisionExtractor import
_THIS = os.path.dirname(os.path.abspath(__file__))
if _THIS not in sys.path:
    sys.path.insert(0, _THIS)

from vision_extraction import VisionExtractor


# Supported raster image extensions
_SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}


class TemplateIngestor:
    """
    Ingests a master design image and extracts its perceptual DNA at runtime.

    Extracts the same two features used during GNN training:
      1. K-Means LAB colour centroids (dominant palette)
      2. SIFT keypoint density (saliency weight)

    Parameters
    ----------
    n_colors : int
        Number of dominant colours to extract via K-Means. Must match the
        value used during GNN training (default: 3).
    """

    def __init__(self, n_colors: int = 3):
        self.n_colors = n_colors
        self._extractor = VisionExtractor(n_colors=n_colors)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(self, image_path: str) -> dict:
        """
        Loads a master design image and extracts its perceptual features.

        Parameters
        ----------
        image_path : str
            Absolute or relative path to the template image (PNG, JPG, etc.).

        Returns
        -------
        dict with keys:
            color_centroids  : list of [L, a, b] triples (OpenCV convention)
            saliency_weight  : float in [0.0, 1.0]
            saliency_map     : dict {"heatmap": [[...]], "image_wh": (w, h)} —
                                per-region visual-noise density (Formula 3.15)
            image_wh         : tuple (width, height) in pixels
            palette_hex      : list of hex colour strings (for display/logging)

        Raises
        ------
        FileNotFoundError
            If the image file does not exist.
        ValueError
            If the file extension is not a supported raster format.
        RuntimeError
            If OpenCV fails to decode the image.
        """
        self._validate_path(image_path)
        image_array = self._load_image(image_path)

        h, w = image_array.shape[:2]

        print(f"  [TemplateIngestor] Image loaded: {os.path.basename(image_path)} ({w}×{h} px)")

        # Extract LAB colour centroids (same call as in build_feature_tensors.py)
        centroids = self._extractor.extract_lab_centroids(image_array)

        # Extract SIFT saliency weight (same call as in build_feature_tensors.py)
        saliency = self._extractor.calculate_saliency_weight(image_array)

        # Extract the spatial saliency heatmap for per-node legibility scoring
        saliency_map = self._extractor.calculate_saliency_map(image_array)

        # Convert centroids to readable hex strings for logging
        palette_hex = [self._lab_to_hex(c) for c in centroids]

        print(f"  [TemplateIngestor] Extracted palette: {' | '.join(palette_hex)}")
        print(f"  [TemplateIngestor] Saliency weight:   {saliency:.4f}")

        return {
            "color_centroids": centroids,
            "saliency_weight": saliency,
            "saliency_map":    saliency_map,
            "image_wh":        (w, h),
            "palette_hex":     palette_hex,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_path(self, image_path: str) -> None:
        if not os.path.exists(image_path):
            raise FileNotFoundError(
                f"[TemplateIngestor] Template image not found: '{image_path}'"
            )
        ext = os.path.splitext(image_path)[1].lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"[TemplateIngestor] Unsupported file type '{ext}'. "
                f"Supported: {sorted(_SUPPORTED_EXTENSIONS)}"
            )

    def _load_image(self, image_path: str) -> np.ndarray:
        """
        Loads the image with OpenCV and converts BGR → RGB for downstream
        compatibility with VisionExtractor (which expects RGB arrays).
        """
        bgr = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if bgr is None:
            raise RuntimeError(
                f"[TemplateIngestor] OpenCV failed to decode image: '{image_path}'. "
                f"File may be corrupt or in an unsupported format."
            )
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    @staticmethod
    def _lab_to_hex(lab: list) -> str:
        """
        Converts a CIE L*a*b* centroid (OpenCV convention) to a CSS hex string.
        Used only for display / logging; not part of the feature vector.
        """
        try:
            lab_pixel = np.array([[[float(lab[0]), float(lab[1]), float(lab[2])]]], dtype=np.float32)
            # Rescale OpenCV L∈[0,255] → standard L∈[0,100]
            lab_pixel[:, :, 0] *= 100.0 / 255.0
            lab_pixel[:, :, 1] -= 128.0
            lab_pixel[:, :, 2] -= 128.0
            rgb = cv2.cvtColor(lab_pixel, cv2.COLOR_Lab2RGB)
            r, g, b = (max(0, min(255, int(c * 255))) for c in rgb[0, 0])
            return f"#{r:02X}{g:02X}{b:02X}"
        except Exception:
            return "#??????"


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test(image_path: str) -> None:
    """Quick diagnostic: ingest one image and print all extracted features."""
    print("\n" + "=" * 60)
    print("  TemplateIngestor — Self-Test")
    print("=" * 60)
    ingestor = TemplateIngestor(n_colors=3)
    result = ingestor.ingest(image_path)

    print(f"\n  colour_centroids (LAB):")
    for i, c in enumerate(result["color_centroids"]):
        print(f"    [{i}] L={c[0]:.2f}  a={c[1]:.2f}  b={c[2]:.2f}  → {result['palette_hex'][i]}")

    print(f"\n  saliency_weight : {result['saliency_weight']:.4f}")
    print(f"  image_wh        : {result['image_wh'][0]} × {result['image_wh'][1]} px")
    print()


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) < 2:
        print("Usage: python template_ingestor.py <path/to/template_image.png>")
        _sys.exit(1)
    _self_test(_sys.argv[1])
