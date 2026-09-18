"""add duplicate_document_json to verifications

Persists the real duplicate/reused-document check result (see
app/services/duplicate/) alongside the other per-signal JSON columns.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("verifications", sa.Column("duplicate_document_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("verifications", "duplicate_document_json")
