import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class VerificationRecord(Base):
    """A persisted screening result. `signature` is an HMAC-SHA256 over
    the content fields (see app/core/hmac_signing.py) — verified on every
    read, never trusted from the row alone."""

    __tablename__ = "verifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    nationality: Mapped[str] = mapped_column(String(64), nullable=False)
    # Informational only (OCR best-effort) — never part of the HMAC-signed
    # payload, so it can't be used to forge or alter a scored result.
    traveler_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # Raw per-signal outputs (each a serialized Pydantic model), stored so
    # any officer can pull the full evidence behind a score later, not only
    # the device that originally ran the screening. Additive only — none of
    # this is part of the HMAC-signed payload.
    ocr_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    tampering_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    deepfake_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    registry_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    face_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    identity_graph_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    liveness_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    top_reason: Mapped[str] = mapped_column(Text, nullable=False)
    breakdown_json: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
