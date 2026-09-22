"""PP-OCR provider — PaddleOCR models via RapidOCR (ONNX runtime).

Uses PP-OCR's text detection + recognition models running on ONNX runtime
via rapidocr-onnxruntime. This avoids PaddlePaddle's heavy native runtime
while using the same underlying PP-OCR model weights.
"""
import io
import logging
import threading

import numpy as np
from PIL import Image, ImageOps

from app.services.ocr.base import OCRProvider, OCRResult
from app.services.ocr.field_extraction import extract_fields

logger = logging.getLogger("pramaan.ocr.ppocr")

_ocr_instance = None
_ocr_lock = threading.Lock()


def _get_ocr():
    global _ocr_instance
    if _ocr_instance is not None:
        return _ocr_instance
    with _ocr_lock:
        if _ocr_instance is not None:
            return _ocr_instance
        from rapidocr_onnxruntime import RapidOCR
        _ocr_instance = RapidOCR()
        logger.info("PP-OCR (RapidOCR/ONNX) initialized")
        return _ocr_instance


class PaddleOCRProvider(OCRProvider):
    def extract(self, image_bytes: bytes, document_type: str) -> OCRResult:
        image = Image.open(io.BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")

        img_array = np.array(image)

        try:
            ocr = _get_ocr()
            result = ocr(img_array)
        except Exception as e:
            logger.warning("PP-OCR failed: %s", e)
            return OCRResult(
                document_type=document_type,
                fields={},
                ocr_confidence=0.0,
            )

        lines: list[str] = []
        confidences: list[float] = []
        bounding_boxes: list[dict] = []

        data = result[0] if isinstance(result, tuple) else result
        if data:
            for item in data:
                box, text, score = item[0], item[1], item[2]
                text = text.strip()
                if text:
                    lines.append(text)
                    confidences.append(float(score))
                    if box is not None:
                        xs = [p[0] for p in box]
                        ys = [p[1] for p in box]
                        bounding_boxes.append({
                            "text": text,
                            "confidence": round(float(score), 4),
                            "x0": int(min(xs)), "y0": int(min(ys)),
                            "x1": int(max(xs)), "y1": int(max(ys)),
                        })

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        raw_text = "\n".join(lines)

        fields = extract_fields(document_type, raw_text)

        return OCRResult(
            document_type=document_type,
            fields=fields,
            ocr_confidence=round(avg_confidence, 4),
            raw_text=raw_text,
            bounding_boxes=bounding_boxes,
        )
