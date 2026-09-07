"""Identity graph endpoint: stores a face embedding for a declared
identity and checks it against every previously stored embedding for a
multi-identity cluster (same face, different declared name/document)."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.identity_embedding_repository import insert_embedding, list_all
from app.services.face.embedding import extract_embedding
from app.services.identity_graph.base import IdentityGraphResult
from app.services.identity_graph.graph import build_graph, find_multi_identity_cluster

router = APIRouter(prefix="/identity", tags=["identity"])


@router.post(
    "/check",
    response_model=IdentityGraphResult,
    summary="Store a face embedding and check for a multi-identity cluster against past embeddings",
)
async def check_identity(
    reference_name: str = Form(...),
    document_number: str | None = Form(None),
    file: UploadFile = File(...),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IdentityGraphResult:
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file upload")

    embedding = extract_embedding(image_bytes)
    record = insert_embedding(db, reference_name, document_number, embedding)
    records = list_all(db)
    graph = build_graph(records)
    return find_multi_identity_cluster(graph, str(record.id))
