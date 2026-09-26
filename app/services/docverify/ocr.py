"""Region-aware OCR on top of the existing PP-OCR engine.

Reuses app.services.ocr.paddleocr_provider's shared PP-OCR (PaddleOCR
detection + recognition weights on ONNX runtime) instance, so the model is
loaded once per process. Every line keeps its confidence and bounding box.
"""
from __future__ import annotations

import logging
import os
import re
import threading
from contextlib import contextmanager

import cv2
import numpy as np

from app.services.docverify.types import OcrLine



class _EnginePool:
    """Shared engines, at most one per concurrently running verification.

    Engines are not shared between two threads at the same time (RapidOCR's
    pre/post-processing is not guaranteed thread-safe), but they are reused
    across threads: worker threads come and go, and a copy per thread cost
    ~70 MB of RAM each time a new one appeared."""

    def __init__(self, factory):
        self._factory = factory
        self._idle: list = []
        self._lock = threading.Lock()

    @contextmanager
    def borrow(self):
        with self._lock:
            engine = self._idle.pop() if self._idle else None
        if engine is None:
            engine = self._factory()
        try:
            yield engine
        finally:
            if engine is not None:
                with self._lock:
                    self._idle.append(engine)


DET_MAX_SIDE = 1280


def _cap_detector(engine):
    """Run text DETECTION at most DET_MAX_SIDE px on the long side.

    RapidOCR detects at up to 2000 px, which on an 1800 px photo cost ~350 MB
    of transient RAM — over a 512 MB instance's limit. Recognition still reads
    each line from the full-resolution image, so only box finding is coarser
    (960 px misread two real documents in the evaluation; 1280 did not).
    RapidOCR's own "max" limit type rounds back up to 2000, hence replacing
    get_preprocess."""
    from rapidocr_onnxruntime.ch_ppocr_det.utils import DetPreProcess
    det = engine.text_det
    det.get_preprocess = lambda max_wh: (DetPreProcess(DET_MAX_SIDE, "max", det.mean, det.std)
                                         if max_wh > DET_MAX_SIDE
                                         else DetPreProcess(det.limit_side_len, det.limit_type, det.mean, det.std))
    return engine


def _new_ocr():
    from rapidocr_onnxruntime import RapidOCR
    n = ocr_threads()
    # rec_batch_num=2 (default 6): a batch is padded to its widest line, and
    # one long line made a batch of 6 cost ~120 MB; 2 costs ~15 MB. 1 was
    # leaner still but misread a real Nepal visa in the evaluation.
    return _cap_detector(RapidOCR(intra_op_num_threads=n, inter_op_num_threads=1, rec_batch_num=2))


_OCR = _EnginePool(_new_ocr)


def _get_ocr():
    """An engine for a one-off check outside a verification (e.g. warm-up)."""
    with _OCR.borrow() as engine:
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


TEXT_SCORE = 0.5  # RapidOCR's own default line-score cut-off


def ocr_image(rgb: np.ndarray, offset: tuple[int, int] = (0, 0), scale: float = 1.0,
              low_out: list[OcrLine] | None = None) -> list[OcrLine]:
    """OCR an RGB array. `offset`/`scale` map crop coordinates back into the
    source image so every bbox is in original-image pixels.

    Lines scoring under TEXT_SCORE are dropped exactly as RapidOCR would; when
    `low_out` is given they are collected there instead (Devanagari text is
    detected but scores low with the Latin recogniser)."""
    try:
        # text_score is passed on every call: RapidOCR keeps call kwargs on
        # the engine, and the filtering is done here.
        with _OCR.borrow() as engine:
            result = engine(rgb, text_score=0.0, box_thresh=0.5, unclip_ratio=1.6)
    except Exception as exc:  # engine failure is reported, never hidden
        logger.warning("PP-OCR failed: %s", exc)
        return []
    data = result[0] if isinstance(result, tuple) else result
    lines: list[OcrLine] = []
    for item in data or []:
        box, text, score = item[0], str(item[1]).strip(), float(item[2])
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        line = OcrLine(
            text=text,
            confidence=round(score, 4),
            bbox=[int(min(xs) / scale) + offset[0], int(min(ys) / scale) + offset[1],
                  int(max(xs) / scale) + offset[0], int(max(ys) / scale) + offset[1]],
        )
        if text and score >= TEXT_SCORE:
            lines.append(line)
        elif low_out is not None:
            low_out.append(line)
    return lines


_GLUED_WORDS = re.compile(r"[A-Za-z]{11,}|[a-z]{3,}[A-Z][a-z]{2,}")
_GLUED_DATES = re.compile(r"\d{4}\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}")
_DATE_IN = re.compile(r"\d{1,2}[-/.]\d{1,2}[-/.](?:\d{4}|\d{2})")


def respace_lines(rgb: np.ndarray, lines: list[OcrLine]) -> list[OcrLine]:
    """Fix lines where PP-OCR ran words or dates together.

    Bold capitals and tightly set dates are often read without their spaces
    ("DEEPCHANDCHANWARIA", "06-05-202505-05-2030"). Re-reading just that line
    (recognition only, padded, original size) usually restores them. A new
    reading is accepted only if it has exactly the same letters and digits,
    so this can only add spaces, never change what was read. Two or more
    dates on one line are split into separate boxes (x estimated from the
    character position) so each can sit under its own label."""
    out: list[OcrLine] = []
    h, w = rgb.shape[:2]
    for line in lines:
        text = line.text
        if "<" in text or not (_GLUED_WORDS.search(text) or _GLUED_DATES.search(text)):
            out.append(line)
            continue
        x0, y0, x1, y1 = line.bbox
        crop = rgb[max(0, y0 - 4):min(h, y1 + 4), max(0, x0 - 4):min(w, x1 + 4)]
        if crop.size == 0:
            out.append(line)
            continue
        key = re.sub(r"[^A-Za-z0-9]", "", text).upper()
        new = text
        for scale in (1, 2):  # the two sizes restore different gaps; keep the best
            c = crop if scale == 1 else cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            c = cv2.copyMakeBorder(c, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=(255, 255, 255))
            try:
                with _OCR.borrow() as engine:
                    res, _ = engine(c, use_det=False, use_cls=False)
            except Exception:
                res = None
            cand = str(res[0][0]).strip() if res else ""
            if re.sub(r"[^A-Za-z0-9]", "", cand).upper() == key and cand.count(" ") > new.count(" "):
                new = cand
        if new == text:
            out.append(line)
            continue
        dates = list(_DATE_IN.finditer(new))
        if len(dates) >= 2:
            span = max(1, len(new))
            for m in dates:
                a, b = m.start() / span, m.end() / span
                out.append(OcrLine(text=m.group(0), confidence=line.confidence,
                                   bbox=[x0 + int((x1 - x0) * a), y0, x0 + int((x1 - x0) * b), y1]))
        else:
            out.append(line.model_copy(update={"text": new}))
    return out


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


_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
DEVANAGARI_ENGINE = "PP-OCRv5 Devanagari recognition (PaddleOCR weights, ONNX runtime)"


def _devanagari_paths() -> tuple[str, str] | None:
    from app.core.config import get_settings
    d = get_settings().pramaan_devanagari_rec_dir
    model, keys = os.path.join(d, "inference.onnx"), os.path.join(d, "keys.txt")
    return (model, keys) if os.path.isfile(model) and os.path.isfile(keys) else None


def devanagari_available() -> bool:
    return _devanagari_paths() is not None


def _new_devanagari():
    paths = _devanagari_paths()
    if paths is None:
        return None
    from rapidocr_onnxruntime import RapidOCR
    n = ocr_threads()
    engine = RapidOCR(rec_model_path=paths[0], rec_keys_path=paths[1], intra_op_num_threads=n, inter_op_num_threads=1,
                      rec_batch_num=1)
    # Only recognition is used (use_det=False, use_cls=False below): release
    # the detector and classifier RapidOCR always loads (~20 MB).
    engine.text_det = engine.text_cls = None
    return engine


_DEVANAGARI_POOL = _EnginePool(_new_devanagari)


def _get_devanagari():
    with _DEVANAGARI_POOL.borrow() as engine:
        return engine


def devanagari_lines(rgb: np.ndarray, lines: list[OcrLine], low: list[OcrLine],
                     min_confidence: float = 0.6) -> list[OcrLine]:
    """Re-read text boxes with the Devanagari recogniser (Nepali/Hindi).

    The main PP-OCR model reads Latin script only: Devanagari lines come back
    as low-scoring junk (dropped) or short uncertain readings. Those boxes —
    from the same detection pass, so no second detection — are re-read with
    recognition only. Only readings that contain Devanagari are returned, as
    extra lines; the Latin reading is never replaced."""
    if not devanagari_available():
        return []
    with _DEVANAGARI_POOL.borrow() as engine:
        return _read_devanagari(engine, rgb, lines, low, min_confidence)


def _read_devanagari(engine, rgb: np.ndarray, lines: list[OcrLine], low: list[OcrLine],
                     min_confidence: float) -> list[OcrLine]:
    h, w = rgb.shape[:2]
    out: list[OcrLine] = []
    for line in low + [l for l in lines if l.confidence < 0.9]:
        x0, y0, x1, y1 = line.bbox
        pad = max(2, (y1 - y0) // 8)
        x0, y0, x1, y1 = max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)
        if x1 - x0 < 8 or y1 - y0 < 8:
            continue
        try:
            res, _ = engine(np.ascontiguousarray(rgb[y0:y1, x0:x1]), use_det=False, use_cls=False)
        except Exception as exc:  # reported by the caller as "not read"
            logger.warning("Devanagari OCR failed: %s", exc)
            return out
        if not res:
            continue
        text, score = str(res[0][0]).strip(), float(res[0][1])
        if score >= min_confidence and len(_DEVANAGARI.findall(text)) >= 2:
            out.append(OcrLine(text=text, confidence=round(score, 4), bbox=list(line.bbox)))
    return out


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
