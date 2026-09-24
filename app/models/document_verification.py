import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class DocumentVerificationRecord(Base):
    """One run of the modular document-verification pipeline (/api/v1).

    Minimum retention: no image is stored — only SHA-256 hashes of the
    inputs, the structured (masked) result and the officer's action.
    Tamper evidence: every row is HMAC-signed and linked into a LOCAL hash
    chain (prev_hash -> record_hash). This is a local tamper-evident log,
    not a distributed ledger or blockchain.
    """

    __tablename__ = "document_verifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # unique: two workers that compute the same next link cannot both commit
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    # Idempotency key from the client (e.g. the offline queue item id), so a
    # retried sync returns the stored result instead of creating a duplicate.
    client_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)  # SERVER_IMAGE | DEVICE_REGIONS | DEVICE_EXTRACTED
    document_types: Mapped[str] = mapped_column(Text, nullable=False)  # JSON list
    country: Mapped[str | None] = mapped_column(String(32), nullable=True)
    border_route: Mapped[str | None] = mapped_column(String(32), nullable=True)
    overall_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    input_hashes: Mapped[str] = mapped_column(Text, nullable=False)  # JSON list of sha256
    reference_data_version: Mapped[str] = mapped_column(String(32), nullable=False)
    captured_offline: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_status: Mapped[str] = mapped_column(String(24), nullable=False, default="SERVER")  # SERVER | SYNCED_FROM_DEVICE
    officer_action: Mapped[str] = mapped_column(String(40), nullable=False, default="PENDING")
    officer_action_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    officer_action_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    officer_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Screening workflow link (set after the record is chained, so it is NOT
    # part of record_hash): the case this verification opened, the signed
    # screening VerificationRecord behind that case, and identity-graph
    # findings computed at that time.
    case_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    screening_verification_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    identity_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Withdrawn records (e.g. synthetic test data) stay in the chain but are
    # hidden from lists; not part of record_hash (migration 0022).
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    signature: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DocumentVerificationCheck(Base):
    """One check of a verification, stored as its own row so evidence can be
    queried (e.g. "all stamp_forensics REVIEW_REQUIRED this week")."""

    __tablename__ = "document_verification_checks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    verification_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("document_verifications.id"), index=True,
                                                       nullable=False)
    document_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    blocking: Mapped[bool] = mapped_column(Boolean, nullable=False)
    strong_evidence: Mapped[bool] = mapped_column(Boolean, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)  # evidence items (boxes, compared values)


class ReferenceDataSnapshot(Base):
    """A registered version of reference_data/ (checkpoints, rules,
    templates, stamp references, trust anchors). Each verification records
    the version it was checked against; this table records what that version
    contained (file list + hashes + data classification)."""

    __tablename__ = "reference_data_snapshots"

    version: Mapped[str] = mapped_column(String(32), primary_key=True)
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DatasetRegistryRecord(Base):
    """Identity/document record extracted from the project's own sample image
    dataset (data/dataset_1) — a LOCAL TEST FIXTURE, not synthetic data and
    not a government database. Built by scripts/docverify/build_dataset_registry.py
    only on a developer machine; never seeded to a deployment.

    Field values keep their provenance: MRZ_VALIDATED when every MRZ check
    digit passed, otherwise OCR_UNREVIEWED with per-field confidence. Aadhaar
    numbers are never stored in full (last 4 digits + SHA-256 only)."""

    __tablename__ = "dataset_registry_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    document_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    country: Mapped[str | None] = mapped_column(String(32), nullable=True)
    document_number: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    document_number_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_of_birth: Mapped[str | None] = mapped_column(String(10), nullable=True)  # ISO
    nationality: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sex: Mapped[str | None] = mapped_column(String(8), nullable=True)
    date_of_issue: Mapped[str | None] = mapped_column(String(10), nullable=True)
    date_of_expiry: Mapped[str | None] = mapped_column(String(10), nullable=True)
    extra_fields_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    field_provenance_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    record_status: Mapped[str] = mapped_column(String(24), nullable=False)  # MRZ_VALIDATED | OCR_UNREVIEWED | FACE_ONLY
    face_image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    face_embedding_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    linked_record_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)  # portrait -> document (face-similarity suggestion)
    link_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_classification: Mapped[str] = mapped_column(String(40), nullable=False, default="REAL_SAMPLE_TEST_FIXTURE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
