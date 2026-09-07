"""add traveler_name to verifications

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Informational only — never part of the HMAC-signed payload, so this
    # doesn't touch signature verification for existing rows. Nullable
    # because OCR doesn't always find a name field.
    op.add_column("verifications", sa.Column("traveler_name", sa.String(length=256), nullable=True))


def downgrade() -> None:
    op.drop_column("verifications", "traveler_name")
