"""Region-aware OCR on top of the existing PP-OCR engine.

Reuses app.services.ocr.paddleocr_provider's shared PP-OCR (PaddleOCR
detection + recognition weights on ONNX runtime) instance, so the model is
loaded once per process. Every line keeps its confidence and bounding box.
"""
from __future__ import annotations

import logging
import threading

import cv2
import numpy as np

from app.services.docverify.types import OcrLine

_local = threading.local()


def _get_ocr():
    """One PP-OCR engine per worker thread: concurrent verifications never
    share a RapidOCR instance (its pre/post-processing is not guaranteed
    thread-safe). Threads are bounded by the concurrency limiter."""
    engine = getattr(_local, "engine", None)
    if engine is None:
        from rapidocr_onnxruntime import RapidOCR
        n = ocr_threads()
        engine = _local.engine = RapidOCR(intra_op_num_threads=n, inter_op_num_threads=1)
    return engine


def ocr_threads() -> int:
    """ONNX Runtime threads per engine. RapidOCR's default (-1 = every
    core) oversubscribes the CPU — on an 8-core machine 4 threads was ~2x
    faster with identical output (scripts/docverify/profile_pipeline.py)."""
    import os
    from app.core.config import get_settings
    configured = get_settings().pramaan_ocr_threads
    return configured if configured > 0 else max(1, min(4, (os.cpu_count() or 2) // 2))


logger = logging.getLogger("pramaan.docverify.ocr")

ENGINE_NAME = "PP-OCR (PaddleOCR det+rec weights, ONNX runtime via RapidOCR)"


def ocr_image(rgb: np.ndarray, offset: tuple[int, int] = (0, 0), scale: float = 1.0) -> list[OcrLine]:
    """OCR an RGB array. `offset`/`scale` map crop coordinates back into the
    source image so every bbox is in original-image pixels."""
    try:
        result = _get_ocr()(rgb)
    except Exception as exc:  # engine failure is reported, never hidden
        logger.warning("PP-OCR failed: %s", exc)
        return []
    data = result[0] if isinstance(result, tuple) else result
    lines: list[OcrLine] = []
    for item in data or []:
        box, text, score = item[0], str(item[1]).strip(), float(item[2])
        if not text:
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        lines.append(OcrLine(
            text=text,
            confidence=round(score, 4),
            bbox=[int(min(xs) / scale) + offset[0], int(min(ys) / scale) + offset[1],
                  int(max(xs) / scale) + offset[0], int(max(ys) / scale) + offset[1]],
        ))
    return lines


def ocr_region(rgb: np.ndarray, bbox: list[int], upscale_to: int = 900) -> list[OcrLine]:
    """Crop a region and OCR it — small regions (stamps) are upscaled first,
    since PP-OCR's detector misses small, rotated ink text at native size."""
    h, w = rgb.shape[:2]
    x0, y0, x1, y1 = max(0, bbox[0]), max(0, bbox[1]), min(w, bbox[2]), min(h, bbox[3])
    if x1 - x0 < 8 or y1 - y0 < 8:
        return []
    crop = rgb[y0:y1, x0:x1]
    longest = max(crop.shape[:2])
    scale = upscale_to / longest if longest < upscale_to else 1.0
    if scale != 1.0:
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    lines = ocr_image(crop, offset=(x0, y0), scale=scale)
    if not lines:
        # Round stamps often have text on an arc; one retry on a contrast-
        # normalised grey crop recovers some of it.
        gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        norm = cv2.equalizeHist(gray)
        lines = ocr_image(cv2.cvtColor(norm, cv2.COLOR_GRAY2RGB), offset=(x0, y0), scale=scale)
    return lines


def group_rows(lines: list[OcrLine]) -> list[list[OcrLine]]:
    """Group OCR boxes into visual rows (PP-OCR returns "Label" and "value"
    as separate boxes on the same row). Rows are sorted top-to-bottom and
    boxes left-to-right."""
    rows: list[list[OcrLine]] = []
    for line in sorted(lines, key=lambda l: (l.bbox[1] + l.bbox[3]) / 2):
        cy = (line.bbox[1] + line.bbox[3]) / 2
        height = max(1, line.bbox[3] - line.bbox[1])
        for row in rows:
            ref = row[0]
            ref_cy = (ref.bbox[1] + ref.bbox[3]) / 2
            if abs(cy - ref_cy) < 0.5 * max(height, ref.bbox[3] - ref.bbox[1]):
                row.append(line)
                break
        else:
            rows.append([line])
    return [sorted(r, key=lambda l: l.bbox[0]) for r in rows]


def mean_confidence(lines: list[OcrLine]) -> float:
    return round(sum(l.confidence for l in lines) / len(lines), 4) if lines else 0.0
