"""System-wide audit log — all authenticated officers have access.
Per-case audit trails stay on /cases/{id}/audit, reachable by whoever
can see that case; this endpoint is the cross-case, system-level view."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.models.user import User
from app.repositories.audit_repository import list_all_events
from app.schemas.audit import AuditLogEntry

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=list[AuditLogEntry], summary="System-wide audit log")
def list_audit_logs(
    limit: int = 100,
    offset: int = 0,
    _user: User = Depends(require_role()),
    db: Session = Depends(get_db),
) -> list[AuditLogEntry]:
    limit = max(1, min(limit, 500))
    rows = list_all_events(db, limit=limit, offset=offset)
    return [
        AuditLogEntry(
            id=str(event.id),
            event_type=event.event_type,
            actor_user_id=str(event.actor_user_id),
            actor_username=username,
            actor_role=role,
            case_id=str(event.case_id) if event.case_id else None,
            case_number=case_number,
            reason=event.reason,
            created_at=event.created_at.isoformat(),
        )
        for event, username, role, case_number in rows
    ]