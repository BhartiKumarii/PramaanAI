"""create audit_events table

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("verification_id", sa.Uuid(), sa.ForeignKey("verifications.id"), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_events_verification_id", "audit_events", ["verification_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_verification_id", table_name="audit_events")
    op.drop_table("audit_events")
