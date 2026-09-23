"""Link a document verification to the screening case it opened.

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("document_verifications") as batch:
        batch.add_column(sa.Column("case_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("screening_verification_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("identity_json", sa.Text(), nullable=True))
        batch.create_index("ix_document_verifications_case_id", ["case_id"])


def downgrade() -> None:
    with op.batch_alter_table("document_verifications") as batch:
        batch.drop_index("ix_document_verifications_case_id")
        batch.drop_column("identity_json")
        batch.drop_column("screening_verification_id")
        batch.drop_column("case_id")
