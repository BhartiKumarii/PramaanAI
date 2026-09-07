"""create identity_embeddings table

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "identity_embeddings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("reference_name", sa.String(length=255), nullable=False),
        sa.Column("document_number", sa.String(length=64), nullable=True),
        sa.Column("embedding_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("identity_embeddings")
