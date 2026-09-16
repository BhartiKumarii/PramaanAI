"""expand user roles, add checkpoints/devices/cases/network-graph tables

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-16

This is the schema for the BorderShieldAI pivot: Field Officer (Android)
scans -> Case created -> forwarded to Immigration Officer (web) -> decision
recorded, plus Supervisor/IT-Admin dashboards and a network-analysis graph.
VerificationRecord (renamed conceptually to "the analysis") is unchanged —
Case wraps it rather than replacing it, so existing screening code keeps
working.
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- user_role: OFFICER/ADMIN split into the four BorderShieldAI roles ---
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE user_role RENAME VALUE 'OFFICER' TO 'FIELD_OFFICER'")
        op.execute("ALTER TYPE user_role RENAME VALUE 'ADMIN' TO 'IT_ADMIN'")
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'IMMIGRATION_OFFICER'")

    # --- checkpoints ---
    op.create_table(
        "checkpoints",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(length=16), nullable=False, unique=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.add_column("users", sa.Column("checkpoint_id", sa.Uuid(), sa.ForeignKey("checkpoints.id"), nullable=True))

    # --- devices ---
    op.create_table(
        "devices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("device_identifier", sa.String(length=128), nullable=False, unique=True),
        sa.Column("officer_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("app_version", sa.String(length=32), nullable=True),
        sa.Column("is_disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- cases ---
    op.create_table(
        "cases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("case_number", sa.String(length=32), nullable=False, unique=True),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING_SYNC", "PENDING", "SENT", "REVIEW_REQUIRED", "CLEAR",
                "SECONDARY_REVIEW", "HOLD_REFER",
                name="case_status",
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "priority",
            sa.Enum("LOW", "MEDIUM", "HIGH", name="case_priority"),
            nullable=False,
            server_default="LOW",
        ),
        sa.Column("checkpoint_id", sa.Uuid(), sa.ForeignKey("checkpoints.id"), nullable=False),
        sa.Column("field_officer_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_officer_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verification_id", sa.Uuid(), sa.ForeignKey("verifications.id"), nullable=True),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("nationality", sa.String(length=64), nullable=False),
        sa.Column("traveler_name", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_cases_checkpoint_id", "cases", ["checkpoint_id"])
    op.create_index("ix_cases_field_officer_id", "cases", ["field_officer_id"])
    op.create_index("ix_cases_status", "cases", ["status"])

    op.create_table(
        "case_notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("author_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_case_notes_case_id", "case_notes", ["case_id"])

    op.create_table(
        "officer_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("officer_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_officer_decisions_case_id", "officer_decisions", ["case_id"])

    op.create_table(
        "sync_queue_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("device_id", sa.Uuid(), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- network graph ---
    op.create_table(
        "person_entities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("masked_document_number", sa.String(length=64), nullable=True),
        sa.Column("nationality", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "vehicle_entities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("plate_number", sa.String(length=32), nullable=False, unique=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "travel_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("person_id", sa.Uuid(), sa.ForeignKey("person_entities.id"), nullable=False),
        sa.Column("checkpoint_id", sa.Uuid(), sa.ForeignKey("checkpoints.id"), nullable=False),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("vehicle_id", sa.Uuid(), sa.ForeignKey("vehicle_entities.id"), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "network_relationships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "source_type",
            sa.Enum("PERSON", "DOCUMENT", "VEHICLE", "CHECKPOINT", "TRAVEL_EVENT", name="entity_type"),
            nullable=False,
        ),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column(
            "target_type",
            sa.Enum("PERSON", "DOCUMENT", "VEHICLE", "CHECKPOINT", "TRAVEL_EVENT", name="entity_type"),
            nullable=False,
        ),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_case_id", sa.Uuid(), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_network_relationships_source_id", "network_relationships", ["source_id"])
    op.create_index("ix_network_relationships_target_id", "network_relationships", ["target_id"])

    # --- audit_events: case-centric events, verification_id no longer required ---
    op.add_column("audit_events", sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id"), nullable=True))
    op.create_index("ix_audit_events_case_id", "audit_events", ["case_id"])
    op.alter_column("audit_events", "verification_id", nullable=True)


def downgrade() -> None:
    op.alter_column("audit_events", "verification_id", nullable=False)
    op.drop_index("ix_audit_events_case_id", table_name="audit_events")
    op.drop_column("audit_events", "case_id")

    op.drop_index("ix_network_relationships_target_id", table_name="network_relationships")
    op.drop_index("ix_network_relationships_source_id", table_name="network_relationships")
    op.drop_table("network_relationships")
    op.execute("DROP TYPE IF EXISTS entity_type")
    op.drop_table("travel_events")
    op.drop_table("vehicle_entities")
    op.drop_table("person_entities")

    op.drop_table("sync_queue_items")
    op.drop_index("ix_officer_decisions_case_id", table_name="officer_decisions")
    op.drop_table("officer_decisions")
    op.drop_index("ix_case_notes_case_id", table_name="case_notes")
    op.drop_table("case_notes")
    op.drop_index("ix_cases_status", table_name="cases")
    op.drop_index("ix_cases_field_officer_id", table_name="cases")
    op.drop_index("ix_cases_checkpoint_id", table_name="cases")
    op.drop_table("cases")
    op.execute("DROP TYPE IF EXISTS case_priority")
    op.execute("DROP TYPE IF EXISTS case_status")

    op.drop_table("devices")
    op.drop_column("users", "checkpoint_id")
    op.drop_table("checkpoints")

    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE user_role RENAME VALUE 'FIELD_OFFICER' TO 'OFFICER'")
        op.execute("ALTER TYPE user_role RENAME VALUE 'IT_ADMIN' TO 'ADMIN'")
        # Postgres can't remove an enum value directly; IMMIGRATION_OFFICER
        # is left in place on downgrade (harmless — nothing references it
        # once this migration's tables are gone).
