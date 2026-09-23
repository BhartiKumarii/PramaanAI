"""OCR provider interface — PP-OCR backed via RapidOCR/ONNX runtime."""
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class OCRResult(BaseModel):
    document_type: str  # The document type used for extraction (may be user-provided or auto-detected)
    fields: dict[str, str]
    ocr_confidence: float
    raw_text: str = ""
    bounding_boxes: list[dict] = Field(default_factory=list)
    detected_document_type: str | None = None  # Auto-detected document type (if classification was run)
    classification_confidence: float | None = None  # Confidence of auto-detection


class OCRProvider(ABC):
    @abstractmethod
    def extract(self, image_bytes: bytes, document_type: str) -> OCRResult:
        """Extract structured fields from a document image."""
