import json
import uuid

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.hmac_signing import sign, verify
from app.models.audit import AuditEvent
from app.models.verification import VerificationRecord
from app.services.risk.base import RiskResult


def _dump(model: BaseModel | None) -> str | None:
    return model.model_dump_json() if model is not None else None


def _canonical_payload(record_id: uuid.UUID, document_type: str, nationality: str, risk_result: RiskResult) -> dict:
    return {
        "id": str(record_id),
        "document_type": document_type,
        "nationality": nationality,
        "score": risk_result.score,
        "level": risk_result.level,
        "decision": risk_result.decision,
        "top_reason": risk_result.top_reason,
        "breakdown": [b.model_dump() for b in risk_result.breakdown],
    }


def create_verification(
    db: Session,
    document_type: str,
    nationality: str,
    risk_result: RiskResult,
    traveler_name: str | None = None,
    ocr_result: BaseModel | None = None,
    validation_result: BaseModel | None = None,
    tampering_result: BaseModel | None = None,
    deepfake_result: BaseModel | None = None,
    registry_result: BaseModel | None = None,
    face_result: BaseModel | None = None,
    identity_graph_result: BaseModel | None = None,
    liveness_result: BaseModel | None = None,
) -> VerificationRecord:
    record_id = uuid.uuid4()
    payload = _canonical_payload(record_id, document_type, nationality, risk_result)
    record = VerificationRecord(
        id=record_id,
        document_type=document_type,
        nationality=nationality,
        traveler_name=traveler_name,
        score=risk_result.score,
        level=risk_result.level,
        decision=risk_result.decision,
        top_reason=risk_result.top_reason,
        breakdown_json=json.dumps(payload["breakdown"]),
        signature=sign(payload),
        ocr_json=_dump(ocr_result),
        validation_json=_dump(validation_result),
        tampering_json=_dump(tampering_result),
        deepfake_json=_dump(deepfake_result),
        registry_json=_dump(registry_result),
        face_json=_dump(face_result),
        identity_graph_json=_dump(identity_graph_result),
        liveness_json=_dump(liveness_result),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_verification(db: Session, verification_id: uuid.UUID) -> VerificationRecord | None:
    return db.get(VerificationRecord, verification_id)


def list_verifications(db: Session, limit: int = 50, offset: int = 0) -> list[tuple[VerificationRecord, str]]:
    """Most recent verifications first, each paired with a real derived
    status: the most recent audit event type for that record if one
    exists (DISPUTED/CLEARED/VIEWED), else PENDING — never a fabricated
    default."""
    records = list(
        db.execute(
            select(VerificationRecord)
            .order_by(VerificationRecord.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).scalars()
    )
    if not records:
        return []

    record_ids = [r.id for r in records]
    latest_events: dict[uuid.UUID, str] = {}
    for event in db.execute(
        select(AuditEvent)
        .where(AuditEvent.verification_id.in_(record_ids))
        .order_by(AuditEvent.created_at.asc())
    ).scalars():
        if event.event_type in ("DISPUTED", "CLEARED"):
            latest_events[event.verification_id] = event.event_type

    return [(record, latest_events.get(record.id, "PENDING")) for record in records]


def verify_signature(record: VerificationRecord) -> bool:
    payload = {
        "id": str(record.id),
        "document_type": record.document_type,
        "nationality": record.nationality,
        "score": record.score,
        "level": record.level,
        "decision": record.decision,
        "top_reason": record.top_reason,
        "breakdown": json.loads(record.breakdown_json),
    }
    return verify(payload, record.signature)
