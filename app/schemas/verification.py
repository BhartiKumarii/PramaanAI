from pydantic import BaseModel

from app.services.deepfake.base import DeepfakeResult
from app.services.face.base import FaceMatchResult
from app.services.identity_graph.base import IdentityGraphResult
from app.services.liveness.base import LivenessResult
from app.services.ocr.base import OCRResult
from app.services.registry.base import RegistryLookupResult
from app.services.risk.base import RiskResult
from app.services.tampering.base import TamperingResult
from app.services.validation.base import ValidationResult


class ScreeningResponse(BaseModel):
    verification_id: str
    risk: RiskResult
    ocr: OCRResult | None = None
    validation: ValidationResult | None = None
    tampering: TamperingResult | None = None
    deepfake: DeepfakeResult | None = None
    registry: RegistryLookupResult | None = None
    face: FaceMatchResult | None = None
    identity_graph: IdentityGraphResult | None = None
    liveness: LivenessResult | None = None


class VerificationRecordResponse(BaseModel):
    id: str
    document_type: str
    nationality: str
    traveler_name: str | None = None
    risk: RiskResult
    signature_valid: bool
    created_at: str
    ocr: OCRResult | None = None
    validation: ValidationResult | None = None
    tampering: TamperingResult | None = None
    deepfake: DeepfakeResult | None = None
    registry: RegistryLookupResult | None = None
    face: FaceMatchResult | None = None
    identity_graph: IdentityGraphResult | None = None
    liveness: LivenessResult | None = None


class VerificationListItemResponse(BaseModel):
    id: str
    document_type: str
    nationality: str
    traveler_name: str | None = None
    score: int
    level: str
    decision: str
    status: str  # PENDING | DISPUTED | CLEARED — derived from the real audit trail
    created_at: str
