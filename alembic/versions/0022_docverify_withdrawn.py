"""Mark a document verification as withdrawn (e.g. synthetic test data).

A withdrawn record stays in the tamper-evident chain — deleting or editing it
would break every later link — but is hidden from lists and counts. The flag
is not part of record_hash.

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("document_verifications") as batch:
        batch.add_column(sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("withdrawn_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("document_verifications") as batch:
        batch.drop_column("withdrawn_reason")
        batch.drop_column("withdrawn_at")
