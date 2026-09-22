"""Image serving and upload endpoints for document and selfie images.
Images are stored in the database (not on disk) so they survive
Render's ephemeral filesystem resets."""
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.image import StoredImage
from app.models.user import User
from app.repositories.verification_repository import get_verification

router = APIRouter(prefix="/images", tags=["images"])


def _get_image(db: Session, verification_id: uuid.UUID, image_type: str) -> StoredImage | None:
    return (
        db.query(StoredImage)
        .filter(StoredImage.verification_id == verification_id, StoredImage.image_type == image_type)
        .first()
    )


def _serve_image(db: Session, verification_id: uuid.UUID, image_type: str, user: User) -> Response:
    record = get_verification(db, verification_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="verification record not found")
    img = _get_image(db, verification_id, image_type)
    if img is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{image_type} image not found")
    return Response(content=img.data, media_type=img.content_type)


@router.get("/{verification_id}/document", summary="Get document front image")
def get_document_image(
    verification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _serve_image(db, verification_id, "document_front", user)


@router.get("/{verification_id}/document-back", summary="Get document back image")
def get_document_back_image(
    verification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _serve_image(db, verification_id, "document_back", user)


@router.get("/{verification_id}/selfie", summary="Get selfie image")
def get_selfie_image(
    verification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _serve_image(db, verification_id, "selfie", user)


@router.post(
    "/{verification_id}/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Upload document/selfie images after screening",
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

    saved = []

    front_bytes = await document_front.read()
    if front_bytes:
        existing = _get_image(db, verification_id, "document_front")
        if existing:
            existing.data = front_bytes
        else:
            db.add(StoredImage(verification_id=verification_id, image_type="document_front", data=front_bytes))
        saved.append("document_front")

    if document_back:
        back_bytes = await document_back.read()
        if back_bytes:
            existing = _get_image(db, verification_id, "document_back")
            if existing:
                existing.data = back_bytes
            else:
                db.add(StoredImage(verification_id=verification_id, image_type="document_back", data=back_bytes))
            saved.append("document_back")

    if selfie:
        selfie_bytes = await selfie.read()
        if selfie_bytes:
            existing = _get_image(db, verification_id, "selfie")
            if existing:
                existing.data = selfie_bytes
            else:
                db.add(StoredImage(verification_id=verification_id, image_type="selfie", data=selfie_bytes))
            saved.append("selfie")

    db.commit()
    return {"verification_id": str(verification_id), "saved": saved}
