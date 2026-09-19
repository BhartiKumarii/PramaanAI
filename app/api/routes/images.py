"""Image serving endpoints for document and selfie images.
Supports serving images stored on server for web dashboard review."""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.verification_repository import get_verification

router = APIRouter(prefix="/images", tags=["images"])

# Directory where images are stored (should match Android app storage)
IMAGES_DIR = Path(settings.images_dir) if hasattr(settings, 'images_dir') else Path("images")
IMAGES_DIR.mkdir(exist_ok=True)


@router.get(
    "/{verification_id}/document",
    response_class=FileResponse,
    summary="Get document front image for a verification record"
)
def get_document_image(
    verification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify user has access to this verification record
    record = get_verification(db, verification_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="verification record not found")

    image_path = IMAGES_DIR / f"{verification_id}.jpg"
    if not image_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document image not found")

    return FileResponse(str(image_path), media_type="image/jpeg")


@router.get(
    "/{verification_id}/document-back",
    response_class=FileResponse,
    summary="Get document back image for a verification record"
)
def get_document_back_image(
    verification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify user has access to this verification record
    record = get_verification(db, verification_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="verification record not found")

    image_path = IMAGES_DIR / f"{verification_id}_back.jpg"
    if not image_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document back image not found")

    return FileResponse(str(image_path), media_type="image/jpeg")


@router.get(
    "/{verification_id}/selfie",
    response_class=FileResponse,
    summary="Get selfie image for a verification record"
)
def get_selfie_image(
    verification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify user has access to this verification record
    record = get_verification(db, verification_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="verification record not found")

    image_path = IMAGES_DIR / f"{verification_id}_selfie.jpg"
    if not image_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="selfie image not found")

    return FileResponse(str(image_path), media_type="image/jpeg")