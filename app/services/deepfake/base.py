"""Deepfake detection interface (Module — see heuristic_provider.py for
the real implementation and its honest scope/limits)."""
from abc import ABC, abstractmethod

from pydantic import BaseModel


class DeepfakeResult(BaseModel):
    status: str  # ANALYZED (this build always produces a real result) | NOT_IMPLEMENTED
    score: float | None = None  # 0..1 heuristic risk, higher = more suspicious
    reason: str


class DeepfakeProvider(ABC):
    @abstractmethod
    def analyze(self, image_bytes: bytes) -> DeepfakeResult:
        """Run deepfake/synthetic-image heuristics; return a risk indicator, not a verdict."""
