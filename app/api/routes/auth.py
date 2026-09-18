import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    verify_password,
)
from app.db.session import get_db
from app.models.checkpoint import Checkpoint
from app.models.user import User
from app.repositories.user_repository import get_user_by_username
from app.schemas.auth import CurrentUserResponse, LoginRequest, RefreshRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate an officer/supervisor/admin and obtain JWTs",
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = get_user_by_username(db, payload.username)
    if user is None or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    return TokenResponse(
        access_token=create_access_token(str(user.id), user.role.value),
        refresh_token=create_refresh_token(str(user.id), user.role.value),
        role=user.role.value,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange a valid refresh token for a fresh access + refresh token pair",
)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    claims = decode_token(payload.refresh_token)
    if claims.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    try:
        user_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return TokenResponse(
        access_token=create_access_token(str(user.id), user.role.value),
        refresh_token=create_refresh_token(str(user.id), user.role.value),
        role=user.role.value,
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="The authenticated officer's own identity — real server-side record, not client-supplied",
)
def get_current_user_info(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CurrentUserResponse:
    checkpoint = db.get(Checkpoint, user.checkpoint_id) if user.checkpoint_id else None
    return CurrentUserResponse(
        id=str(user.id),
        username=user.username,
        role=user.role.value,
        checkpoint_id=str(checkpoint.id) if checkpoint else None,
        checkpoint_code=checkpoint.code if checkpoint else None,
        checkpoint_name=checkpoint.name if checkpoint else None,
    )
