import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class IdentityEmbeddingRecord(Base):
    """A stored face embedding tied to a declared identity (name +
    optional document number), used to detect the same face registered
    under more than one identity."""

    __tablename__ = "identity_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    reference_name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding_json: Mapped[str] = mapped_column(Text, nullable=False)
    # Set (via set_case_id, after the fact — the case doesn't exist yet
    # when the embedding is captured mid-screening) so a multi-identity
    # cluster found later can be traced back to the cases it spans, for
    # the Identity History page.
    case_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("cases.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
