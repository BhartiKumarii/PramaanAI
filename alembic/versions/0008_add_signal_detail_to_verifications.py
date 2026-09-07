"""persist raw per-signal detail on verifications

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# Raw signal outputs computed during /documents/screen were only ever
# returned in that one response, never persisted — so re-fetching a
# verification (from another device, or after this device's local cache is
# gone) could only recover the fused score, not the evidence behind it.
# All nullable and none part of the HMAC-signed payload: purely additive
# detail, doesn't change what's cryptographically attested.
_COLUMNS = [
    "ocr_json",
    "validation_json",
    "tampering_json",
    "deepfake_json",
    "registry_json",
    "face_json",
    "identity_graph_json",
    "liveness_json",
]


def upgrade() -> None:
    for name in _COLUMNS:
        op.add_column("verifications", sa.Column(name, sa.Text(), nullable=True))


def downgrade() -> None:
    for name in _COLUMNS:
        op.drop_column("verifications", name)
