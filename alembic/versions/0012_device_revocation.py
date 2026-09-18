"""add revoked_at/revoked_reason to devices

A "Revoked Devices" state distinct from the existing is_disabled
toggle — see app/models/device.py's docstring.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("devices", sa.Column("revoked_reason", sa.String(length=256), nullable=True))


def downgrade() -> None:
    op.drop_column("devices", "revoked_reason")
    op.drop_column("devices", "revoked_at")
