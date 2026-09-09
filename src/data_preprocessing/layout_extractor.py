"""
ThemeSync — Layout Extractor (Semantic Layout Parsing)
=========================================================
Implements Chapter 3, p. 50's "Phase 1: Data Extraction and Graph
Construction" — Semantic Layout Parsing utilizing YOLOv8 for object bounding
box detection and Tesseract OCR for text extraction, converting a flattened
raster master template into structured, editable nodes.

This is a standalone extraction path, independent of the existing
NodeInstantiator (dynamic_instantiation.py), which builds nodes from a
hand-authored JSON schema payload instead. The two are not (yet) wired
together in pipeline.py — see notes/gnn_fixes_and_methodology_notes.md,
item 6, for the open question of whether this should replace or run
alongside the schema-payload flow.

Usage:
    from layout_extractor import LayoutExtractor
    extractor = LayoutExtractor(weights_path="themesync_yolo_v1.pt")
    nodes = extractor.extract("data/raw/sample_template.png")
"""

import os

import cv2
import pytesseract
from ultralytics import YOLO

# YOLO class id (0-indexed, matching prepare_yolo_dataset.py's CGL_CATEGORIES - 1)
# -> ThemeSync structural_class. CGL-Dataset's 4-category taxonomy is finer
# than ThemeSync's 3 structural classes, so logo/underlay/embellishment all
# collapse to "image_node" (the closest existing category for a non-text
# graphic element) — "repeating_group" has no YOLO-detectable equivalent
# (it's a template-specific structural pattern, e.g. 3 signature blocks in
# the certificate domain, not a generic visual category), so it's never
# auto-assigned here; a detected run of similar adjacent text boxes could be
# heuristically grouped into one later, but that's out of scope for this pass.
_YOLO_CLASS_NAMES = {0: "logo", 1: "text", 2: "underlay", 3: "embellishment"}
_CLASS_TO_STRUCTURAL = {
    "logo":          "image_node",
    "text":          "text_node",
    "underlay":      "image_node",
    "embellishment": "image_node",
}

DEFAULT_CONFIDENCE = 0.25


class LayoutExtractor:
    def __init__(self, weights_path, confidence=DEFAULT_CONFIDENCE):
        if not os.path.exists(weights_path):
            raise FileNotFoundError(
                f"YOLO weights not found at '{weights_path}'. "
                "Run src/data_preprocessing/prepare_yolo_dataset.py then "
                "src/models/train_yolo_extractor.py first."
            )
        self.model = YOLO(weights_path)
        self.confidence = confidence

    def extract(self, image_path):
        """
        Runs YOLO detection + (for text-class detections) Tesseract OCR on
        a master template image, returning a node list compatible with the
        rest of the pipeline's schema: node_id, semantic_category,
        structural_class, spatial_hierarchy, bbox, constraint_type.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Template image not found: '{image_path}'")

        bgr = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if bgr is None:
            raise RuntimeError(f"OpenCV failed to decode image: '{image_path}'")
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

        results = self.model.predict(image_path, conf=self.confidence, verbose=False)
        detections = []
        for result in results:
            for box in result.boxes:
                cls_id = int(box.cls.item())
                class_name = _YOLO_CLASS_NAMES.get(cls_id, "embellishment")
                x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
                detections.append({
                    "class_name":  class_name,
                    "confidence":  float(box.conf.item()),
                    "bbox_xyxy":   (x1, y1, x2, y2),
                })

        # Reading order: logo first, then remaining detections top-to-bottom
        def _sort_key(d):
            is_logo = 0 if d["class_name"] == "logo" else 1
            _, y1, _, _ = d["bbox_xyxy"]
            return (is_logo, y1)

        detections.sort(key=_sort_key)

        nodes = []
        for idx, det in enumerate(detections):
            x1, y1, x2, y2 = det["bbox_xyxy"]
            w, h = x2 - x1, y2 - y1
            structural_class = _CLASS_TO_STRUCTURAL[det["class_name"]]

            node = {
                "node_id":           f"auto_{det['class_name']}_{idx}",
                "semantic_category": det["class_name"],
                "structural_class":  structural_class,
                "spatial_hierarchy": idx,
                "bbox":              [round(x1, 2), round(y1, 2), round(w, 2), round(h, 2)],
                "constraint_type":   "Soft",
                "detection_confidence": round(det["confidence"], 4),
            }

            if structural_class == "text_node":
                node["ocr_text"] = self._ocr_region(rgb, x1, y1, x2, y2)

            nodes.append(node)

        return nodes

    @staticmethod
    def _ocr_region(rgb_image, x1, y1, x2, y2):
        h_img, w_img = rgb_image.shape[:2]
        xi1, yi1 = max(0, int(x1)), max(0, int(y1))
        xi2, yi2 = min(w_img, int(x2)), min(h_img, int(y2))
        if xi2 <= xi1 or yi2 <= yi1:
            return ""

        crop = rgb_image[yi1:yi2, xi1:xi2]
        try:
            text = pytesseract.image_to_string(crop).strip()
        except Exception:
            text = ""
        return text
