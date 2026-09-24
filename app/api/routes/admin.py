"""Admin user and device management. All authenticated officers have full access."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.models.checkpoint import Checkpoint
from app.models.user import User, UserRole
from app.repositories.audit_repository import log_event
from app.repositories.device_repository import list_devices, reactivate_device, revoke_device, set_device_disabled
from app.repositories.device_repository import get_device as get_device_row
from app.repositories.user_repository import create_user, get_user, list_users, officer_roster, update_user
from app.schemas.admin import (
    CheckpointResponse,
    DeviceResponse,
    DeviceRevokeRequest,
    DeviceUpdateRequest,
    OfficerResponse,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)

# Every route that creates, changes or deletes data (and the account list) is
# admin-only (REVIEWER). The officer roster and checkpoint list are read-only
# and open to any signed-in user.
router = APIRouter(prefix="/admin", tags=["admin"])


def _user_response(db: Session, user: User) -> UserResponse:
    checkpoint = db.get(Checkpoint, user.checkpoint_id) if user.checkpoint_id else None
    return UserResponse(
        id=str(user.id), username=user.username, role=user.role.value,
        checkpoint_code=checkpoint.code if checkpoint else None,
        is_active=user.is_active, created_at=user.created_at.isoformat(),
    )


def _device_response(db: Session, device) -> DeviceResponse:
    officer = db.execute(select(User).where(User.id == str(device.officer_id))).scalar_one_or_none()
    return DeviceResponse(
        id=str(device.id), device_identifier=device.device_identifier,
        officer_username=officer.username if officer else None,
        app_version=device.app_version, is_disabled=device.is_disabled,
        revoked_at=device.revoked_at.isoformat() if device.revoked_at else None,
        revoked_reason=device.revoked_reason,
        last_active_at=device.last_active_at.isoformat() if device.last_active_at else None,
        registered_at=device.registered_at.isoformat(),
    )


@router.get("/users", response_model=list[UserResponse], summary="List all system accounts")
def list_users_route(
    _user: User = Depends(require_role(UserRole.REVIEWER)), db: Session = Depends(get_db)
) -> list[UserResponse]:
    return [_user_response(db, u) for u in list_users(db)]


@router.post("/users", response_model=UserResponse, summary="Create a new account")
def create_user_route(
    payload: UserCreateRequest,
    _user: User = Depends(require_role(UserRole.REVIEWER)),
    db: Session = Depends(get_db),
) -> UserResponse:
    checkpoint_id = uuid.UUID(payload.checkpoint_id) if payload.checkpoint_id else None
    try:
        user = create_user(db, payload.username, payload.password, UserRole.OFFICER, checkpoint_id)
    except Exception as exc:  # unique-username violation, etc.
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"could not create user: {exc}") from exc
    return _user_response(db, user)


@router.patch("/users/{user_id}", response_model=UserResponse, summary="Change checkpoint/active state, or reset password")
def update_user_route(
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    _user: User = Depends(require_role(UserRole.REVIEWER)),
    db: Session = Depends(get_db),
) -> UserResponse:
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    checkpoint_id = uuid.UUID(payload.checkpoint_id) if payload.checkpoint_id else None
    user = update_user(
        db, user, role=None, checkpoint_id=checkpoint_id, is_active=payload.is_active, new_password=payload.new_password
    )
    return _user_response(db, user)


@router.get("/officers", response_model=list[OfficerResponse], summary="Officer roster with real case counts")
def list_officers_route(
    _user: User = Depends(require_role()), db: Session = Depends(get_db)
) -> list[OfficerResponse]:
    return [OfficerResponse(**row) for row in officer_roster(db)]


@router.get("/devices", response_model=list[DeviceResponse], summary="List all registered field devices")
def list_devices_route(
    _user: User = Depends(require_role(UserRole.REVIEWER)), db: Session = Depends(get_db)
) -> list[DeviceResponse]:
    return [_device_response(db, d) for d in list_devices(db)]


@router.patch("/devices/{device_id}", response_model=DeviceResponse, summary="Disable (or re-enable) a device, e.g. reported lost")
def update_device_route(
    device_id: uuid.UUID,
    payload: DeviceUpdateRequest,
    _user: User = Depends(require_role(UserRole.REVIEWER)),
    db: Session = Depends(get_db),
) -> DeviceResponse:
    device = get_device_row(db, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device not found")
    device = set_device_disabled(db, device, payload.is_disabled)
    return _device_response(db, device)


@router.post(
    "/devices/{device_id}/revoke",
    response_model=DeviceResponse,
    summary="Revoke a device (select device, confirm, give a reason) — a harder, reasoned state than disable",
)
def revoke_device_route(
    device_id: uuid.UUID,
    payload: DeviceRevokeRequest,
    user: User = Depends(require_role(UserRole.REVIEWER)),
    db: Session = Depends(get_db),
) -> DeviceResponse:
    device = get_device_row(db, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device not found")
    device = revoke_device(db, device, payload.reason)
    log_event(db, None, "DEVICE_REVOKED", user.id, reason=payload.reason)
    return _device_response(db, device)


@router.post(
    "/devices/{device_id}/reactivate",
    response_model=DeviceResponse,
    summary="Reactivate a previously revoked device",
)
def reactivate_device_route(
    device_id: uuid.UUID,
    user: User = Depends(require_role(UserRole.REVIEWER)),
    db: Session = Depends(get_db),
) -> DeviceResponse:
    device = get_device_row(db, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device not found")
    device = reactivate_device(db, device)
    log_event(db, None, "DEVICE_REACTIVATED", user.id)
    return _device_response(db, device)


@router.delete("/reset-screening", summary="Delete all screening cases, verifications, and audit data")
def reset_screening_data(
    _user: User = Depends(require_role(UserRole.REVIEWER)), db: Session = Depends(get_db)
) -> dict:
    tables = ["case_notes", "officer_decisions", "audit_events", "stored_images",
               "blockchain_blocks", "cases", "verifications", "sync_queue_items"]
    deleted = {}
    for t in tables:
        try:
            count = db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            try:
                db.execute(text(f"TRUNCATE TABLE {t} CASCADE"))
            except Exception:
                db.rollback()
                db.execute(text(f"DELETE FROM {t}"))
            db.commit()
            deleted[t] = count
        except Exception:
            db.rollback()
            deleted[t] = "skipped"
    return {"deleted": deleted}


@router.delete("/purge-demo-cases", summary="Delete only the seeded demo cases (BSA-20260916-*) and their verification records")
def purge_demo_cases(
    _user: User = Depends(require_role(UserRole.REVIEWER)), db: Session = Depends(get_db)
) -> dict:
    from app.models.case import Case
    from app.models.verification import VerificationRecord
    demo_cases = db.query(Case).filter(Case.case_number.like("BSA-20260916-%")).all()
    if not demo_cases:
        return {"deleted_cases": 0, "deleted_verifications": 0}
    verification_ids = [c.verification_id for c in demo_cases if c.verification_id]
    case_ids = [c.id for c in demo_cases]
    for cid in case_ids:
        db.execute(text("DELETE FROM case_notes WHERE case_id = :cid"), {"cid": str(cid)})
        db.execute(text("DELETE FROM officer_decisions WHERE case_id = :cid"), {"cid": str(cid)})
        db.execute(text("DELETE FROM audit_events WHERE case_id = :cid"), {"cid": str(cid)})
    for c in demo_cases:
        db.delete(c)
    db.flush()
    v_count = 0
    for vid in verification_ids:
        v = db.get(VerificationRecord, vid)
        if v:
            db.delete(v)
            v_count += 1
    db.commit()
    return {"deleted_cases": len(demo_cases), "deleted_verifications": v_count}


@router.get("/checkpoints", response_model=list[CheckpointResponse], summary="List all checkpoints")
def list_checkpoints_route(
    _user: User = Depends(require_role()), db: Session = Depends(get_db)
) -> list[CheckpointResponse]:
    checkpoints = list(db.query(Checkpoint).order_by(Checkpoint.code).all())
    return [
        CheckpointResponse(id=str(c.id), code=c.code, name=c.name, location=c.location, is_active=c.is_active)
        for c in checkpoints
    ]

class _TestCases(BaseModel):
    case_numbers: list[str] = Field(min_length=1, max_length=100)


@router.delete("/test-cases", summary="Remove synthetic test cases (e.g. from end-to-end checks)")
def remove_test_cases(body: _TestCases, user: User = Depends(require_role(UserRole.REVIEWER)),
                      db: Session = Depends(get_db)) -> dict:
    """Delete the named cases and everything linked to them, only if every one
    is synthetic test data (traveller name contains SYNTHETIC). The document
    verification behind each case stays in the tamper-evident chain, marked
    withdrawn and hidden from lists. The removal itself is audit-logged."""
    from datetime import datetime, timezone
    from app.models.case import Case
    from app.models.document_verification import DocumentVerificationRecord
    cases = db.query(Case).filter(Case.case_number.in_(body.case_numbers)).all()
    found = {c.case_number for c in cases}
    missing = sorted(set(body.case_numbers) - found)
    not_test = sorted(c.case_number for c in cases if "SYNTHETIC" not in (c.traveler_name or "").upper())
    if missing or not_test:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"missing": missing, "not_synthetic": not_test,
                                    "message": "only existing synthetic test cases can be removed"})
    now = datetime.now(timezone.utc)
    removed, withdrawn = [], 0
    for c in cases:
        cid = str(c.id)
        params = {"cid": cid}
        for sql in ("DELETE FROM case_notes WHERE case_id = :cid",
                    "DELETE FROM officer_decisions WHERE case_id = :cid",
                    "DELETE FROM sync_queue_items WHERE case_id = :cid",
                    "DELETE FROM network_relationships WHERE evidence_case_id = :cid",
                    "DELETE FROM travel_events WHERE case_id = :cid",
                    "DELETE FROM identity_embeddings WHERE case_id = :cid",
                    "DELETE FROM audit_events WHERE case_id = :cid"):
            db.execute(text(sql), _uuid_params(db, params))
        if c.verification_id:
            db.execute(text("DELETE FROM stored_images WHERE verification_id = :vid"),
                       _uuid_params(db, {"vid": str(c.verification_id)}))
        for rec in db.query(DocumentVerificationRecord).filter(DocumentVerificationRecord.case_id == cid):
            rec.case_id = None
            rec.withdrawn_at = now
            rec.withdrawn_reason = f"synthetic test data (case {c.case_number}) removed by {user.username}"
            withdrawn += 1
        db.delete(c)
        removed.append(c.case_number)
    db.flush()
    log_event(db, None, "TEST_DATA_REMOVED", user.id, reason="Removed synthetic test cases: " + ", ".join(removed))
    db.commit()
    return {"removed_cases": removed, "withdrawn_verifications": withdrawn}


def _uuid_params(db: Session, params: dict) -> dict:
    """UUID columns: native uuid on PostgreSQL, 32-char hex on SQLite."""
    if db.get_bind().dialect.name == "postgresql":
        return params
    return {k: uuid.UUID(v).hex for k, v in params.items()}
