"""Image serving and upload endpoints for document and selfie images.
Supports serving images stored on server for web dashboard review.
Upload endpoint is separate from the screening submission —
raw images are never sent as part of the screening request itself."""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.verification_repository import get_verification

router = APIRouter(prefix="/images", tags=["images"])

# Directory where images are stored (should match Android app storage)
def get_images_dir():
    settings = get_settings()
    images_dir = Path(getattr(settings, 'images_dir', 'images'))
    images_dir.mkdir(exist_ok=True)
    return images_dir


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

    image_path = get_images_dir() / f"{verification_id}.jpg"
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

    image_path = get_images_dir() / f"{verification_id}_back.jpg"
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

    image_path = get_images_dir() / f"{verification_id}_selfie.jpg"
    if not image_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="selfie image not found")

    return FileResponse(str(image_path), media_type="image/jpeg")


@router.post(
    "/{verification_id}/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Upload document/selfie images after screening (separate from screening data)",
)
async def upload_images(
    verification_id: uuid.UUID,
    document_front: UploadFile = File(..., description="Front side of document"),
    document_back: UploadFile | None = File(None, description="Back side of document (optional)"),
    selfie: UploadFile | None = File(None, description="Live selfie capture (optional)"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = get_verification(db, verification_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="verification record not found")

    images_dir = get_images_dir()
    saved = []

    front_bytes = await document_front.read()
    if front_bytes:
        (images_dir / f"{verification_id}.jpg").write_bytes(front_bytes)
        saved.append("document_front")

    if document_back:
        back_bytes = await document_back.read()
        if back_bytes:
            (images_dir / f"{verification_id}_back.jpg").write_bytes(back_bytes)
            saved.append("document_back")

    if selfie:
        selfie_bytes = await selfie.read()
        if selfie_bytes:
            (images_dir / f"{verification_id}_selfie.jpg").write_bytes(selfie_bytes)
            saved.append("selfie")

    return {"verification_id": str(verification_id), "saved": saved}