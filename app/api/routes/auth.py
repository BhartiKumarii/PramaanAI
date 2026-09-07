from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token, get_current_user, verify_password
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repository import get_user_by_username
from app.schemas.auth import CurrentUserResponse, LoginRequest, TokenResponse

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


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="The authenticated officer's own identity — real server-side record, not client-supplied",
)
def get_current_user_info(user: User = Depends(get_current_user)) -> CurrentUserResponse:
    return CurrentUserResponse(id=str(user.id), username=user.username, role=user.role.value)
