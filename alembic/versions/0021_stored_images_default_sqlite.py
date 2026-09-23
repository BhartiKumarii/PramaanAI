"""Fix stored_images.created_at default on SQLite.

The table was created with server_default=now(), a PostgreSQL function that
SQLite does not have, so every image upload failed on local SQLite
databases ("unknown function: now()"). Rebuilds the column default as
CURRENT_TIMESTAMP on SQLite; PostgreSQL is unaffected (no-op).

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        return
    with op.batch_alter_table("stored_images") as batch:
        batch.alter_column("created_at", existing_type=sa.DateTime(timezone=True),
                           server_default=sa.text("CURRENT_TIMESTAMP"), existing_nullable=True)


def downgrade() -> None:
    pass
