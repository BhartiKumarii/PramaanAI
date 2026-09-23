"""Modular document-verification pipeline: verification records, per-check
evidence rows and reference-data snapshots.

Revision ID: 0017
Revises: e28403cb489a
Create Date: 2026-09-23
"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "e28403cb489a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_verifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("client_request_id", sa.String(64), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("document_types", sa.Text(), nullable=False),
        sa.Column("country", sa.String(32), nullable=True),
        sa.Column("border_route", sa.String(32), nullable=True),
        sa.Column("overall_status", sa.String(40), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("input_hashes", sa.Text(), nullable=False),
        sa.Column("reference_data_version", sa.String(32), nullable=False),
        sa.Column("captured_offline", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("device_id", sa.String(128), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_status", sa.String(24), nullable=False, server_default="SERVER"),
        sa.Column("officer_action", sa.String(40), nullable=False, server_default="PENDING"),
        sa.Column("officer_action_reason", sa.Text(), nullable=True),
        sa.Column("officer_action_by", sa.String(36), nullable=True),
        sa.Column("officer_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("record_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_document_verifications_sequence", "document_verifications", ["sequence"], unique=True)
    op.create_index("ix_document_verifications_client_request_id", "document_verifications", ["client_request_id"],
                    unique=True)
    op.create_index("ix_document_verifications_created_by", "document_verifications", ["created_by"])
    op.create_index("ix_document_verifications_overall_status", "document_verifications", ["overall_status"])
    op.create_table(
        "document_verification_checks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("verification_id", sa.Uuid(), sa.ForeignKey("document_verifications.id"), nullable=False),
        sa.Column("document_index", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(48), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("blocking", sa.Boolean(), nullable=False),
        sa.Column("strong_evidence", sa.Boolean(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_document_verification_checks_verification_id", "document_verification_checks", ["verification_id"])
    op.create_index("ix_document_verification_checks_name", "document_verification_checks", ["name"])
    op.create_index("ix_document_verification_checks_status", "document_verification_checks", ["status"])
    op.create_table(
        "reference_data_snapshots",
        sa.Column("version", sa.String(32), primary_key=True),
        sa.Column("manifest_json", sa.Text(), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("document_verification_checks")
    op.drop_table("document_verifications")
    op.drop_table("reference_data_snapshots")
