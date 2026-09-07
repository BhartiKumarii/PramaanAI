"""Risk scoring engine interface — Module 6: weighted fusion of whatever
signals actually ran, with hard overrides for blacklist/multi-identity/
severe-mismatch. No API/UI path may ever construct a RiskResult except
through this engine — there is deliberately no way to pass in a score."""
from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.services.deepfake.base import DeepfakeResult
from app.services.face.base import FaceMatchResult
from app.services.identity_graph.base import IdentityGraphResult
from app.services.liveness.base import LivenessResult
from app.services.registry.base import RegistryLookupResult
from app.services.tampering.base import TamperingResult
from app.services.validation.base import ValidationResult


class RiskSignalBreakdown(BaseModel):
    signal: str
    weight: float  # normalized weight actually applied (renormalized over available signals)
    raw_risk: float  # 0..1, this signal's own risk contribution before weighting
    contribution: float  # weight * raw_risk
    reason: str
    location: dict | None = None


class RiskResult(BaseModel):
    score: int  # 0-100
    level: str  # LOW_RISK | MEDIUM_RISK | HIGH_RISK
    decision: str  # CLEAR | MANUAL_REVIEW
    top_reason: str
    breakdown: list[RiskSignalBreakdown]


class RiskEngine(ABC):
    @abstractmethod
    def score(
        self,
        validation_result: ValidationResult | None = None,
        tampering_result: TamperingResult | None = None,
        deepfake_result: DeepfakeResult | None = None,
        registry_result: RegistryLookupResult | None = None,
        face_result: FaceMatchResult | None = None,
        identity_graph_result: IdentityGraphResult | None = None,
        liveness_result: LivenessResult | None = None,
    ) -> RiskResult:
        """Combine whichever signals were actually supplied into one risk
        outcome, applying hard-override rules first."""
