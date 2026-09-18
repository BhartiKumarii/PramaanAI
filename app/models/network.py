"""Entities and relationships for the network-analysis graph.

Design choice: rather than a separate join table per node-type pair
(person-vehicle, person-checkpoint, ...), `NetworkRelationship` is one
generic edge table keyed by (type, id) on each side. That's enough to
render the graph (Person / Document / Vehicle / Checkpoint / TravelEvent
nodes, typed edges) for a demo without a combinatorial schema — see
CLAUDE.md's identity-graph guidance ("a simple pairwise loop is enough").

Every edge is evidence-linked (`evidence_case_id`), and relationship_type
values must stay neutral (e.g. "SHARED_VEHICLE", "SAME_DOCUMENT_NUMBER")
— never a label implying guilt. A graph edge is not proof of anything by
itself; the case-review page is where a human makes that call.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class EntityType(str, enum.Enum):
    PERSON = "PERSON"
    DOCUMENT = "DOCUMENT"
    VEHICLE = "VEHICLE"
    CHECKPOINT = "CHECKPOINT"
    TRAVEL_EVENT = "TRAVEL_EVENT"


class PersonEntity(Base):
    """A canonical person record the graph can point at. Distinct from
    `User` (system accounts) and `IdentityEmbeddingRecord` (raw face
    vectors) — this is the node the officer-facing UI shows."""

    __tablename__ = "person_entities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Masked at write time (e.g. "P***4567") — never the full number.
    masked_document_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # SHA-256 of the normalized raw number — lets us detect "this same
    # document number was used before" without ever storing or exposing
    # the plaintext number itself (see app/utils/masking.py).
    document_number_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    nationality: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class VehicleEntity(Base):
    __tablename__ = "vehicle_entities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    plate_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TravelEvent(Base):
    """One person's crossing of one checkpoint at one time — the graph's
    time-anchored node, linking a person to a checkpoint (and optionally
    a case and a vehicle, for batch/group crossings)."""

    __tablename__ = "travel_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("person_entities.id"), nullable=False)
    checkpoint_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("checkpoints.id"), nullable=False)
    case_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("cases.id"), nullable=True)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("vehicle_entities.id"), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NetworkRelationship(Base):
    """A typed, evidenced edge between two entities. `relationship_type`
    is a neutral description of what was observed (e.g.
    "SHARED_VEHICLE", "SIMILAR_IDENTITY", "SAME_CHECKPOINT_SEQUENCE"),
    never a conclusion about the people involved."""

    __tablename__ = "network_relationships"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_type: Mapped[EntityType] = mapped_column(Enum(EntityType, name="entity_type"), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    target_type: Mapped[EntityType] = mapped_column(Enum(EntityType, name="entity_type"), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_case_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("cases.id"), nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
