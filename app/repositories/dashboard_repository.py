"""Aggregate counts for the three web-console dashboards. Every number
here is a real query result. Anything we don't actually track yet
(active sessions, failed-login counters, ...) is left out of the
response entirely rather than hardcoded — see CLAUDE.md's honesty rule:
an omitted metric is honest, a fabricated one is not."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.case import Case, CaseStatus, SyncQueueItem
from app.models.checkpoint import Checkpoint
from app.models.device import Device
from app.models.user import User, UserRole


def immigration_dashboard(db: Session, checkpoint_id: uuid.UUID | None) -> dict:
    stmt = select(Case)
    if checkpoint_id is not None:
        stmt = stmt.where(Case.checkpoint_id == checkpoint_id)
    cases = list(db.execute(stmt).scalars())

    return {
        "new_cases": sum(1 for c in cases if c.status == CaseStatus.SENT),
        "pending_review": sum(1 for c in cases if c.status in (CaseStatus.SENT, CaseStatus.REVIEW_REQUIRED)),
        "high_priority": sum(1 for c in cases if c.priority.value == "HIGH" and c.status in (CaseStatus.SENT, CaseStatus.REVIEW_REQUIRED)),
        "cleared_cases": sum(1 for c in cases if c.status == CaseStatus.CLEAR),
    }


def supervisor_dashboard(db: Session) -> dict:
    cases = list(db.execute(select(Case)).scalars())
    active_officers = db.execute(
        select(func.count()).select_from(User).where(User.role == UserRole.FIELD_OFFICER, User.is_active.is_(True))
    ).scalar_one()
    sync_queue_pending = db.execute(
        select(func.count()).select_from(SyncQueueItem).where(SyncQueueItem.status == "PENDING")
    ).scalar_one()

    decided = [c for c in cases if c.decided_at is not None]
    avg_processing_seconds = (
        sum((c.decided_at - c.created_at).total_seconds() for c in decided) / len(decided) if decided else None
    )

    by_checkpoint: dict[str, dict] = {}
    checkpoints = {cp.id: cp.code for cp in db.execute(select(Checkpoint)).scalars()}
    for c in cases:
        code = checkpoints.get(c.checkpoint_id, "UNKNOWN")
        bucket = by_checkpoint.setdefault(code, {"checkpoint_code": code, "pending": 0, "cleared": 0, "review_required": 0})
        if c.status in (CaseStatus.PENDING, CaseStatus.PENDING_SYNC, CaseStatus.SENT):
            bucket["pending"] += 1
        elif c.status == CaseStatus.CLEAR:
            bucket["cleared"] += 1
        elif c.status in (CaseStatus.REVIEW_REQUIRED, CaseStatus.SECONDARY_REVIEW, CaseStatus.HOLD_REFER):
            bucket["review_required"] += 1

    return {
        "total_scans": len(cases),
        "pending_cases": sum(1 for c in cases if c.status in (CaseStatus.PENDING, CaseStatus.PENDING_SYNC, CaseStatus.SENT)),
        "review_required": sum(1 for c in cases if c.status in (CaseStatus.REVIEW_REQUIRED, CaseStatus.SECONDARY_REVIEW, CaseStatus.HOLD_REFER)),
        "high_priority": sum(1 for c in cases if c.priority.value == "HIGH"),
        "active_officers": active_officers,
        "avg_processing_time_seconds": avg_processing_seconds,
        "offline_sync_queue": sync_queue_pending,
        "checkpoint_breakdown": list(by_checkpoint.values()),
    }


def admin_dashboard(db: Session) -> dict:
    return {
        "registered_users": db.execute(select(func.count()).select_from(User)).scalar_one(),
        "registered_devices": db.execute(select(func.count()).select_from(Device)).scalar_one(),
        "sync_queue_pending": db.execute(
            select(func.count()).select_from(SyncQueueItem).where(SyncQueueItem.status == "PENDING")
        ).scalar_one(),
    }
