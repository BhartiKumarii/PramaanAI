"""Region detection — the first stage of the pipeline.

Two interchangeable implementations behind one interface:

* YoloRegionDetector — YOLO11 (ultralytics) with trained weights configured
  via PRAMAAN_YOLO_WEIGHTS. Class names are mapped onto RegionLabel; stamp
  sub-classes (IMMIGRATION_STAMP, ENTRY_STAMP, ...) are kept as
  `detector_label` and later cross-checked against the stamp's own text.
* ClassicalRegionDetector — fallback when no trained weights (or no
  ultralytics install) are available, e.g. on a slim deployment. Face
  detectors locate the photograph; ink segmentation + Hough circles propose
  stamp *candidates*; OCR label anchors locate the signature area.

Trained weights: models/yolo/pramaan_regions_yolo11n.pt, produced by
scripts/docverify/yolo (labelled real photos + synthetic documents). They are
used automatically when present unless PRAMAAN_YOLO_WEIGHTS says otherwise.

Colour and shape are only ever used to PROPOSE a candidate region here —
never to identify a country, an authority or a border type. Every region
records which method produced it, so no classical result is ever presented
as a YOLO detection.
"""
from __future__ import annotations

import io
import logging
import threading
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from app.core.config import get_settings
from app.services.docverify.types import OcrLine, Region, RegionLabel

logger = logging.getLogger("pramaan.docverify.detection")

# YOLO class name -> (RegionLabel, detector_label)
YOLO_CLASS_MAP: dict[str, tuple[RegionLabel, str | None]] = {
    "document": (RegionLabel.DOCUMENT, None),
    "passport": (RegionLabel.PASSPORT, None),
    "visa": (RegionLabel.VISA, None),
    "driving_licence": (RegionLabel.DRIVING_LICENCE, None),
    "identity_document": (RegionLabel.IDENTITY_DOCUMENT, None),
    "entry_permit": (RegionLabel.ENTRY_PERMIT, None),
    "visa_sticker": (RegionLabel.VISA_STICKER, None),
    "immigration_stamp": (RegionLabel.STAMP, "IMMIGRATION_STAMP"),
    "visa_stamp": (RegionLabel.STAMP, "VISA_STAMP"),
    "entry_stamp": (RegionLabel.STAMP, "ENTRY_STAMP"),
    "exit_stamp": (RegionLabel.STAMP, "EXIT_STAMP"),
    "permit_marking": (RegionLabel.STAMP, "PERMIT_MARKING"),
    "stamp": (RegionLabel.STAMP, "STAMP"),  # generic: the stamp's type comes from its own text
    "photograph": (RegionLabel.PHOTOGRAPH, None),
    "qr_code": (RegionLabel.QR_CODE, None),
    "barcode": (RegionLabel.BARCODE, None),
    "mrz": (RegionLabel.MRZ, None),
    "security_feature": (RegionLabel.SECURITY_FEATURE, None),
    "yellow_gold_feature": (RegionLabel.SECURITY_FEATURE, "YELLOW_GOLD_FEATURE"),
    "signature": (RegionLabel.SIGNATURE, None),
}


class RegionDetector(ABC):
    name: str

    @abstractmethod
    def detect(self, bgr: np.ndarray, ocr_lines: list[OcrLine], *, want_stamps: bool) -> list[Region]:
        ...


# ------------------------------------------------------------------ helpers

def _encode_png(bgr: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", bgr)
    return buf.tobytes() if ok else b""


_BLAZEFACE_LOCK = threading.Lock()


def detect_faces(bgr: np.ndarray) -> list[tuple[list[int], float, str]]:
    """Faces as (bbox, confidence, method). BlazeFace first (fast); falls
    back to InsightFace's SCRFD detector, which handles the small, printed
    faces on ID cards that BlazeFace's short-range model misses."""
    from app.services.face.blazeface_detector import BlazeFaceDetector

    faces: list[tuple[list[int], float, str]] = []
    try:
        with _BLAZEFACE_LOCK:  # the shared MediaPipe detector is not re-entrant
            result = BlazeFaceDetector().detect(_encode_png(bgr))
        for f in result.faces:
            loc = f.location
            faces.append(([loc["x"], loc["y"], loc["x"] + loc["width"], loc["y"] + loc["height"]],
                          float(f.confidence), "blazeface"))
    except Exception as exc:
        logger.debug("BlazeFace failed: %s", exc)
    if faces:
        return faces
    try:
        from app.services.face.mobilefacenet_provider import _get_insightface_app

        app = _get_insightface_app()
        if app is not None:
            for f in app.get(bgr):
                x0, y0, x1, y1 = (int(v) for v in f.bbox)
                faces.append(([x0, y0, x1, y1], float(f.det_score), "insightface-scrfd"))
            if not faces:
                faces = _tiled_faces(app, bgr)
    except Exception as exc:
        logger.debug("InsightFace detection failed: %s", exc)
    return faces


def _tiled_faces(app, bgr: np.ndarray) -> list[tuple[list[int], float, str]]:
    """Second pass for small printed portraits: the detector downsamples the
    whole page to 640px, which shrinks an ID photo below its threshold. Run
    it on overlapping half-page tiles instead and merge the hits."""
    h, w = bgr.shape[:2]
    out: list[tuple[list[int], float, str]] = []
    tw, th = int(w * 0.6), int(h * 0.75)
    for ox in (0, w - tw):
        for oy in (0, h - th):
            for f in app.get(bgr[oy:oy + th, ox:ox + tw]):
                box = [int(f.bbox[0]) + ox, int(f.bbox[1]) + oy, int(f.bbox[2]) + ox, int(f.bbox[3]) + oy]
                if not any(_overlap_fraction(box, o[0]) > 0.5 for o in out):
                    out.append((box, float(f.det_score), "insightface-scrfd:tiled"))
    return out


def _photo_region_from_face(face: list[int], shape: tuple[int, ...]) -> list[int]:
    h, w = shape[:2]
    fw, fh = face[2] - face[0], face[3] - face[1]
    return [max(0, int(face[0] - 0.35 * fw)), max(0, int(face[1] - 0.45 * fh)),
            min(w, int(face[2] + 0.35 * fw)), min(h, int(face[3] + 0.55 * fh))]


def _overlap_fraction(inner: list[int], outer: list[int]) -> float:
    ix0, iy0 = max(inner[0], outer[0]), max(inner[1], outer[1])
    ix1, iy1 = min(inner[2], outer[2]), min(inner[3], outer[3])
    inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
    area = max(1, (inner[2] - inner[0]) * (inner[3] - inner[1]))
    return inter / area


def stamp_candidates(bgr: np.ndarray, exclude: list[list[int]], max_candidates: int = 8) -> list[tuple[list[int], float, str]]:
    """Propose stamp regions from (a) coloured-ink blobs and (b) circular
    outlines. Candidates only — the stamp pipeline keeps a candidate only if
    its text or structure supports it."""
    h, w = bgr.shape[:2]
    area_img = h * w
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    ink = ((hsv[..., 1] > 70) & (hsv[..., 2] > 50) & (hsv[..., 2] < 245)).astype(np.uint8) * 255
    k = max(3, int(min(h, w) * 0.012)) | 1
    closed = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)), iterations=2)
    out: list[tuple[list[int], float, str]] = []
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        box = [x, y, x + cw, y + ch]
        rel = (cw * ch) / area_img
        if rel < 0.006 or rel > 0.45 or min(cw, ch) < 30:
            continue
        aspect = cw / max(1, ch)
        if aspect > 4.0 or aspect < 0.25:
            continue
        density = cv2.countNonZero(ink[y:y + ch, x:x + cw]) / max(1, cw * ch)
        if not 0.04 <= density <= 0.65:  # ink strokes, not a solid colour block
            continue
        if any(_overlap_fraction(box, ex) > 0.5 for ex in exclude):
            continue
        out.append((box, round(min(0.8, 0.35 + density), 3), "classical:ink-segmentation"))

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    scale = 800 / max(h, w) if max(h, w) > 800 else 1.0
    small = cv2.resize(gray, None, fx=scale, fy=scale) if scale != 1.0 else gray
    circles = cv2.HoughCircles(cv2.medianBlur(small, 5), cv2.HOUGH_GRADIENT, dp=1.2,
                               minDist=int(min(small.shape) * 0.15), param1=120, param2=60,
                               minRadius=int(min(small.shape) * 0.06), maxRadius=int(min(small.shape) * 0.3))
    if circles is not None:
        for cx, cy, r in circles[0][:6]:
            cx, cy, r = cx / scale, cy / scale, r / scale
            box = [max(0, int(cx - r)), max(0, int(cy - r)), min(w, int(cx + r)), min(h, int(cy + r))]
            if any(_overlap_fraction(box, ex) > 0.5 for ex in exclude):
                continue
            if any(_overlap_fraction(box, o[0]) > 0.3 for o in out):
                continue  # same impression already proposed by ink segmentation
            out.append((box, 0.5, "classical:hough-circle"))
    out.sort(key=lambda o: -o[1])
    return out[:max_candidates]


def _signature_region(ocr_lines: list[OcrLine], shape: tuple[int, ...]) -> list[int] | None:
    h, w = shape[:2]
    for line in ocr_lines:
        t = line.text.lower()
        if "signature" in t or "holder's sign" in t or "sign of" in t:
            x0, y0, x1, y1 = line.bbox
            lh = y1 - y0
            return [max(0, x0 - lh), max(0, y0 - 3 * lh), min(w, x1 + 2 * lh), min(h, y1 + lh)]
    return None


# ------------------------------------------------------------------ detectors

class ClassicalRegionDetector(RegionDetector):
    name = "classical-opencv (no trained YOLO weights configured)"

    def detect(self, bgr: np.ndarray, ocr_lines: list[OcrLine], *, want_stamps: bool) -> list[Region]:
        regions: list[Region] = []
        photos: list[list[int]] = []
        for i, (face, conf, method) in enumerate(detect_faces(bgr)):
            photo = _photo_region_from_face(face, bgr.shape)
            photos.append(photo)
            regions.append(Region(id=f"photo-{i + 1}", label=RegionLabel.PHOTOGRAPH, bbox=photo,
                                  confidence=round(conf, 3), source=f"classical:{method}",
                                  meta={"face_bbox": face}))
        sig = _signature_region(ocr_lines, bgr.shape)
        if sig:
            regions.append(Region(id="signature-1", label=RegionLabel.SIGNATURE, bbox=sig, confidence=0.4,
                                  source="classical:ocr-label-anchor"))
        if want_stamps:
            for i, (box, conf, method) in enumerate(stamp_candidates(bgr, exclude=photos)):
                regions.append(Region(id=f"stamp-{i + 1}", label=RegionLabel.STAMP, bbox=box,
                                      confidence=conf, source=method, meta={"candidate": True}))
        return regions


class YoloRegionDetector(RegionDetector):
    """Ultralytics models are not thread-safe for concurrent predict(), so
    each worker thread lazily gets its own copy of the (5 MB) model."""

    def __init__(self, weights: str, conf: float):
        from ultralytics import YOLO  # optional dependency — ImportError selects the fallback

        self._weights = weights
        self._conf = conf
        self._local = threading.local()
        self._local.model = YOLO(weights)
        self.name = f"yolo11:{Path(weights).name}"

    def _model(self):
        model = getattr(self._local, "model", None)
        if model is None:
            from ultralytics import YOLO
            model = self._local.model = YOLO(self._weights)
        return model

    def detect(self, bgr: np.ndarray, ocr_lines: list[OcrLine], *, want_stamps: bool) -> list[Region]:
        result = self._model().predict(bgr, conf=self._conf, verbose=False)[0]
        names = result.names
        regions: list[Region] = []
        for i, box in enumerate(result.boxes):
            cls_name = str(names[int(box.cls)]).lower()
            if cls_name not in YOLO_CLASS_MAP:
                continue
            label, sub = YOLO_CLASS_MAP[cls_name]
            if label == RegionLabel.STAMP and not want_stamps:
                continue
            x0, y0, x1, y1 = (int(v) for v in box.xyxy[0].tolist())
            regions.append(Region(id=f"{label.value.lower()}-{i + 1}", label=label, bbox=[x0, y0, x1, y1],
                                  confidence=round(float(box.conf), 3), source=self.name,
                                  meta={"detector_label": sub, "yolo_class": cls_name}))
        # YOLO has no photograph class trained? Fall back to face detection for it.
        if not any(r.label == RegionLabel.PHOTOGRAPH for r in regions):
            regions.extend(r for r in ClassicalRegionDetector().detect(bgr, ocr_lines, want_stamps=False)
                           if r.label == RegionLabel.PHOTOGRAPH)
        return regions


DEFAULT_WEIGHTS = Path(__file__).resolve().parents[3] / "models/yolo/pramaan_regions_yolo11n.pt"


@lru_cache
def get_region_detector() -> RegionDetector:
    settings = get_settings()
    # Explicit setting wins; "none" forces the classical detector; otherwise
    # the project's trained weights are used when present.
    weights = settings.pramaan_yolo_weights or (str(DEFAULT_WEIGHTS) if DEFAULT_WEIGHTS.is_file() else "")
    if weights.lower() == "none":
        return ClassicalRegionDetector()
    if weights:
        if not Path(weights).is_file():
            logger.warning("PRAMAAN_YOLO_WEIGHTS=%s not found — using classical detector", weights)
        else:
            try:
                return YoloRegionDetector(weights, settings.pramaan_yolo_conf)
            except ImportError:
                logger.warning("ultralytics not installed — using classical detector")
    return ClassicalRegionDetector()


def decode_image(image_bytes: bytes, max_side: int = 1800) -> tuple[np.ndarray, np.ndarray]:
    """Decode (EXIF-orientation aware) to (bgr, rgb), capped in size."""
    from PIL import Image, ImageOps

    image = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes))).convert("RGB")
    if max(image.size) > max_side:
        image.thumbnail((max_side, max_side))
    rgb = np.asarray(image)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), rgb
