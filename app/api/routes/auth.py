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
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id, user.role.value),
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
        user_id = claims["sub"]  # Keep as string since our model now uses String type
        # Validate it's a proper UUID format
        uuid.UUID(user_id)  # This validates the format but we keep it as string
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject") from exc

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id, user.role.value),
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
    checkpoint = db.query(Checkpoint).filter(Checkpoint.id == user.checkpoint_id).first() if user.checkpoint_id else None
    return CurrentUserResponse(
        id=user.id,  # Already a string now
        username=user.username,
        role=user.role.value,
        checkpoint_id=checkpoint.id if checkpoint else None,  # Already a string now
        checkpoint_code=checkpoint.code if checkpoint else None,
        checkpoint_name=checkpoint.name if checkpoint else None,
    )
