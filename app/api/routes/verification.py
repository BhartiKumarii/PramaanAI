"""Verification record retrieval, audit trail, and the dispute/clear
workflow. GET re-verifies the HMAC signature on every read — a tampered
row is flagged explicitly (`signature_valid: false`), never silently
trusted. Dispute requires a reason and is logged, never a silent clear.
"""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.audit_repository import list_events_with_actor, log_event
from app.repositories.verification_repository import get_verification, list_verifications, verify_signature
from app.schemas.audit import AuditEventResponse, DisputeRequest
from app.schemas.verification import VerificationListItemResponse, VerificationRecordResponse
from app.services.deepfake.base import DeepfakeResult
from app.services.face.base import FaceMatchResult
from app.services.identity_graph.base import IdentityGraphResult
from app.services.liveness.base import LivenessResult
from app.services.ocr.base import OCRResult
from app.services.registry.base import RegistryLookupResult
from app.services.risk.base import RiskResult, RiskSignalBreakdown
from app.services.tampering.base import TamperingResult
from app.services.validation.base import ValidationResult


def _load(model_cls, raw_json: str | None):
    return model_cls.model_validate_json(raw_json) if raw_json else None

router = APIRouter(prefix="/verification", tags=["verification"])


def _get_or_404(db: Session, verification_id: uuid.UUID):
    record = get_verification(db, verification_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="verification record not found")
    return record


@router.get(
    "/{verification_id}",
    response_model=VerificationRecordResponse,
    summary="Retrieve a stored screening result, verifying its HMAC signature",
)
def get_verification_record(
    verification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VerificationRecordResponse:
    record = _get_or_404(db, verification_id)
    log_event(db, verification_id, "VIEWED", user.id)

    signature_valid = verify_signature(record)
    breakdown = [RiskSignalBreakdown(**item) for item in json.loads(record.breakdown_json)]
    risk = RiskResult(
        score=record.score,
        level=record.level,
        decision=record.decision,
        top_reason=record.top_reason,
        breakdown=breakdown,
    )

    return VerificationRecordResponse(
        id=str(record.id),
        document_type=record.document_type,
        nationality=record.nationality,
        traveler_name=record.traveler_name,
        risk=risk,
        signature_valid=signature_valid,
        created_at=record.created_at.isoformat(),
        ocr=_load(OCRResult, record.ocr_json),
        validation=_load(ValidationResult, record.validation_json),
        tampering=_load(TamperingResult, record.tampering_json),
        deepfake=_load(DeepfakeResult, record.deepfake_json),
        registry=_load(RegistryLookupResult, record.registry_json),
        face=_load(FaceMatchResult, record.face_json),
        identity_graph=_load(IdentityGraphResult, record.identity_graph_json),
        liveness=_load(LivenessResult, record.liveness_json),
    )


@router.get(
    "",
    response_model=list[VerificationListItemResponse],
    summary="Most recent screenings, each with a real status derived from its own audit trail",
)
def list_verification_records(
    limit: int = 50,
    offset: int = 0,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[VerificationListItemResponse]:
    limit = max(1, min(limit, 200))
    rows = list_verifications(db, limit=limit, offset=offset)
    return [
        VerificationListItemResponse(
            id=str(record.id),
            document_type=record.document_type,
            nationality=record.nationality,
            traveler_name=record.traveler_name,
            score=record.score,
            level=record.level,
            decision=record.decision,
            status=derived_status,
            created_at=record.created_at.isoformat(),
        )
        for record, derived_status in rows
    ]


@router.get(
    "/{verification_id}/audit",
    response_model=list[AuditEventResponse],
    summary="Full lifecycle audit trail for a verification (created, viewed, disputed, cleared)",
)
def get_audit_trail(
    verification_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AuditEventResponse]:
    _get_or_404(db, verification_id)
    events = list_events_with_actor(db, verification_id)
    return [
        AuditEventResponse(
            id=str(event.id),
            event_type=event.event_type,
            actor_user_id=str(event.actor_user_id),
            actor_username=username,
            reason=event.reason,
            created_at=event.created_at.isoformat(),
        )
        for event, username in events
    ]


@router.post(
    "/{verification_id}/dispute",
    response_model=AuditEventResponse,
    summary="Flag a verification for secondary inspection — a reason is required and logged",
)
def dispute_verification(
    verification_id: uuid.UUID,
    payload: DisputeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditEventResponse:
    _get_or_404(db, verification_id)
    event = log_event(db, verification_id, "DISPUTED", user.id, reason=payload.reason)
    return AuditEventResponse(
        id=str(event.id),
        event_type=event.event_type,
        actor_user_id=str(event.actor_user_id),
        reason=event.reason,
        created_at=event.created_at.isoformat(),
    )


@router.post(
    "/{verification_id}/clear",
    response_model=AuditEventResponse,
    summary="Officer accepts the screening result after review — logged, never silent",
)
def clear_verification(
    verification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditEventResponse:
    _get_or_404(db, verification_id)
    event = log_event(db, verification_id, "CLEARED", user.id)
    return AuditEventResponse(
        id=str(event.id),
        event_type=event.event_type,
        actor_user_id=str(event.actor_user_id),
        reason=event.reason,
        created_at=event.created_at.isoformat(),
    )
