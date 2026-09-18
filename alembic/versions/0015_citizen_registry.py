"""add mock_citizen_registry table and verifications.citizen_registry_json

A positive-verification counterpart to the existing watchlist-only
mock_central_registry: "this document number belongs to this declared
person" rather than only "this person is flagged." Still clearly mock/
demo data (see app/models/citizen_registry.py).

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mock_citizen_registry",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_number", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("date_of_birth", sa.String(length=10), nullable=False),
        sa.Column("nationality", sa.String(length=64), nullable=False),
        sa.Column("gender", sa.String(length=16), nullable=True),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("date_of_expiry", sa.String(length=10), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mock_citizen_registry_document_number", "mock_citizen_registry", ["document_number"]
    )
    op.add_column("verifications", sa.Column("citizen_registry_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("verifications", "citizen_registry_json")
    op.drop_index("ix_mock_citizen_registry_document_number", table_name="mock_citizen_registry")
    op.drop_table("mock_citizen_registry")
