from pydantic import BaseModel, Field

from app.schemas.document import DocumentType
from app.services.citizen_registry.base import CitizenRegistryResult
from app.services.deepfake.base import DeepfakeResult
from app.services.duplicate.base import DuplicateDocumentResult
from app.services.face.base import FaceDetectionResult, FaceMatchResult
from app.services.identity_graph.base import IdentityGraphResult
from app.services.liveness.base import LivenessResult
from app.services.ocr.base import OCRResult
from app.services.registry.base import RegistryLookupResult
from app.services.risk.base import RiskResult
from app.services.tampering.base import TamperingResult
from app.services.validation.base import ValidationResult


class ScreeningSubmission(BaseModel):
    """What the device actually sends for a screening — extracted,
    encoded data only, never a raw image. OCR (image -> text) and MRZ
    zone OCR both run on-device; this still carries the *result* of that
    on-device OCR (structured fields, or the raw MRZ text for the
    server's existing checksum/parsing logic to run on) rather than
    pixels. Tampering/deepfake/liveness need pixel-level analysis, which
    can only happen where the pixels are (on-device) — when the device
    hasn't computed one yet, it's simply omitted here, and the risk
    engine already treats a missing signal as "not run", never as
    "clean" (see app/services/risk/engine.py)."""

    document_type: DocumentType
    nationality: str
    ocr_fields: dict[str, str] = Field(default_factory=dict)
    ocr_confidence: float = 0.0
    # Raw text from an on-device OCR pass over the MRZ zone specifically
    # (two or three 44-char lines) — the server still does the actual
    # TD3 parsing + modulo-10 checksum validation (app/services/validation/mrz.py),
    # unchanged; only the image-to-text step moved to the device.
    mrz_text: str | None = None
    aadhaar_number: str | None = None
    # Real fixed-length descriptor vectors computed on-device (see
    # app/services/face/embedding.py for the algorithm every device
    # implementation must match) — never the photos themselves.
    document_face_embedding: list[float] | None = None
    live_face_embedding: list[float] | None = None
    tampering_result: TamperingResult | None = None
    deepfake_result: DeepfakeResult | None = None
    liveness_result: LivenessResult | None = None
    # On-device ML Kit face detection over the live selfie capture (see
    # FaceDetectionAnalyzer.kt) — face count/position, never the image.
    face_detection_result: FaceDetectionResult | None = None


class ScreeningResponse(BaseModel):
    verification_id: str
    # The Case this screening created (see app/models/case.py) — the
    # Android "Send to Immigration" button calls POST
    # /cases/{case_id}/submit with this id.
    case_id: str
    case_number: str
    case_status: str
    risk: RiskResult
    ocr: OCRResult | None = None
    validation: ValidationResult | None = None
    tampering: TamperingResult | None = None
    deepfake: DeepfakeResult | None = None
    registry: RegistryLookupResult | None = None
    face: FaceMatchResult | None = None
    identity_graph: IdentityGraphResult | None = None
    liveness: LivenessResult | None = None
    duplicate_document: DuplicateDocumentResult | None = None
    face_detection: FaceDetectionResult | None = None
    citizen_registry: CitizenRegistryResult | None = None


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
    duplicate_document: DuplicateDocumentResult | None = None
    face_detection: FaceDetectionResult | None = None
    citizen_registry: CitizenRegistryResult | None = None


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
