"""add face_detection_json to verifications

Persists the real face-presence/count/position check result (see
app/services/face/yunet_detector.py and FaceDetectionAnalyzer.kt).

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("verifications", sa.Column("face_detection_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("verifications", "face_detection_json")
