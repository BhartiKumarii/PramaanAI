"""OCR provider interface. Concrete implementation (PaddleOCR-backed) is
Module 1, not yet built — this defines the swappable contract only."""
from abc import ABC, abstractmethod

from pydantic import BaseModel


class OCRResult(BaseModel):
    document_type: str
    fields: dict[str, str]
    ocr_confidence: float


class OCRProvider(ABC):
    @abstractmethod
    def extract(self, image_bytes: bytes, document_type: str) -> OCRResult:
        """Extract structured fields from a document image."""
