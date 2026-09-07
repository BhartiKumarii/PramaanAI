import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class MockCentralRegistryEntry(Base):
    """A synthetic watchlist/lost-document entry. Explicitly labeled mock —
    there is no real INTERPOL/government registry access here or anywhere
    in this build."""

    __tablename__ = "mock_central_registry"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_number: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)  # LOW | MEDIUM | HIGH
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
