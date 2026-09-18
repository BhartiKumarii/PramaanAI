"""Network-graph persistence: person/vehicle/travel-event nodes plus a
generic typed-edge relationship table (see app/models/network.py for the
design rationale). Relationship detection here is intentionally limited
to two concrete, explainable signals — matching document number, and the
existing face-embedding cluster from identity_graph — never a vague
"connected" inference. Every edge carries `explanation` and
`evidence_case_id` so the web console can show *why*, not just *that*."""
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.network import EntityType, NetworkRelationship, PersonEntity, TravelEvent
from app.utils.masking import hash_document_number, mask_document_number


def get_or_create_person(
    db: Session,
    full_name: str | None,
    raw_document_number: str | None,
    nationality: str | None,
) -> PersonEntity:
    """Every screening gets its own PersonEntity node — a declared
    identity as of that case, not a pre-merged "real person" record.
    Two cases genuinely being the same traveler is exactly what
    SAME_DOCUMENT_NUMBER / SIMILAR_IDENTITY edges are for: an explicit,
    explained graph relationship an officer can inspect, rather than a
    silent merge that would hide the fact there were two screenings."""
    doc_hash = hash_document_number(raw_document_number) if raw_document_number else None
    person = PersonEntity(
        full_name=full_name or "UNKNOWN",
        masked_document_number=mask_document_number(raw_document_number) if raw_document_number else None,
        document_number_hash=doc_hash,
        nationality=nationality,
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


def record_travel_event(
    db: Session, person_id: uuid.UUID, checkpoint_id: uuid.UUID, case_id: uuid.UUID | None
) -> TravelEvent:
    event = TravelEvent(person_id=person_id, checkpoint_id=checkpoint_id, case_id=case_id)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def person_for_case(db: Session, case_id: uuid.UUID) -> PersonEntity | None:
    event = db.execute(select(TravelEvent).where(TravelEvent.case_id == case_id)).scalar_one_or_none()
    if event is None:
        return None
    return db.get(PersonEntity, event.person_id)


def find_persons_by_document_hash(
    db: Session, document_number_hash: str, exclude_person_id: uuid.UUID | None = None
) -> list[PersonEntity]:
    stmt = select(PersonEntity).where(PersonEntity.document_number_hash == document_number_hash)
    if exclude_person_id is not None:
        stmt = stmt.where(PersonEntity.id != exclude_person_id)
    return list(db.execute(stmt).scalars())


def _relationship_exists(
    db: Session, source_id: uuid.UUID, target_id: uuid.UUID, relationship_type: str
) -> bool:
    stmt = select(NetworkRelationship).where(
        NetworkRelationship.relationship_type == relationship_type,
        (
            ((NetworkRelationship.source_id == source_id) & (NetworkRelationship.target_id == target_id))
            | ((NetworkRelationship.source_id == target_id) & (NetworkRelationship.target_id == source_id))
        ),
    )
    return db.execute(stmt).first() is not None


def record_relationship(
    db: Session,
    source_type: EntityType,
    source_id: uuid.UUID,
    target_type: EntityType,
    target_id: uuid.UUID,
    relationship_type: str,
    evidence_case_id: uuid.UUID | None,
    explanation: str,
) -> NetworkRelationship | None:
    if source_id == target_id or _relationship_exists(db, source_id, target_id, relationship_type):
        return None
    relationship = NetworkRelationship(
        source_type=source_type, source_id=source_id, target_type=target_type, target_id=target_id,
        relationship_type=relationship_type, evidence_case_id=evidence_case_id, explanation=explanation,
    )
    db.add(relationship)
    db.commit()
    db.refresh(relationship)
    return relationship


def relationships_for_entity(db: Session, entity_type: EntityType, entity_id: uuid.UUID) -> list[NetworkRelationship]:
    stmt = select(NetworkRelationship).where(
        ((NetworkRelationship.source_type == entity_type) & (NetworkRelationship.source_id == entity_id))
        | ((NetworkRelationship.target_type == entity_type) & (NetworkRelationship.target_id == entity_id))
    )
    return list(db.execute(stmt).scalars())


def travel_events_for_person(db: Session, person_id: uuid.UUID) -> list[TravelEvent]:
    return list(
        db.execute(
            select(TravelEvent).where(TravelEvent.person_id == person_id).order_by(TravelEvent.occurred_at.desc())
        ).scalars()
    )


def search_persons(db: Session, query: str, limit: int = 20) -> list[PersonEntity]:
    """Name search across every declared identity the graph has seen —
    the backing query for "Person Search". Matches on `full_name` only:
    document numbers are never stored in searchable plaintext (see
    `hash_document_number`), so a document-number search isn't offered
    here — only an exact-hash lookup could ever answer that honestly,
    and that's what the registry lookup / SAME_DOCUMENT_NUMBER edges are
    for."""
    limit = max(1, min(limit, 100))
    stmt = (
        select(PersonEntity)
        .where(PersonEntity.full_name.ilike(f"%{query.strip()}%"))
        .order_by(PersonEntity.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())


def list_relationships(
    db: Session,
    *,
    checkpoint_id: uuid.UUID | None = None,
    relationship_type: str | None = None,
    since: date | None = None,
    limit: int = 100,
) -> list[NetworkRelationship]:
    stmt = select(NetworkRelationship)
    if relationship_type is not None:
        stmt = stmt.where(NetworkRelationship.relationship_type == relationship_type)
    if since is not None:
        stmt = stmt.where(NetworkRelationship.created_at >= since)
    if checkpoint_id is not None:
        stmt = stmt.join(Case, Case.id == NetworkRelationship.evidence_case_id).where(
            Case.checkpoint_id == checkpoint_id
        )
    stmt = stmt.order_by(NetworkRelationship.created_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars())
