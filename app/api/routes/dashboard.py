from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.models.user import User
from app.repositories.dashboard_repository import (
    admin_dashboard,
    analytics_dashboard,
    immigration_dashboard,
    supervisor_dashboard,
)
from app.schemas.dashboard import (
    AdminDashboardResponse,
    AnalyticsDashboardResponse,
    ImmigrationDashboardResponse,
    SupervisorDashboardResponse,
    UnifiedDashboardResponse,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/unified",
    response_model=UnifiedDashboardResponse,
    summary="Unified dashboard with all stats for officers",
)
def get_unified_dashboard(
    user: User = Depends(require_role()),
    db: Session = Depends(get_db),
) -> UnifiedDashboardResponse:
    imm = immigration_dashboard(db, user.checkpoint_id)
    sup = supervisor_dashboard(db)
    adm = admin_dashboard(db)
    ana = analytics_dashboard(db, days=14)
    return UnifiedDashboardResponse(
        new_cases=imm["new_cases"],
        pending_review=imm["pending_review"],
        high_priority=imm["high_priority"],
        cleared_cases=imm["cleared_cases"],
        total_scans=sup["total_scans"],
        pending_cases=sup["pending_cases"],
        review_required=sup["review_required"],
        high_priority_supervisor=sup["high_priority_supervisor"],
        active_officers=sup["active_officers"],
        avg_processing_time_seconds=sup["avg_processing_time_seconds"],
        offline_sync_queue=sup["offline_sync_queue"],
        checkpoint_breakdown=sup["checkpoint_breakdown"],
        registered_users=adm["registered_users"],
        registered_devices=adm["registered_devices"],
        sync_queue_pending=adm["sync_queue_pending"],
        total_screenings=ana["total_screenings"],
        by_document_type=ana["by_document_type"],
        by_decision=ana["by_decision"],
        by_risk_level=ana["by_risk_level"],
        by_day=ana["by_day"],
    )


@router.get(
    "/immigration",
    response_model=ImmigrationDashboardResponse,
    summary="Case counts for the caller's own checkpoint",
)
def get_immigration_dashboard(
    user: User = Depends(require_role()),
    db: Session = Depends(get_db),
) -> ImmigrationDashboardResponse:
    return ImmigrationDashboardResponse(**immigration_dashboard(db, user.checkpoint_id))


@router.get(
    "/supervisor",
    response_model=SupervisorDashboardResponse,
    summary="Cross-checkpoint case, workload, and sync-queue statistics",
)
def get_supervisor_dashboard(
    _user: User = Depends(require_role()),
    db: Session = Depends(get_db),
) -> SupervisorDashboardResponse:
    return SupervisorDashboardResponse(**supervisor_dashboard(db))


@router.get(
    "/admin",
    response_model=AdminDashboardResponse,
    summary="Registered users/devices and sync-queue depth",
)
def get_admin_dashboard(
    _user: User = Depends(require_role()),
    db: Session = Depends(get_db),
) -> AdminDashboardResponse:
    return AdminDashboardResponse(**admin_dashboard(db))


@router.get(
    "/analytics",
    response_model=AnalyticsDashboardResponse,
    summary="Screening-history aggregates — backs Document Intelligence and Reports & Analytics",
)
def get_analytics_dashboard(
    days: int = 14,
    _user: User = Depends(require_role()),
    db: Session = Depends(get_db),
) -> AnalyticsDashboardResponse:
    days = max(1, min(days, 90))
    return AnalyticsDashboardResponse(**analytics_dashboard(db, days=days))