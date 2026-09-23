"""Pre-label real images with the current (classical) detectors so a human
(or reviewer) only corrects boxes instead of drawing them from scratch.

Output: data/dataset_1/boxes_auto.json — {file: [{"cls": name, "box": [x0,y0,x1,y1] (0-1)}]}
These are PROPOSALS, not ground truth. The reviewed file is boxes.json.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
logging.disable(logging.WARNING)

from app.services.docverify.pipeline import verify_images  # noqa: E402

DATA = ROOT / "data/dataset_1"
CLASSES = ["document", "photograph", "mrz", "qr_code", "barcode", "stamp", "yellow_gold_feature"]


def document_outline(bgr: np.ndarray) -> list[float]:
    """Largest roughly-rectangular contour covering >=20% of the image; else the full frame."""
    h, w = bgr.shape[:2]
    gray = cv2.GaussianBlur(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    edges = cv2.dilate(cv2.Canny(gray, 40, 120), np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        if cw * ch >= 0.2 * w * h and (best is None or cw * ch > best[2] * best[3]):
            best = (x, y, cw, ch)
    if best is None:
        return [0.0, 0.0, 1.0, 1.0]
    x, y, cw, ch = best
    return [x / w, y / h, (x + cw) / w, (y + ch) / h]


def main() -> None:
    labels = json.loads((DATA / "labels.json").read_text())
    out: dict[str, list[dict]] = {}
    for r in labels["records"]:
        if r["exclude"]:
            continue
        data = (DATA / "Dataset" / r["file"]).read_bytes()
        res = verify_images([data])
        doc = res.documents[0]
        w, h = doc.image_size
        boxes = [{"cls": "document", "box": [round(v, 4) for v in document_outline(
            _bgr(data))]}]
        for reg in doc.regions:
            cls = {"PHOTOGRAPH": "photograph", "MRZ": "mrz", "QR_CODE": "qr_code", "BARCODE": "barcode",
                   "STAMP": "stamp"}.get(reg.label.value)
            if reg.label.value == "SECURITY_FEATURE" and reg.meta.get("detector_label") == "YELLOW_GOLD_FEATURE":
                cls = "yellow_gold_feature"
            if cls:
                b = reg.bbox
                boxes.append({"cls": cls, "box": [round(max(0, b[0]) / w, 4), round(max(0, b[1]) / h, 4),
                                                   round(min(w, b[2]) / w, 4), round(min(h, b[3]) / h, 4)]})
        out[r["file"]] = boxes
        print(r["file"], [b["cls"] for b in boxes], flush=True)
    (DATA / "boxes_auto.json").write_text(json.dumps(out, indent=1))


def _bgr(data: bytes) -> np.ndarray:
    from app.services.docverify.detection import decode_image
    return decode_image(data)[0]


if __name__ == "__main__":
    main()
