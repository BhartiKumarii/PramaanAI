from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.citizen_registry import MockCitizenRegistryEntry
from app.utils.masking import normalize_document_number


def find_by_document_number(db: Session, document_number: str) -> MockCitizenRegistryEntry | None:
    normalized = normalize_document_number(document_number)
    return db.execute(
        select(MockCitizenRegistryEntry).where(
            MockCitizenRegistryEntry.document_number == normalized
        )
    ).scalar_one_or_none()


def count_entries(db: Session) -> int:
    return len(list(db.execute(select(MockCitizenRegistryEntry.id)).scalars()))


def insert_entry(
    db: Session,
    document_number: str,
    full_name: str,
    date_of_birth: str,
    nationality: str,
    document_type: str,
    date_of_expiry: str | None = None,
    gender: str | None = None,
    status: str = "ACTIVE",
) -> MockCitizenRegistryEntry:
    entry = MockCitizenRegistryEntry(
        document_number=normalize_document_number(document_number),
        full_name=full_name,
        date_of_birth=date_of_birth,
        nationality=nationality,
        gender=gender,
        document_type=document_type,
        date_of_expiry=date_of_expiry,
        status=status,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
