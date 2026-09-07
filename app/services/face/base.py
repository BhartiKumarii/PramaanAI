"""Face verification provider interface — Module 4: face detection,
embedding extraction, and cosine-similarity matching."""
from abc import ABC, abstractmethod

from pydantic import BaseModel


class FaceMatchResult(BaseModel):
    match: bool
    similarity: float
    confidence: float
    reason: str  # specific similarity value + threshold, never a generic string
    location: dict | None = None  # detected face bbox in the presented image, null if none found


class FaceProvider(ABC):
    @abstractmethod
    def verify(self, document_face: bytes, presented_face: bytes) -> FaceMatchResult:
        """Compare a face extracted from a document against a presented live photo."""
