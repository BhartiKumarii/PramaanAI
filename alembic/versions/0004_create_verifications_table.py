"""create verifications table

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "verifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("nationality", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("top_reason", sa.Text(), nullable=False),
        sa.Column("breakdown_json", sa.Text(), nullable=False),
        sa.Column("signature", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("verifications")
