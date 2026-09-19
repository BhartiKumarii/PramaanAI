"""Document OCR / validation / tampering / screening endpoints.

/documents/ocr (Module 1), /documents/validate (Module 2),
/documents/tampering (Module 3), and the orchestrating /documents/screen
(Module 7) are implemented.
"""
import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
import json
import shutil
from pathlib import Path
from sqlalchemy.orm import Session

from app.api.deps import (
    get_blockchain_service,
    get_deepfake_provider,
    get_face_detector,
    get_face_provider,
    get_liveness_provider,
    get_ocr_provider,
    get_risk_engine,
    get_tampering_provider,
    get_validation_engine,
)
from app.core.security import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.case import CasePriority, CaseStatus
from app.models.network import EntityType
from app.models.user import User
from app.repositories.audit_repository import log_event
from app.repositories.case_repository import create_case
from app.repositories.identity_embedding_repository import get_embedding, insert_embedding, list_all
from app.repositories.identity_embedding_repository import set_case_id as set_embedding_case_id
from app.repositories.network_repository import (
    find_persons_by_document_hash,
    get_or_create_person,
    person_for_case,
    record_relationship,
    record_travel_event,
)
from app.repositories.verification_repository import create_verification
from app.schemas.document import DocumentType
from app.schemas.verification import ScreeningResponse, ScreeningSubmission
from app.services.blockchain.base import BlockchainService
from app.services.citizen_registry.base import CitizenRegistryResult
from app.services.citizen_registry.lookup import lookup_citizen_registry
from app.services.deepfake.base import DeepfakeProvider, DeepfakeResult
from app.services.duplicate.base import DuplicateDocumentResult
from app.services.duplicate.checker import check_duplicate_document
from app.services.face.base import FaceDetectionResult, FaceDetector, FaceMatchResult, FaceProvider
from app.services.face.classical_provider import match_from_embeddings
from app.services.identity_graph.base import IdentityGraphResult
from app.services.identity_graph.graph import build_graph, find_multi_identity_cluster
from app.services.liveness.base import LivenessProvider, LivenessResult
from app.services.ocr.base import OCRProvider, OCRResult
from app.services.ocr.mrz_ocr import extract_mrz_text
from app.services.registry.base import RegistryLookupResult
from app.services.registry.lookup import lookup_registry
from app.services.risk.base import RiskEngine
from app.services.tampering.base import TamperingProvider, TamperingResult
from app.services.validation.base import ValidationEngine, ValidationResult
from app.services.validation.mrz import MRZFormatError, extract_mrz_lines, parse_td3
from app.utils.image import downscale_image_bytes

router = APIRouter(prefix="/documents", tags=["documents"])


def _update_network_graph(
    db,
    *,
    case,
    name: str | None,
    document_number: str | None,
    nationality: str,
    identity_graph_result: IdentityGraphResult | None,
) -> None:
    """Real, explainable relationship detection — two signals only:
    (1) the same document number appearing on more than one case, and
    (2) the face-embedding cluster the risk pipeline already computed
    (identity_graph_result). Never a vague "these people are connected"
    inference — see app/repositories/network_repository.py."""
    person = get_or_create_person(db, name, document_number, nationality)
    record_travel_event(db, person.id, case.checkpoint_id, case.id)

    if document_number:
        for other in find_persons_by_document_hash(db, person.document_number_hash, person.id):
            record_relationship(
                db, EntityType.PERSON, person.id, EntityType.PERSON, other.id,
                "SAME_DOCUMENT_NUMBER", case.id,
                "The same document number was used to screen more than one case.",
            )

    if identity_graph_result is not None and identity_graph_result.status == "CLUSTER_FOUND":
        for member in identity_graph_result.members:
            member_embedding = get_embedding(db, uuid.UUID(member.record_id))
            if member_embedding is None or member_embedding.case_id is None or member_embedding.case_id == case.id:
                continue
            other_person = person_for_case(db, member_embedding.case_id)
            if other_person is None or other_person.id == person.id:
                continue
            record_relationship(
                db, EntityType.PERSON, person.id, EntityType.PERSON, other_person.id,
                "SIMILAR_IDENTITY", case.id,
                "The same face was matched across cases declared under different identities: "
                + identity_graph_result.reason,
            )


@router.post(
    "/ocr",
    response_model=OCRResult,
    summary="Extract structured fields from a document image via OCR",
)
async def ocr_document(
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    _user: User = Depends(get_current_user),
    ocr_provider: OCRProvider = Depends(get_ocr_provider),
) -> OCRResult:
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file upload")
    image_bytes = downscale_image_bytes(image_bytes)
    return ocr_provider.extract(image_bytes, document_type.value)


@router.post(
    "/validate",
    response_model=ValidationResult,
    summary="Nationality-aware document validation: MRZ/ICAO checksum for "
    "foreign nationals, Aadhaar/Verhoeff checksum for Indian nationals, "
    "plus front/back cross-validation when a back image is supplied",
)
async def validate_document(
    nationality: str = Form(...),
    front_fields: str = Form(..., description="JSON object of fields from a prior /documents/ocr call"),
    back_image: UploadFile | None = File(None),
    aadhaar_number: str | None = Form(None),
    _user: User = Depends(get_current_user),
    validation_engine: ValidationEngine = Depends(get_validation_engine),
) -> ValidationResult:
    try:
        ocr_result = json.loads(front_fields)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"front_fields is not valid JSON: {exc}"
        ) from exc
    if not isinstance(ocr_result, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="front_fields must be a JSON object")

    mrz_result = None
    if back_image is not None:
        back_bytes = await back_image.read()
        if not back_bytes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty back_image upload")
        back_bytes = downscale_image_bytes(back_bytes)
        raw_text = extract_mrz_text(back_bytes)
        lines = extract_mrz_lines(raw_text)
        if lines is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="could not locate two valid 44-character MRZ lines in back_image",
            )
        try:
            mrz_result = parse_td3(*lines)
        except MRZFormatError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return validation_engine.validate(
        ocr_result=ocr_result,
        mrz_result=mrz_result,
        nationality=nationality,
        aadhaar_number=aadhaar_number,
    )


@router.post(
    "/tampering",
    response_model=TamperingResult,
    summary="Error Level Analysis forensics: flags the highest-anomaly region of a document image",
)
async def analyze_tampering(
    file: UploadFile = File(...),
    _user: User = Depends(get_current_user),
    tampering_provider: TamperingProvider = Depends(get_tampering_provider),
) -> TamperingResult:
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file upload")
    image_bytes = downscale_image_bytes(image_bytes)
    return tampering_provider.analyze(image_bytes)


@router.post(
    "/detect-faces",
    response_model=FaceDetectionResult,
    summary="Real face detection (YuNet) — face presence, count, and position; "
    "diagnostic/testing endpoint, since the production device→server flow never "
    "sends raw images (see ScreeningSubmission.face_detection_result, computed "
    "on-device instead)",
)
async def detect_faces(
    file: UploadFile = File(...),
    _user: User = Depends(get_current_user),
    face_detector: FaceDetector = Depends(get_face_detector),
) -> FaceDetectionResult:
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file upload")
    image_bytes = downscale_image_bytes(image_bytes)
    return face_detector.detect(image_bytes)


@router.post(
    "/deepfake",
    response_model=DeepfakeResult,
    summary="Deepfake detection — a real frequency/noise heuristic (see module docstring for scope), never a faked pass",
)
async def deepfake_check(
    file: UploadFile = File(...),
    _user: User = Depends(get_current_user),
    deepfake_provider: DeepfakeProvider = Depends(get_deepfake_provider),
) -> DeepfakeResult:
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file upload")
    image_bytes = downscale_image_bytes(image_bytes)
    return deepfake_provider.analyze(image_bytes)


@router.post(
    "/screen",
    response_model=ScreeningResponse,
    summary="Full screening pipeline over encoded, on-device-extracted data — never a raw image "
    "(see ScreeningSubmission): validation, blacklist, face match, identity graph, and risk "
    "fusion over whatever signals the device already computed — persists a signed result",
)
def screen_document(
    payload: ScreeningSubmission,
    _user: User = Depends(get_current_user),
    validation_engine: ValidationEngine = Depends(get_validation_engine),
    risk_engine: RiskEngine = Depends(get_risk_engine),
    blockchain_service: BlockchainService = Depends(get_blockchain_service),
    db: Session = Depends(get_db),
) -> ScreeningResponse:
    if not payload.ocr_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ocr_fields is empty — on-device OCR must run before a screening is submitted",
        )
    ocr_result = OCRResult(
        document_type=payload.document_type.value, fields=payload.ocr_fields, ocr_confidence=payload.ocr_confidence
    )

    mrz_result = None
    if payload.mrz_text:
        try:
            lines = extract_mrz_lines(payload.mrz_text)
            if lines is not None:
                mrz_result = parse_td3(*lines)
        except MRZFormatError:
            mrz_result = None  # a real but unreadable MRZ read shouldn't abort the whole screening

    validation_result: ValidationResult = validation_engine.validate(
        ocr_result=payload.ocr_fields,
        mrz_result=mrz_result,
        nationality=payload.nationality,
        aadhaar_number=payload.aadhaar_number,
    )

    name_for_lookup = payload.ocr_fields.get("name")
    document_number_for_lookup = payload.ocr_fields.get("passport_number") or payload.aadhaar_number
    registry_result: RegistryLookupResult = lookup_registry(db, document_number_for_lookup, name_for_lookup)
    duplicate_document_result: DuplicateDocumentResult | None = check_duplicate_document(
        db, document_number_for_lookup, name_for_lookup
    )
    citizen_registry_result: CitizenRegistryResult | None = lookup_citizen_registry(
        db,
        document_number_for_lookup,
        name_for_lookup,
        payload.ocr_fields.get("date_of_birth"),
        payload.nationality,
    )

    face_result: FaceMatchResult | None = None
    if payload.document_face_embedding and payload.live_face_embedding:
        face_result = match_from_embeddings(payload.document_face_embedding, payload.live_face_embedding)

    identity_graph_result: IdentityGraphResult | None = None
    embedding_record = None
    if payload.live_face_embedding:
        embedding_record = insert_embedding(
            db, name_for_lookup or "UNKNOWN", document_number_for_lookup, payload.live_face_embedding
        )
        graph = build_graph(list_all(db))
        identity_graph_result = find_multi_identity_cluster(graph, str(embedding_record.id))

    # Tampering/deepfake/liveness need pixel-level analysis, which can
    # only run where the pixels are — on-device. Whatever the device
    # already computed (or None if it hasn't yet) passes straight
    # through; the risk engine treats a missing signal as "not run",
    # never as "clean" (see app/services/risk/engine.py).
    tampering_result = payload.tampering_result
    deepfake_result = payload.deepfake_result
    liveness_result = payload.liveness_result
    face_detection_result = payload.face_detection_result

    risk_result = risk_engine.score(
        validation_result=validation_result,
        tampering_result=tampering_result,
        deepfake_result=deepfake_result,
        registry_result=registry_result,
        face_result=face_result,
        identity_graph_result=identity_graph_result,
        liveness_result=liveness_result,
        duplicate_document_result=duplicate_document_result,
        face_detection_result=face_detection_result,
        citizen_registry_result=citizen_registry_result,
    )

    verification_record = create_verification(
        db,
        payload.document_type.value,
        payload.nationality,
        risk_result,
        traveler_name=name_for_lookup,
        ocr_result=ocr_result,
        validation_result=validation_result,
        tampering_result=tampering_result,
        deepfake_result=deepfake_result,
        registry_result=registry_result,
        face_result=face_result,
        identity_graph_result=identity_graph_result,
        liveness_result=liveness_result,
        duplicate_document_result=duplicate_document_result,
        face_detection_result=face_detection_result,
        citizen_registry_result=citizen_registry_result,
    )

    if _user.checkpoint_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your account has no assigned checkpoint — ask IT/Admin to assign one before screening.",
        )
    case = create_case(
        db,
        checkpoint_id=_user.checkpoint_id,
        field_officer_id=_user.id,
        verification_id=verification_record.id,
        document_type=payload.document_type.value,
        nationality=payload.nationality,
        traveler_name=name_for_lookup,
        initial_status=CaseStatus.REVIEW_REQUIRED if risk_result.decision == "MANUAL_REVIEW" else CaseStatus.PENDING,
        priority={"HIGH_RISK": CasePriority.HIGH, "MEDIUM_RISK": CasePriority.MEDIUM}.get(
            risk_result.level, CasePriority.LOW
        ),
    )

    log_event(db, verification_record.id, "CREATED", _user.id, case_id=case.id)

    if embedding_record is not None:
        set_embedding_case_id(db, embedding_record, case.id)
    _update_network_graph(
        db, case=case, name=name_for_lookup, document_number=document_number_for_lookup,
        nationality=payload.nationality, identity_graph_result=identity_graph_result,
    )

    # No image ever reached the server to hash — the submitted encoded
    # payload itself (fields + MRZ text + embeddings) is what's attested
    # instead.
    payload_hash = hashlib.sha256(
        payload.model_dump_json(
            exclude={"tampering_result", "deepfake_result", "liveness_result", "face_detection_result"}
        ).encode()
    ).hexdigest()
    blockchain_service.create_verification_record(
        verification_id=str(verification_record.id),
        document_hash=payload_hash,
        issuer_reference=str(_user.id),
        event_type="SCREENING_CREATED",
    )

    return ScreeningResponse(
        verification_id=str(verification_record.id),
        case_id=str(case.id),
        case_number=case.case_number,
        case_status=case.status.value,
        risk=risk_result,
        ocr=ocr_result,
        validation=validation_result,
        tampering=tampering_result,
        deepfake=deepfake_result,
        registry=registry_result,
        face=face_result,
        identity_graph=identity_graph_result,
        liveness=liveness_result,
        duplicate_document=duplicate_document_result,
        face_detection=face_detection_result,
        citizen_registry=citizen_registry_result,
    )


@router.post(
    "/screen-with-images",
    response_model=ScreeningResponse,
    summary="Full screening pipeline with image uploads for web dashboard review",
)
async def screen_document_with_images(
    screening_data: str = Form(..., description="JSON-encoded ScreeningSubmission data"),
    document_front: UploadFile = File(..., description="Front side of document"),
    document_back: UploadFile = File(None, description="Back side of document (optional)"),
    selfie: UploadFile = File(..., description="Live selfie capture"),
    _user: User = Depends(get_current_user),
    validation_engine: ValidationEngine = Depends(get_validation_engine),
    risk_engine: RiskEngine = Depends(get_risk_engine),
    blockchain_service: BlockchainService = Depends(get_blockchain_service),
    db: Session = Depends(get_db),
) -> ScreeningResponse:
    # Parse the screening data from form field
    try:
        payload_data = json.loads(screening_data)
        payload = ScreeningSubmission(**payload_data)
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid screening data JSON: {e}"
        )

    # Process the screening data (same logic as the original screen endpoint)
    if not payload.ocr_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ocr_fields is empty — on-device OCR must run before a screening is submitted",
        )

    # Run the same screening logic as the original endpoint
    # (I'll abbreviate this for space, but it would include all the same logic)
    ocr_result = OCRResult(
        document_type=payload.document_type.value, fields=payload.ocr_fields, ocr_confidence=payload.ocr_confidence
    )

    # ... (same validation, registry, face matching, etc. logic as above)
    # For brevity, I'll call the original screen function and then save images

    # First run the standard screening without images
    screen_response = screen_document(payload, _user, validation_engine, risk_engine, blockchain_service, db)

    # Now save the uploaded images
    settings = get_settings()
    images_dir = Path(getattr(settings, 'images_dir', 'images'))
    images_dir.mkdir(exist_ok=True)

    verification_id = screen_response.verification_id

    # Save document front image
    if document_front:
        front_path = images_dir / f"{verification_id}.jpg"
        with open(front_path, "wb") as buffer:
            shutil.copyfileobj(document_front.file, buffer)

    # Save document back image if provided
    if document_back:
        back_path = images_dir / f"{verification_id}_back.jpg"
        with open(back_path, "wb") as buffer:
            shutil.copyfileobj(document_back.file, buffer)

    # Save selfie image
    if selfie:
        selfie_path = images_dir / f"{verification_id}_selfie.jpg"
        with open(selfie_path, "wb") as buffer:
            shutil.copyfileobj(selfie.file, buffer)

    return screen_response
