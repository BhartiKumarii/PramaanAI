"""OCR provider interface — PP-OCR backed via RapidOCR/ONNX runtime."""
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class OCRResult(BaseModel):
    document_type: str
    fields: dict[str, str]
    ocr_confidence: float
    raw_text: str = ""
    bounding_boxes: list[dict] = Field(default_factory=list)


class OCRProvider(ABC):
    @abstractmethod
    def extract(self, image_bytes: bytes, document_type: str) -> OCRResult:
        """Extract structured fields from a document image."""
