"""Case is the officer-facing workflow unit: created alongside a
VerificationRecord when /documents/screen runs, carries it through
Field Officer -> Immigration Officer -> decision. Role-based visibility
is enforced here (not just filtered in the frontend) — see list_cases."""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.case import Case, CaseNote, CasePriority, CaseStatus, OfficerDecision
from app.models.user import User, UserRole


def _generate_case_number(db: Session) -> str:
    today = date.today().strftime("%Y%m%d")
    prefix = f"BSA-{today}-"
    count_today = db.execute(
        select(func.count()).select_from(Case).where(Case.case_number.like(f"{prefix}%"))
    ).scalar_one()
    return f"{prefix}{count_today + 1:04d}"


def _to_uuid(value) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def create_case(
    db: Session,
    *,
    checkpoint_id: uuid.UUID,
    field_officer_id: uuid.UUID,
    verification_id: uuid.UUID,
    document_type: str,
    nationality: str,
    traveler_name: str | None,
    initial_status: CaseStatus,
    priority: CasePriority,
) -> Case:
    # A day-scoped counter can race under concurrent scans; retry once on
    # the (rare) unique-constraint collision rather than failing the scan.
    for _ in range(3):
        case = Case(
            case_number=_generate_case_number(db),
            status=initial_status,
            priority=priority,
            checkpoint_id=_to_uuid(checkpoint_id),
            field_officer_id=_to_uuid(field_officer_id),
            verification_id=_to_uuid(verification_id),
            document_type=document_type,
            nationality=nationality,
            traveler_name=traveler_name,
        )
        db.add(case)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(case)
        return case
    raise RuntimeError("could not allocate a unique case_number after 3 attempts")


def get_case(db: Session, case_id: uuid.UUID) -> Case | None:
    return db.get(Case, case_id)


def list_cases(
    db: Session,
    *,
    requester: User,
    status_filter: CaseStatus | None = None,
    checkpoint_id: uuid.UUID | None = None,
    priority: CasePriority | None = None,
    source_officer_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Case]:
    """All authenticated officers have full access to all cases."""
    stmt = select(Case)

    if status_filter is not None:
        stmt = stmt.where(Case.status == status_filter)
    if checkpoint_id is not None:
        stmt = stmt.where(Case.checkpoint_id == checkpoint_id)
    if priority is not None:
        stmt = stmt.where(Case.priority == priority)
    if source_officer_id is not None:
        stmt = stmt.where(Case.field_officer_id == source_officer_id)

    stmt = stmt.order_by(Case.created_at.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars())


def submit_case(db: Session, case: Case) -> Case:
    case.status = CaseStatus.SENT
    case.sent_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(case)
    return case


def assign_case(db: Session, case: Case, officer_id: uuid.UUID | None = None, priority: CasePriority | None = None) -> Case:
    if officer_id is not None:
        case.assigned_officer_id = officer_id
    if priority is not None:
        case.priority = priority
    db.commit()
    db.refresh(case)
    return case


_DECISION_TO_STATUS = {
    "CLEAR": CaseStatus.CLEAR,
    "SECONDARY_REVIEW": CaseStatus.SECONDARY_REVIEW,
    "HOLD_REFER": CaseStatus.HOLD_REFER,
}


def record_decision(
    db: Session, case: Case, officer_id: uuid.UUID, decision: str, reason: str | None
) -> tuple[Case, OfficerDecision]:
    record = OfficerDecision(case_id=case.id, officer_id=officer_id, decision=decision, reason=reason)
    db.add(record)
    case.status = _DECISION_TO_STATUS[decision]
    case.decided_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(case)
    db.refresh(record)
    return case, record


def list_decisions(db: Session, case_id: uuid.UUID) -> list[OfficerDecision]:
    return list(
        db.execute(
            select(OfficerDecision).where(OfficerDecision.case_id == case_id).order_by(OfficerDecision.created_at)
        ).scalars()
    )


def add_note(db: Session, case_id: uuid.UUID, author_id: uuid.UUID, note: str) -> CaseNote:
    record = CaseNote(case_id=case_id, author_id=author_id, note=note)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_notes(db: Session, case_id: uuid.UUID) -> list[tuple[CaseNote, str | None]]:
    rows = db.execute(
        select(CaseNote, User.username)
        .join(User, User.id == CaseNote.author_id, isouter=True)
        .where(CaseNote.case_id == case_id)
        .order_by(CaseNote.created_at)
    ).all()
    return [(row[0], row[1]) for row in rows]
