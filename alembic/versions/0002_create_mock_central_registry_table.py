"""create mock_central_registry table

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mock_central_registry",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_number", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_mock_central_registry_document_number",
        "mock_central_registry",
        ["document_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_mock_central_registry_document_number", table_name="mock_central_registry")
    op.drop_table("mock_central_registry")
