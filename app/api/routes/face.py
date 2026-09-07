"""Face verification endpoint (Module 4): real embedding extraction +
real cosine similarity between a document photo and a live capture."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import get_face_provider
from app.core.security import get_current_user
from app.models.user import User
from app.services.face.base import FaceMatchResult, FaceProvider
from app.utils.image import downscale_image_bytes

router = APIRouter(prefix="/face", tags=["face"])


@router.post(
    "/verify",
    response_model=FaceMatchResult,
    summary="Compare a document photo against a live capture via face embedding cosine similarity",
)
async def verify_face(
    document_face: UploadFile = File(...),
    presented_face: UploadFile = File(...),
    _user: User = Depends(get_current_user),
    face_provider: FaceProvider = Depends(get_face_provider),
) -> FaceMatchResult:
    document_bytes = await document_face.read()
    presented_bytes = await presented_face.read()
    if not document_bytes or not presented_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file upload")
    document_bytes = downscale_image_bytes(document_bytes)
    presented_bytes = downscale_image_bytes(presented_bytes)
    return face_provider.verify(document_bytes, presented_bytes)
