"""IT/Admin user and device management. Every route here is IT_ADMIN-only,
enforced server-side (require_role), never just hidden in the frontend."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.models.checkpoint import Checkpoint
from app.models.user import User, UserRole
from app.repositories.device_repository import list_devices, set_device_disabled
from app.repositories.device_repository import get_device as get_device_row
from app.repositories.user_repository import create_user, get_user, list_users, update_user
from app.schemas.admin import (
    CheckpointResponse,
    DeviceResponse,
    DeviceUpdateRequest,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _user_response(db: Session, user: User) -> UserResponse:
    checkpoint = db.get(Checkpoint, user.checkpoint_id) if user.checkpoint_id else None
    return UserResponse(
        id=str(user.id), username=user.username, role=user.role.value,
        checkpoint_code=checkpoint.code if checkpoint else None,
        is_active=user.is_active, created_at=user.created_at.isoformat(),
    )


def _device_response(db: Session, device) -> DeviceResponse:
    officer = db.get(User, device.officer_id)
    return DeviceResponse(
        id=str(device.id), device_identifier=device.device_identifier,
        officer_username=officer.username if officer else None,
        app_version=device.app_version, is_disabled=device.is_disabled,
        last_active_at=device.last_active_at.isoformat() if device.last_active_at else None,
        registered_at=device.registered_at.isoformat(),
    )


@router.get("/users", response_model=list[UserResponse], summary="List all system accounts")
def list_users_route(
    _user: User = Depends(require_role(UserRole.IT_ADMIN)), db: Session = Depends(get_db)
) -> list[UserResponse]:
    return [_user_response(db, u) for u in list_users(db)]


@router.post("/users", response_model=UserResponse, summary="Create a new account")
def create_user_route(
    payload: UserCreateRequest,
    _user: User = Depends(require_role(UserRole.IT_ADMIN)),
    db: Session = Depends(get_db),
) -> UserResponse:
    checkpoint_id = uuid.UUID(payload.checkpoint_id) if payload.checkpoint_id else None
    try:
        user = create_user(db, payload.username, payload.password, UserRole(payload.role), checkpoint_id)
    except Exception as exc:  # unique-username violation, etc.
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"could not create user: {exc}") from exc
    return _user_response(db, user)


@router.patch("/users/{user_id}", response_model=UserResponse, summary="Change role/checkpoint/active state, or reset password")
def update_user_route(
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    _user: User = Depends(require_role(UserRole.IT_ADMIN)),
    db: Session = Depends(get_db),
) -> UserResponse:
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    checkpoint_id = uuid.UUID(payload.checkpoint_id) if payload.checkpoint_id else None
    role = UserRole(payload.role) if payload.role else None
    user = update_user(
        db, user, role=role, checkpoint_id=checkpoint_id, is_active=payload.is_active, new_password=payload.new_password
    )
    return _user_response(db, user)


@router.get("/devices", response_model=list[DeviceResponse], summary="List all registered field devices")
def list_devices_route(
    _user: User = Depends(require_role(UserRole.IT_ADMIN)), db: Session = Depends(get_db)
) -> list[DeviceResponse]:
    return [_device_response(db, d) for d in list_devices(db)]


@router.patch("/devices/{device_id}", response_model=DeviceResponse, summary="Disable (or re-enable) a device, e.g. reported lost")
def update_device_route(
    device_id: uuid.UUID,
    payload: DeviceUpdateRequest,
    _user: User = Depends(require_role(UserRole.IT_ADMIN)),
    db: Session = Depends(get_db),
) -> DeviceResponse:
    device = get_device_row(db, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device not found")
    device = set_device_disabled(db, device, payload.is_disabled)
    return _device_response(db, device)


@router.get("/checkpoints", response_model=list[CheckpointResponse], summary="List all checkpoints (for user/device assignment dropdowns)")
def list_checkpoints_route(
    _user: User = Depends(require_role(UserRole.IT_ADMIN)), db: Session = Depends(get_db)
) -> list[CheckpointResponse]:
    checkpoints = list(db.query(Checkpoint).order_by(Checkpoint.code).all())
    return [
        CheckpointResponse(id=str(c.id), code=c.code, name=c.name, location=c.location, is_active=c.is_active)
        for c in checkpoints
    ]
