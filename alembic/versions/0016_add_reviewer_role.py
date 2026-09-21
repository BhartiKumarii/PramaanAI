"""Add REVIEWER to user_role enum and create demo reviewer account

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite stores enums as VARCHAR and does not enforce CHECK constraints from
    # SQLAlchemy's Enum type, so we only need to handle PostgreSQL here.
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'REVIEWER'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed without recreating the type.
    # For SQLite there is nothing to revert.
    pass
