import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device import Device


def get_device_by_identifier(db: Session, device_identifier: str) -> Device | None:
    return db.execute(select(Device).where(Device.device_identifier == device_identifier)).scalar_one_or_none()


def register_device(db: Session, device_identifier: str, officer_id: uuid.UUID, app_version: str | None) -> Device:
    existing = get_device_by_identifier(db, device_identifier)
    if existing is not None:
        existing.officer_id = officer_id
        existing.app_version = app_version or existing.app_version
        existing.last_active_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing
    device = Device(device_identifier=device_identifier, officer_id=officer_id, app_version=app_version)
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def list_devices(db: Session) -> list[Device]:
    return list(db.execute(select(Device).order_by(Device.registered_at.desc())).scalars())


def get_device(db: Session, device_id: uuid.UUID) -> Device | None:
    return db.get(Device, device_id)


def set_device_disabled(db: Session, device: Device, is_disabled: bool) -> Device:
    device.is_disabled = is_disabled
    db.commit()
    db.refresh(device)
    return device


def touch_last_active(db: Session, device: Device) -> Device:
    device.last_active_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(device)
    return device
