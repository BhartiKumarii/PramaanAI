"""add stored_images table

Revision ID: e28403cb489a
Revises: 0016
Create Date: 2026-09-22 05:03:43.912218

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e28403cb489a'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'stored_images',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('verification_id', sa.Uuid(), nullable=False),
        sa.Column('image_type', sa.String(length=32), nullable=False),
        sa.Column('content_type', sa.String(length=64), nullable=False),
        sa.Column('data', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_stored_images_verification_id', 'stored_images', ['verification_id'])


def downgrade() -> None:
    op.drop_index('ix_stored_images_verification_id', table_name='stored_images')
    op.drop_table('stored_images')
