"""link identity_embeddings to cases, add document-number hash to person_entities

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "identity_embeddings", sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id"), nullable=True)
    )
    op.add_column(
        "person_entities", sa.Column("document_number_hash", sa.String(length=64), nullable=True)
    )
    op.create_index("ix_person_entities_document_number_hash", "person_entities", ["document_number_hash"])


def downgrade() -> None:
    op.drop_index("ix_person_entities_document_number_hash", table_name="person_entities")
    op.drop_column("person_entities", "document_number_hash")
    op.drop_column("identity_embeddings", "case_id")
