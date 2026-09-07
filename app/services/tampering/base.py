"""Document forensics/tampering provider interface — Module 3: Error Level
Analysis (ELA) baseline. Designed so a trained classifier can replace the
baseline without changing callers."""
from abc import ABC, abstractmethod

from pydantic import BaseModel


class TamperingFinding(BaseModel):
    type: str
    confidence: float
    reason: str  # specific values (block stats), never a generic string
    location: dict | None = None  # bounding box of the highest-anomaly region


class TamperingResult(BaseModel):
    tampering_risk: float
    findings: list[TamperingFinding]


class TamperingProvider(ABC):
    @abstractmethod
    def analyze(self, image_bytes: bytes) -> TamperingResult:
        """Run forensic analysis on a document image; return a risk indicator, not a verdict."""
