import json
import uuid

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


def get_embedding(db: Session, record_id: uuid.UUID) -> IdentityEmbeddingRecord | None:
    return db.get(IdentityEmbeddingRecord, record_id)


def get_by_case_id(db: Session, case_id: uuid.UUID) -> IdentityEmbeddingRecord | None:
    return db.execute(
        select(IdentityEmbeddingRecord).where(IdentityEmbeddingRecord.case_id == case_id)
    ).scalar_one_or_none()


def set_case_id(db: Session, record: IdentityEmbeddingRecord, case_id: uuid.UUID) -> IdentityEmbeddingRecord:
    record.case_id = case_id
    db.commit()
    db.refresh(record)
    return record
