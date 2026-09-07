"""Liveness / anti-spoofing interface.

Scope, stated honestly: this checks the single live-capture image for
indicators of a *presentation attack* (a printed photo or a phone/screen
held up to the camera instead of a real face) — it does NOT verify that
the officer's on-screen challenge (e.g. "turn your head left") was
actually followed, since that would require analyzing a sequence of
frames/video for real head-pose motion, and this build's capture flow
takes a single still photo per step. The officer still visually judges
challenge compliance; this adds a real, automated single-image spoof
check alongside that, not a replacement for it.
"""
from abc import ABC, abstractmethod

from pydantic import BaseModel


class LivenessResult(BaseModel):
    status: str  # LIVE | SUSPECTED_SPOOF | NOT_IMPLEMENTED
    score: float | None = None  # 0..1 spoof-risk, higher = more suspicious
    reason: str


class LivenessProvider(ABC):
    @abstractmethod
    def analyze(self, live_capture_bytes: bytes) -> LivenessResult:
        """Run single-image anti-spoofing heuristics on the live capture."""
