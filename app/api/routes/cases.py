"""Case workflow:
  Officer (OFFICER role) scans → Case created → submitted for review.
  Reviewer (REVIEWER role) → reviews evidence → makes final decision.

Every state change is logged via AuditEvent so nothing is silently changed."""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_role
from app.db.session import get_db
from app.models.case import Case, CasePriority, CaseStatus
from app.models.checkpoint import Checkpoint
from app.models.user import User, UserRole
from app.repositories.audit_repository import list_case_events_with_actor, log_event
from app.repositories.case_repository import (
    add_note,
    assign_case,
    get_case,
    list_cases,
    list_decisions,
    list_notes,
    record_decision,
    submit_case,
)
from app.repositories.identity_embedding_repository import get_by_case_id, get_embedding, list_all
from app.repositories.verification_repository import get_verification, verify_signature
from app.schemas.audit import AuditEventResponse
from app.schemas.case import (
    CaseAssignRequest,
    CaseDecisionRequest,
    CaseDecisionSummary,
    CaseDetailResponse,
    CaseListItemResponse,
    CaseNoteRequest,
    CaseNoteResponse,
    CaseSubmitRequest,
    CaseTimelineEvent,
)
from app.schemas.network import IdentityHistoryRecord
from app.schemas.verification import VerificationRecordResponse
from app.services.identity_graph.graph import build_graph, find_multi_identity_cluster
from app.utils.masking import mask_document_number
from app.services.citizen_registry.base import CitizenRegistryResult
from app.services.deepfake.base import DeepfakeResult
from app.services.duplicate.base import DuplicateDocumentResult
from app.services.face.base import FaceDetectionResult, FaceMatchResult
from app.services.identity_graph.base import IdentityGraphResult
from app.services.liveness.base import LivenessResult
from app.services.ocr.base import OCRResult
from app.services.registry.base import RegistryLookupResult
from app.services.risk.base import RiskResult, RiskSignalBreakdown
from app.services.tampering.base import TamperingResult
from app.services.validation.base import ValidationResult

router = APIRouter(prefix="/cases", tags=["cases"])


def _get_case_or_404(db: Session, case_id: uuid.UUID, user: User) -> Case:
    case = get_case(db, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
    return case


def _serialize_list(db: Session, cases: list[Case]) -> list[CaseListItemResponse]:
    if not cases:
        return []
    # Case model stores Uuid; Checkpoint/User models use String(36) PKs — convert before .in_()
    checkpoint_ids = {str(c.checkpoint_id) for c in cases}
    user_ids = {str(c.field_officer_id) for c in cases} | {str(c.assigned_officer_id) for c in cases if c.assigned_officer_id}
    verification_ids = {c.verification_id for c in cases if c.verification_id}
    checkpoints = {cp.id: cp for cp in db.query(Checkpoint).filter(Checkpoint.id.in_(checkpoint_ids))}
    users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids))}
    from app.models.verification import VerificationRecord
    verifications = (
        {str(v.id): v for v in db.query(VerificationRecord).filter(VerificationRecord.id.in_(verification_ids))}
        if verification_ids else {}
    )

    def _risk(c: Case, attr: str):
        if not c.verification_id:
            return None
        v = verifications.get(str(c.verification_id))
        return getattr(v, attr, None) if v else None

    return [
        CaseListItemResponse(
            id=str(c.id),
            case_number=c.case_number,
            status=c.status.value,
            priority=c.priority.value,
            checkpoint_code=checkpoints[str(c.checkpoint_id)].code if str(c.checkpoint_id) in checkpoints else "—",
            field_officer_username=users[str(c.field_officer_id)].username if str(c.field_officer_id) in users else "—",
            assigned_officer_username=(
                users[str(c.assigned_officer_id)].username
                if c.assigned_officer_id and str(c.assigned_officer_id) in users
                else None
            ),
            document_type=c.document_type,
            nationality=c.nationality,
            traveler_name=c.traveler_name,
            created_at=c.created_at.isoformat(),
            sent_at=c.sent_at.isoformat() if c.sent_at else None,
            risk_level=_risk(c, "level"),
            risk_score=_risk(c, "score"),
        )
        for c in cases
    ]


def _load(model_cls, raw_json: str | None):
    return model_cls.model_validate_json(raw_json) if raw_json else None


def _verification_response(record) -> VerificationRecordResponse:
    breakdown = [RiskSignalBreakdown(**item) for item in json.loads(record.breakdown_json)]
    risk = RiskResult(
        score=record.score, level=record.level, decision=record.decision,
        top_reason=record.top_reason, breakdown=breakdown,
    )
    return VerificationRecordResponse(
        id=str(record.id), document_type=record.document_type, nationality=record.nationality,
        traveler_name=record.traveler_name, risk=risk, signature_valid=verify_signature(record),
        created_at=record.created_at.isoformat(),
        ocr=_load(OCRResult, record.ocr_json), validation=_load(ValidationResult, record.validation_json),
        tampering=_load(TamperingResult, record.tampering_json), deepfake=_load(DeepfakeResult, record.deepfake_json),
        registry=_load(RegistryLookupResult, record.registry_json), face=_load(FaceMatchResult, record.face_json),
        identity_graph=_load(IdentityGraphResult, record.identity_graph_json),
        liveness=_load(LivenessResult, record.liveness_json),
        duplicate_document=_load(DuplicateDocumentResult, record.duplicate_document_json),
        face_detection=_load(FaceDetectionResult, record.face_detection_json),
        citizen_registry=_load(CitizenRegistryResult, record.citizen_registry_json),
    )


@router.get("", response_model=list[CaseListItemResponse], summary="List cases, scoped to the caller's role")
def list_cases_route(
    status_filter: CaseStatus | None = None,
    checkpoint_id: uuid.UUID | None = None,
    priority: CasePriority | None = None,
    source_officer_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CaseListItemResponse]:
    limit = max(1, min(limit, 200))
    cases = list_cases(
        db, requester=user, status_filter=status_filter, checkpoint_id=checkpoint_id,
        priority=priority, source_officer_id=source_officer_id, limit=limit, offset=offset,
    )
    return _serialize_list(db, cases)


@router.get("/{case_id}", response_model=CaseDetailResponse, summary="Full case detail: evidence, notes, decision history")
def get_case_route(case_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CaseDetailResponse:
    case = _get_case_or_404(db, case_id, user)
    log_event(db, case.verification_id, "VIEWED", user.id, case_id=case.id)

    [summary] = _serialize_list(db, [case])
    verification = None
    if case.verification_id:
        record = get_verification(db, case.verification_id)
        if record is not None:
            verification = _verification_response(record)

    notes = [
        CaseNoteResponse(id=str(n.id), author_username=username, note=n.note, created_at=n.created_at.isoformat())
        for n, username in list_notes(db, case_id)
    ]
    decisions_rows = list_decisions(db, case_id)
    officer_ids = {d.officer_id for d in decisions_rows}
    officers = {u.id: u for u in db.query(User).filter(User.id.in_(officer_ids))} if officer_ids else {}
    decisions = [
        CaseDecisionSummary(
            decision=d.decision,
            officer_username=officers[d.officer_id].username if d.officer_id in officers else None,
            reason=d.reason,
            created_at=d.created_at.isoformat(),
        )
        for d in decisions_rows
    ]

    return CaseDetailResponse(
        **summary.model_dump(),
        verification=verification,
        notes=notes,
        decisions=decisions,
        decided_at=case.decided_at.isoformat() if case.decided_at else None,
    )


@router.post("/{case_id}/submit", response_model=CaseListItemResponse, summary="Officer forwards a case for review")
def submit_case_route(
    case_id: uuid.UUID, payload: CaseSubmitRequest,
    user: User = Depends(require_role()),
    db: Session = Depends(get_db),
) -> CaseListItemResponse:
    case = _get_case_or_404(db, case_id, user)
    if case.status not in (CaseStatus.PENDING, CaseStatus.REVIEW_REQUIRED):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"case is already {case.status.value}, cannot resubmit")
    if payload.note:
        add_note(db, case_id, uuid.UUID(user.id), payload.note)
    case = submit_case(db, case)
    log_event(db, case.verification_id, "SENT", user.id, case_id=case.id)
    [summary] = _serialize_list(db, [case])
    return summary


@router.patch("/{case_id}", response_model=CaseListItemResponse, summary="Assign an officer and/or set priority")
def assign_case_route(
    case_id: uuid.UUID, payload: CaseAssignRequest,
    user: User = Depends(require_role()),
    db: Session = Depends(get_db),
) -> CaseListItemResponse:
    case = _get_case_or_404(db, case_id, user)
    officer_uuid = uuid.UUID(payload.officer_id) if payload.officer_id else None
    priority = CasePriority(payload.priority) if payload.priority else None
    case = assign_case(db, case, officer_id=officer_uuid, priority=priority)
    [summary] = _serialize_list(db, [case])
    return summary


@router.post("/{case_id}/decision", response_model=CaseDetailResponse, summary="Record the authorised final decision (REVIEWER role required)")
def decide_case_route(
    case_id: uuid.UUID, payload: CaseDecisionRequest,
    user: User = Depends(require_role(UserRole.REVIEWER)),
    db: Session = Depends(get_db),
) -> CaseDetailResponse:
    case = _get_case_or_404(db, case_id, user)
    if case.status not in (CaseStatus.SENT, CaseStatus.REVIEW_REQUIRED):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"case is {case.status.value}, not awaiting a decision")
    if payload.decision != "CLEAR" and not payload.reason:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="reason is required for Secondary Review and Hold/Refer")

    case, _decision = record_decision(db, case, uuid.UUID(user.id), payload.decision, payload.reason)
    log_event(db, case.verification_id, f"DECISION_{payload.decision}", user.id, reason=payload.reason, case_id=case.id)
    return get_case_route(case_id, user, db)


@router.post("/{case_id}/notes", response_model=CaseNoteResponse, summary="Add a note to a case's permanent record")
def add_note_route(
    case_id: uuid.UUID, payload: CaseNoteRequest,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> CaseNoteResponse:
    _get_case_or_404(db, case_id, user)
    note = add_note(db, case_id, uuid.UUID(user.id), payload.note)
    return CaseNoteResponse(id=str(note.id), author_username=user.username, note=note.note, created_at=note.created_at.isoformat())


@router.get("/{case_id}/audit", response_model=list[AuditEventResponse], summary="Full lifecycle audit trail for a case")
def get_case_audit_route(case_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[AuditEventResponse]:
    case = _get_case_or_404(db, case_id, user)
    events = list_case_events_with_actor(db, case.id)
    return [
        AuditEventResponse(
            id=str(e.id), event_type=e.event_type, actor_user_id=str(e.actor_user_id),
            actor_username=username, reason=e.reason, created_at=e.created_at.isoformat(),
        )
        for e, username in events
    ]


@router.get(
    "/{case_id}/identity-history",
    response_model=list[IdentityHistoryRecord],
    summary="Other cases whose live-capture face matches this case's, via the same real cluster detection used during screening",
)
def get_case_identity_history_route(
    case_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[IdentityHistoryRecord]:
    case = _get_case_or_404(db, case_id, user)
    embedding = get_by_case_id(db, case_id)
    if embedding is None:
        # No live capture was taken during this case's screening, so
        # there's nothing to compare — an honest empty result, not a
        # fabricated "no history" claim.
        return []

    graph = build_graph(list_all(db))
    cluster = find_multi_identity_cluster(graph, str(embedding.id))

    records: list[IdentityHistoryRecord] = []
    for member in cluster.members:
        if member.record_id == str(embedding.id):
            continue
        similarity = None
        if graph.has_edge(str(embedding.id), member.record_id):
            similarity = graph.edges[str(embedding.id), member.record_id]["similarity"]

        member_embedding = get_embedding(db, uuid.UUID(member.record_id))
        related_case = (
            get_case(db, member_embedding.case_id)
            if member_embedding is not None and member_embedding.case_id is not None
            else None
        )
        checkpoint = db.get(Checkpoint, str(related_case.checkpoint_id)) if related_case is not None else None

        records.append(
            IdentityHistoryRecord(
                record_id=member.record_id,
                case_id=str(related_case.id) if related_case else None,
                case_number=related_case.case_number if related_case else None,
                checkpoint_code=checkpoint.code if checkpoint else None,
                declared_name=member.reference_name,
                masked_document_number=mask_document_number(member.document_number) if member.document_number else None,
                occurred_at=related_case.created_at.isoformat() if related_case else None,
                similarity=similarity,
                review_status=related_case.status.value if related_case else None,
            )
        )
    return records


_EVENT_ACTION_LABELS = {
    "CREATED": "Document scanned — OCR, validation, forensics, and (where a live capture was taken) "
    "face matching, liveness, and identity-graph analysis all completed",
    "VIEWED": "Case opened for review",
    "SENT": "Case submitted for admin review by field officer",
    "DECISION_CLEAR": "Admin decision: Identity Verified",
    "DECISION_SECONDARY_REVIEW": "Admin decision: Re-capture Requested",
    "DECISION_HOLD_REFER": "Admin decision: Referred for Manual Verification",
    "NOTE_ADDED": "Note added",
}


@router.get(
    "/{case_id}/timeline",
    response_model=list[CaseTimelineEvent],
    summary="Chronological case history — every real logged event, oldest first",
)
def get_case_timeline_route(
    case_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[CaseTimelineEvent]:
    case = _get_case_or_404(db, case_id, user)

    events = [
        CaseTimelineEvent(
            event_type=e.event_type,
            action=_EVENT_ACTION_LABELS.get(e.event_type, e.event_type),
            actor_username=username,
            detail=e.reason,
            created_at=e.created_at.isoformat(),
        )
        for e, username in list_case_events_with_actor(db, case.id)
    ]
    events.extend(
        CaseTimelineEvent(
            event_type="NOTE_ADDED",
            action=_EVENT_ACTION_LABELS["NOTE_ADDED"],
            actor_username=username,
            detail=note.note,
            created_at=note.created_at.isoformat(),
        )
        for note, username in list_notes(db, case.id)
    )
    events.sort(key=lambda e: e.created_at)
    return events
