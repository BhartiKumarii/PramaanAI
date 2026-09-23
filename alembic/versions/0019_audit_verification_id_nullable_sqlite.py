"""Make audit_events.verification_id nullable on SQLite too.

Revision 0009 relaxed this column with op.alter_column, which SQLite does not
support (the change silently did nothing there), so local SQLite databases
kept NOT NULL and case-/document-verification audit events without a
screening verification id failed to insert. Batch mode rebuilds the table on
SQLite; on PostgreSQL the column is already nullable and this is a no-op.

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        return
    with op.batch_alter_table("audit_events") as batch:
        batch.alter_column("verification_id", existing_type=sa.CHAR(32), nullable=True)


def downgrade() -> None:
    # Intentionally not re-tightened: rows written since then may be NULL.
    pass
