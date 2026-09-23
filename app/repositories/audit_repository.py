import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.case import Case
from app.models.user import User, UserRole


def _to_uuid(value) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def log_event(
    db: Session,
    verification_id: uuid.UUID | None,
    event_type: str,
    actor_user_id: uuid.UUID,
    reason: str | None = None,
    case_id: uuid.UUID | None = None,
) -> AuditEvent:
    event = AuditEvent(
        verification_id=_to_uuid(verification_id),
        case_id=_to_uuid(case_id),
        event_type=event_type,
        actor_user_id=_to_uuid(actor_user_id),
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
    events = list(db.execute(select(AuditEvent).where(AuditEvent.verification_id == verification_id)
                             .order_by(AuditEvent.created_at)).scalars())
    actors = _actors(db, events)
    return [(e, actors.get(e.actor_user_id, (None, None))[0]) for e in events]


def list_case_events_with_actor(db: Session, case_id: uuid.UUID) -> list[tuple[AuditEvent, str | None]]:
    """Same as list_events_with_actor, filtered by case_id instead —
    covers case-lifecycle events (SENT, DECISION_*) logged without a
    verification_id."""
    events = list(db.execute(select(AuditEvent).where(AuditEvent.case_id == case_id)
                             .order_by(AuditEvent.created_at)).scalars())
    actors = _actors(db, events)
    return [(e, actors.get(e.actor_user_id, (None, None))[0]) for e in events]


def list_all_events(
    db: Session, *, limit: int = 100, offset: int = 0
) -> list[tuple[AuditEvent, str | None, str | None, str | None]]:
    """System-wide audit log (Admin/IT only — see /audit-logs). Each row
    pairs the real event with the real acting officer's username+role and
    the real case number it belongs to, if any — never a placeholder for
    a field that isn't actually resolvable."""
    rows = db.execute(
        select(AuditEvent, Case.case_number)
        .join(Case, Case.id == AuditEvent.case_id, isouter=True)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    actors = _actors(db, [r[0] for r in rows])
    out = []
    for event, case_number in rows:
        username, role = actors.get(event.actor_user_id, (None, None))
        out.append((event, username, role.value if role else None, case_number))
    return out


def _actors(db: Session, events: list[AuditEvent]) -> dict[uuid.UUID, tuple[str, UserRole]]:
    """users.id is a hyphenated UUID string while audit_events.actor_user_id
    is a native UUID column (stored as 32 hex chars on SQLite), so a SQL join
    between them silently never matches. Resolve actors by normalised UUID
    instead."""
    ids = {e.actor_user_id for e in events if e.actor_user_id is not None}
    if not ids:
        return {}
    users = db.execute(select(User).where(User.id.in_([str(i) for i in ids]))).scalars()
    return {uuid.UUID(u.id): (u.username, u.role) for u in users}
