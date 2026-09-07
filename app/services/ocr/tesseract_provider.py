import io

import pytesseract
from PIL import Image, ImageOps

from app.services.ocr.base import OCRProvider, OCRResult
from app.services.ocr.field_extraction import extract_fields


class TesseractOCRProvider(OCRProvider):
    """Real OCR via the Tesseract binary (through pytesseract).

    Chosen over PaddleOCR for this build: PaddleOCR pulls in PaddlePaddle
    (hundreds of MB), which is a poor fit for a hackathon build on a
    constrained connection. Swappable — anything implementing OCRProvider
    can replace this without touching callers.
    """

    def extract(self, image_bytes: bytes, document_type: str) -> OCRResult:
        image = Image.open(io.BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image)
        image = image.convert("L")
        image = ImageOps.autocontrast(image)

        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        confidences = []
        for raw_conf in data.get("conf", []):
            try:
                conf = int(float(raw_conf))
            except (TypeError, ValueError):
                continue
            if conf >= 0:
                confidences.append(conf)
        avg_confidence = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0

        raw_text = pytesseract.image_to_string(image)
        fields = extract_fields(document_type, raw_text)

        return OCRResult(
            document_type=document_type,
            fields=fields,
            ocr_confidence=round(avg_confidence, 4),
        )
