from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.registry import MockCentralRegistryEntry


def find_by_document_number(db: Session, document_number: str) -> MockCentralRegistryEntry | None:
    normalized = document_number.strip().upper()
    return db.execute(
        select(MockCentralRegistryEntry).where(
            func.upper(MockCentralRegistryEntry.document_number) == normalized
        )
    ).scalar_one_or_none()


def list_all_entries(db: Session) -> list[MockCentralRegistryEntry]:
    return list(db.execute(select(MockCentralRegistryEntry)).scalars())


def insert_entries(db: Session, entries: list[dict]) -> int:
    objects = [MockCentralRegistryEntry(**entry) for entry in entries]
    db.add_all(objects)
    db.commit()
    return len(objects)
