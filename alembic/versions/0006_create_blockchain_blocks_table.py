"""create blockchain_blocks table

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "blockchain_blocks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("verification_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("issuer_reference", sa.String(length=255), nullable=False),
        sa.Column("document_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("block_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_blockchain_blocks_verification_id", "blockchain_blocks", ["verification_id"])


def downgrade() -> None:
    op.drop_index("ix_blockchain_blocks_verification_id", table_name="blockchain_blocks")
    op.drop_table("blockchain_blocks")
