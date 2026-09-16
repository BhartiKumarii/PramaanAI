import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class CaseStatus(str, enum.Enum):
    # Screening pipeline ran on-device but hasn't reached the server yet
    # (offline capture) — Android's "Pending Sync" filter.
    PENDING_SYNC = "PENDING_SYNC"
    # Synced, screened, not yet forwarded to an Immigration Officer.
    PENDING = "PENDING"
    # Forwarded — sitting in the Immigration Officer's incoming queue.
    SENT = "SENT"
    # A preliminary result of REVIEW_REQUIRED was reached by the on-device
    # heuristics (identity/network alert) — still awaiting the officer's
    # authorised decision, distinct from the final decision statuses below.
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    # Terminal states, set only via POST /cases/{id}/decision.
    CLEAR = "CLEAR"
    SECONDARY_REVIEW = "SECONDARY_REVIEW"
    HOLD_REFER = "HOLD_REFER"


class CasePriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Case(Base):
    """The officer-facing workflow unit — wraps one screening result
    (VerificationRecord) with who scanned it, where, its current status,
    and who it's assigned to. This is what /cases, the web console's
    Incoming Cases queue, and the Android My Cases list all operate on;
    VerificationRecord stays the immutable, signed analysis payload
    underneath it."""

    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Short human-facing identifier shown on screen/reports, e.g.
    # "BSA-20260916-0007" — not used for any lookup, `id` is authoritative.
    case_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus, name="case_status"), nullable=False, default=CaseStatus.PENDING
    )
    priority: Mapped[CasePriority] = mapped_column(
        Enum(CasePriority, name="case_priority"), nullable=False, default=CasePriority.LOW
    )
    checkpoint_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("checkpoints.id"), nullable=False)
    field_officer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    assigned_officer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    verification_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("verifications.id"), nullable=True
    )
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    nationality: Mapped[str] = mapped_column(String(64), nullable=False)
    traveler_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CaseNote(Base):
    """A free-text note attached to a case by any officer/supervisor who
    touched it — additive, never edited or deleted, so the note trail
    itself is part of the audit record."""

    __tablename__ = "case_notes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cases.id"), nullable=False, index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OfficerDecision(Base):
    """The authorised, final human decision on a case — the one thing no
    AI signal or UI path may set directly. Every decision is a new row
    (never an update), so `cases.status` reflects the latest but the full
    history — including a supervisor override — survives in this table."""

    __tablename__ = "officer_decisions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cases.id"), nullable=False, index=True)
    officer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)  # CLEAR | SECONDARY_REVIEW | HOLD_REFER
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SyncQueueItem(Base):
    """A case captured offline on a device, queued until connectivity
    returns. `attempts` and `last_error` exist so IT/Admin's sync-status
    view can show *why* something is stuck, not just that it is."""

    __tablename__ = "sync_queue_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("devices.id"), nullable=False)
    case_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("cases.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")  # PENDING|SYNCED|FAILED
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
