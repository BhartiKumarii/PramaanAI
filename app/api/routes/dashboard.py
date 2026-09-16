from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories.dashboard_repository import admin_dashboard, immigration_dashboard, supervisor_dashboard
from app.schemas.dashboard import AdminDashboardResponse, ImmigrationDashboardResponse, SupervisorDashboardResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/immigration",
    response_model=ImmigrationDashboardResponse,
    summary="Case counts for the caller's own checkpoint",
)
def get_immigration_dashboard(
    user: User = Depends(require_role(UserRole.IMMIGRATION_OFFICER, UserRole.SUPERVISOR)),
    db: Session = Depends(get_db),
) -> ImmigrationDashboardResponse:
    return ImmigrationDashboardResponse(**immigration_dashboard(db, user.checkpoint_id))


@router.get(
    "/supervisor",
    response_model=SupervisorDashboardResponse,
    summary="Cross-checkpoint case, workload, and sync-queue statistics",
)
def get_supervisor_dashboard(
    _user: User = Depends(require_role(UserRole.SUPERVISOR)),
    db: Session = Depends(get_db),
) -> SupervisorDashboardResponse:
    return SupervisorDashboardResponse(**supervisor_dashboard(db))


@router.get(
    "/admin",
    response_model=AdminDashboardResponse,
    summary="Registered users/devices and sync-queue depth",
)
def get_admin_dashboard(
    _user: User = Depends(require_role(UserRole.IT_ADMIN)),
    db: Session = Depends(get_db),
) -> AdminDashboardResponse:
    return AdminDashboardResponse(**admin_dashboard(db))
