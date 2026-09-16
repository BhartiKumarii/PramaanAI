"""Self-service device registration — called by the Android app on first
login (Profile screen's "Device registration status"), distinct from
/admin/devices which is IT/Admin's management view of every device."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.device_repository import get_device_by_identifier, register_device, touch_last_active
from app.schemas.admin import DeviceRegisterRequest, DeviceResponse

router = APIRouter(prefix="/devices", tags=["devices"])


def _response(device, officer_username: str) -> DeviceResponse:
    return DeviceResponse(
        id=str(device.id), device_identifier=device.device_identifier, officer_username=officer_username,
        app_version=device.app_version, is_disabled=device.is_disabled,
        last_active_at=device.last_active_at.isoformat() if device.last_active_at else None,
        registered_at=device.registered_at.isoformat(),
    )


@router.post("/register", response_model=DeviceResponse, summary="Register (or re-attest) this device against the logged-in officer")
def register_device_route(
    payload: DeviceRegisterRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> DeviceResponse:
    device = register_device(db, payload.device_identifier, user.id, payload.app_version)
    return _response(device, user.username)


@router.post("/{device_identifier}/heartbeat", response_model=DeviceResponse, summary="Update last-active time for this device")
def heartbeat_route(
    device_identifier: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> DeviceResponse:
    device = get_device_by_identifier(db, device_identifier)
    if device is None:
        device = register_device(db, device_identifier, user.id, app_version=None)
    else:
        device = touch_last_active(db, device)
    return _response(device, user.username)
