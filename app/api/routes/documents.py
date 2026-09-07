"""Document OCR / validation / tampering / screening endpoints.

/documents/ocr (Module 1), /documents/validate (Module 2),
/documents/tampering (Module 3), and the orchestrating /documents/screen
(Module 7) are implemented.
"""
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

import hashlib

from app.api.deps import (
    get_blockchain_service,
    get_deepfake_provider,
    get_face_provider,
    get_liveness_provider,
    get_ocr_provider,
    get_risk_engine,
    get_tampering_provider,
    get_validation_engine,
)
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.audit_repository import log_event
from app.repositories.identity_embedding_repository import insert_embedding, list_all
from app.repositories.verification_repository import create_verification
from app.schemas.document import DocumentType
from app.schemas.verification import ScreeningResponse
from app.services.blockchain.base import BlockchainService
from app.services.deepfake.base import DeepfakeProvider, DeepfakeResult
from app.services.face.base import FaceMatchResult, FaceProvider
from app.services.face.embedding import extract_embedding
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
    summary="Full screening pipeline: OCR, validation, forensics, deepfake, blacklist, "
    "face match, identity graph, and risk fusion — persists a signed result",
)
async def screen_document(
    document_type: DocumentType = Form(...),
    nationality: str = Form(...),
    front_image: UploadFile = File(...),
    back_image: UploadFile | None = File(None),
    live_capture: UploadFile | None = File(None),
    aadhaar_number: str | None = Form(None),
    _user: User = Depends(get_current_user),
    ocr_provider: OCRProvider = Depends(get_ocr_provider),
    validation_engine: ValidationEngine = Depends(get_validation_engine),
    tampering_provider: TamperingProvider = Depends(get_tampering_provider),
    face_provider: FaceProvider = Depends(get_face_provider),
    deepfake_provider: DeepfakeProvider = Depends(get_deepfake_provider),
    liveness_provider: LivenessProvider = Depends(get_liveness_provider),
    risk_engine: RiskEngine = Depends(get_risk_engine),
    blockchain_service: BlockchainService = Depends(get_blockchain_service),
    db: Session = Depends(get_db),
) -> ScreeningResponse:
    front_bytes = await front_image.read()
    if not front_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty front_image upload")
    front_bytes = downscale_image_bytes(front_bytes)

    ocr_result = ocr_provider.extract(front_bytes, document_type.value)

    mrz_result = None
    if back_image is not None:
        back_bytes = await back_image.read()
        if back_bytes:
            back_bytes = downscale_image_bytes(back_bytes)
            try:
                lines = extract_mrz_lines(extract_mrz_text(back_bytes))
                if lines is not None:
                    mrz_result = parse_td3(*lines)
            except MRZFormatError:
                mrz_result = None  # a real but unreadable back image shouldn't abort the whole screening

    validation_result: ValidationResult = validation_engine.validate(
        ocr_result=ocr_result.fields,
        mrz_result=mrz_result,
        nationality=nationality,
        aadhaar_number=aadhaar_number,
    )
    tampering_result: TamperingResult = tampering_provider.analyze(front_bytes)

    name_for_lookup = ocr_result.fields.get("name")
    document_number_for_lookup = ocr_result.fields.get("passport_number") or aadhaar_number
    registry_result: RegistryLookupResult = lookup_registry(db, document_number_for_lookup, name_for_lookup)

    face_result: FaceMatchResult | None = None
    identity_graph_result: IdentityGraphResult | None = None
    liveness_result: LivenessResult | None = None
    deepfake_result: DeepfakeResult
    if live_capture is not None:
        live_bytes = await live_capture.read()
        if live_bytes:
            live_bytes = downscale_image_bytes(live_bytes)
            face_result = face_provider.verify(front_bytes, live_bytes)
            embedding = extract_embedding(live_bytes)
            record = insert_embedding(
                db, name_for_lookup or "UNKNOWN", document_number_for_lookup, embedding
            )
            graph = build_graph(list_all(db))
            identity_graph_result = find_multi_identity_cluster(graph, str(record.id))
            liveness_result = liveness_provider.analyze(live_bytes)
            # Deepfake detection targets the live capture (the thing that
            # would actually be AI-generated in a spoofing attempt), not
            # the static document photo.
            deepfake_result = deepfake_provider.analyze(live_bytes)
        else:
            deepfake_result = deepfake_provider.analyze(front_bytes)
    else:
        deepfake_result = deepfake_provider.analyze(front_bytes)

    risk_result = risk_engine.score(
        validation_result=validation_result,
        tampering_result=tampering_result,
        deepfake_result=deepfake_result,
        registry_result=registry_result,
        face_result=face_result,
        identity_graph_result=identity_graph_result,
        liveness_result=liveness_result,
    )

    verification_record = create_verification(
        db,
        document_type.value,
        nationality,
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
    )
    log_event(db, verification_record.id, "CREATED", _user.id)
    blockchain_service.create_verification_record(
        verification_id=str(verification_record.id),
        document_hash=hashlib.sha256(front_bytes).hexdigest(),
        issuer_reference=str(_user.id),
        event_type="SCREENING_CREATED",
    )

    return ScreeningResponse(
        verification_id=str(verification_record.id),
        risk=risk_result,
        ocr=ocr_result,
        validation=validation_result,
        tampering=tampering_result,
        deepfake=deepfake_result,
        registry=registry_result,
        face=face_result,
        identity_graph=identity_graph_result,
        liveness=liveness_result,
    )
