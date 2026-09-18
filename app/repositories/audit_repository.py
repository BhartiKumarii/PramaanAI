import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.case import Case
from app.models.user import User


def log_event(
    db: Session,
    verification_id: uuid.UUID | None,
    event_type: str,
    actor_user_id: uuid.UUID,
    reason: str | None = None,
    case_id: uuid.UUID | None = None,
) -> AuditEvent:
    event = AuditEvent(
        verification_id=verification_id,
        case_id=case_id,
        event_type=event_type,
        actor_user_id=actor_user_id,
        reason=reason,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_events(db: Session, verification_id: uuid.UUID) -> list[AuditEvent]:
    return list(
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.verification_id == verification_id)
            .order_by(AuditEvent.created_at)
        ).scalars()
    )


def list_events_with_actor(db: Session, verification_id: uuid.UUID) -> list[tuple[AuditEvent, str | None]]:
    """Same events as list_events, paired with the real acting officer's
    username (via a join on users) — None only if that user was since
    deleted, never a placeholder name."""
    rows = db.execute(
        select(AuditEvent, User.username)
        .join(User, User.id == AuditEvent.actor_user_id, isouter=True)
        .where(AuditEvent.verification_id == verification_id)
        .order_by(AuditEvent.created_at)
    ).all()
    return [(row[0], row[1]) for row in rows]


def list_case_events_with_actor(db: Session, case_id: uuid.UUID) -> list[tuple[AuditEvent, str | None]]:
    """Same as list_events_with_actor, filtered by case_id instead —
    covers case-lifecycle events (SENT, DECISION_*) logged without a
    verification_id."""
    rows = db.execute(
        select(AuditEvent, User.username)
        .join(User, User.id == AuditEvent.actor_user_id, isouter=True)
        .where(AuditEvent.case_id == case_id)
        .order_by(AuditEvent.created_at)
    ).all()
    return [(row[0], row[1]) for row in rows]


def list_all_events(
    db: Session, *, limit: int = 100, offset: int = 0
) -> list[tuple[AuditEvent, str | None, str | None, str | None]]:
    """System-wide audit log (Admin/IT only — see /audit-logs). Each row
    pairs the real event with the real acting officer's username+role and
    the real case number it belongs to, if any — never a placeholder for
    a field that isn't actually resolvable."""
    rows = db.execute(
        select(AuditEvent, User.username, User.role, Case.case_number)
        .join(User, User.id == AuditEvent.actor_user_id, isouter=True)
        .join(Case, Case.id == AuditEvent.case_id, isouter=True)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [(row[0], row[1], row[2].value if row[2] else None, row[3]) for row in rows]
