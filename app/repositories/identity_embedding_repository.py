import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.identity_embedding import IdentityEmbeddingRecord


def insert_embedding(
    db: Session, reference_name: str, document_number: str | None, embedding: list[float]
) -> IdentityEmbeddingRecord:
    record = IdentityEmbeddingRecord(
        reference_name=reference_name,
        document_number=document_number,
        embedding_json=json.dumps(embedding),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_all(db: Session) -> list[IdentityEmbeddingRecord]:
    return list(db.execute(select(IdentityEmbeddingRecord)).scalars())
