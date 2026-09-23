"""Local test-fixture registry built from the project's sample image dataset.

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-23
"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dataset_registry_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_file", sa.String(255), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("country", sa.String(32), nullable=True),
        sa.Column("document_number", sa.String(64), nullable=True),
        sa.Column("document_number_sha256", sa.String(64), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("date_of_birth", sa.String(10), nullable=True),
        sa.Column("nationality", sa.String(64), nullable=True),
        sa.Column("sex", sa.String(8), nullable=True),
        sa.Column("date_of_issue", sa.String(10), nullable=True),
        sa.Column("date_of_expiry", sa.String(10), nullable=True),
        sa.Column("extra_fields_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("field_provenance_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("record_status", sa.String(24), nullable=False),
        sa.Column("face_image_path", sa.String(512), nullable=True),
        sa.Column("face_embedding_json", sa.Text(), nullable=True),
        sa.Column("linked_record_id", sa.Uuid(), nullable=True),
        sa.Column("link_similarity", sa.Float(), nullable=True),
        sa.Column("data_classification", sa.String(40), nullable=False, server_default="REAL_SAMPLE_TEST_FIXTURE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_dataset_registry_records_document_type", "dataset_registry_records", ["document_type"])
    op.create_index("ix_dataset_registry_records_document_number", "dataset_registry_records", ["document_number"])
    op.create_index("ix_dataset_registry_records_document_number_sha256", "dataset_registry_records",
                    ["document_number_sha256"])


def downgrade() -> None:
    op.drop_table("dataset_registry_records")
