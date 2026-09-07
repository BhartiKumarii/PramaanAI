import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.user import User


def log_event(
    db: Session,
    verification_id: uuid.UUID,
    event_type: str,
    actor_user_id: uuid.UUID,
    reason: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        verification_id=verification_id, event_type=event_type, actor_user_id=actor_user_id, reason=reason
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
