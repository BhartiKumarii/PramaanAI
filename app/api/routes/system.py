from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.models.case import SyncQueueItem
from app.models.user import User
from app.schemas.system import RiskConfigResponse, SyncStatusResponse, SystemHealthResponse
from app.services.risk.engine import active_risk_config

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health", response_model=SystemHealthResponse, summary="Real component health")
def get_system_health(
    _user: User = Depends(require_role()), db: Session = Depends(get_db)
) -> SystemHealthResponse:
    try:
        db.execute(text("SELECT 1"))
        database_status = "ok"
    except Exception:
        database_status = "unreachable"

    return SystemHealthResponse(
        api_status="ok",
        database_status=database_status,
        analysis_pipeline_status="ok (in-process with the API — no separate service to monitor)",
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/sync-status", response_model=SyncStatusResponse, summary="Offline sync queue depth")
def get_sync_status(
    _user: User = Depends(require_role()), db: Session = Depends(get_db)
) -> SyncStatusResponse:
    counts = {
        row[0]: row[1]
        for row in db.execute(select(SyncQueueItem.status, func.count()).group_by(SyncQueueItem.status)).all()
    }
    last_sync = db.execute(
        select(func.max(SyncQueueItem.synced_at)).where(SyncQueueItem.status == "SYNCED")
    ).scalar_one()

    return SyncStatusResponse(
        pending=counts.get("PENDING", 0),
        synced=counts.get("SYNCED", 0),
        failed=counts.get("FAILED", 0),
        last_successful_sync_at=last_sync.isoformat() if last_sync else None,
    )


@router.get(
    "/risk-config",
    response_model=RiskConfigResponse,
    summary="Real active risk-scoring weights and thresholds — read-only",
)
def get_risk_config(_user: User = Depends(require_role())) -> RiskConfigResponse:
    return RiskConfigResponse(**active_risk_config())