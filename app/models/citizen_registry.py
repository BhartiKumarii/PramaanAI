import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class MockCitizenRegistryEntry(Base):
    """A synthetic citizen/passport-holder registry entry — the positive
    counterpart to MockCentralRegistryEntry's watchlist: "this document
    number belongs to this person" rather than "this person is flagged."
    Explicitly labeled mock — there is no real government population
    registry access here or anywhere in this build (see CLAUDE.md)."""

    __tablename__ = "mock_citizen_registry"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_number: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    date_of_birth: Mapped[str] = mapped_column(String(10), nullable=False)  # DD/MM/YYYY
    nationality: Mapped[str] = mapped_column(String(64), nullable=False)
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    date_of_expiry: Mapped[str | None] = mapped_column(String(10), nullable=True)  # DD/MM/YYYY
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")  # ACTIVE | EXPIRED | REVOKED
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
