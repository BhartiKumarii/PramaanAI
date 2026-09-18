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


class DetectedFace(BaseModel):
    location: dict  # {x, y, width, height} in the source image's pixel coordinates
    confidence: float
    # True if the detected box touches an image edge — a real, honest
    # proxy for "the face may be cropped/obscured by the frame", not a
    # claim about occlusion by an object (which this model doesn't
    # attempt to detect).
    touches_edge: bool


class FaceDetectionResult(BaseModel):
    status: str  # NO_FACE | SINGLE_FACE | MULTIPLE_FACES
    faces: list[DetectedFace]
    reason: str


class FaceDetector(ABC):
    @abstractmethod
    def detect(self, image_bytes: bytes) -> FaceDetectionResult:
        """Locate faces in an image — real face presence/count/position,
        never assumed. Distinct from FaceProvider.verify, which assumes
        its two inputs are already face-framed."""
