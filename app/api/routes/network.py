"""Network-analysis / identity-pattern graph: Person/Document/Vehicle/
Checkpoint/TravelEvent nodes with typed, evidenced edges (see
app/repositories/network_repository.py). All authenticated officers have full access.

Every relationship_type and explanation returned here must stay neutral
— "SHARED_DOCUMENT_NUMBER" / "SIMILAR_IDENTITY" are observations, not
conclusions. The frontend must never render these as an accusation, and
must never use words like "criminal" or "guilty" — see CLAUDE.md."""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.models.checkpoint import Checkpoint
from app.models.network import EntityType, PersonEntity, TravelEvent, VehicleEntity
from app.models.user import User
from app.repositories.network_repository import (
    list_relationships,
    person_for_case,
    relationships_for_entity,
    search_persons,
    travel_events_for_person,
)
from app.schemas.network import GraphEdge, GraphNode, NetworkGraphResponse, PersonSearchResult, RelationshipListItem

router = APIRouter(prefix="/network", tags=["network"])


def _resolve_node(db: Session, entity_type: EntityType, entity_id: uuid.UUID) -> GraphNode | None:
    if entity_type == EntityType.PERSON:
        row = db.get(PersonEntity, entity_id)
        if row is None:
            return None
        return GraphNode(
            id=str(row.id), type="PERSON", label=row.full_name,
            detail={"masked_document_number": row.masked_document_number, "nationality": row.nationality},
        )
    if entity_type == EntityType.CHECKPOINT:
        row = db.get(Checkpoint, str(entity_id))  # checkpoints.id is a hyphenated string
        if row is None:
            return None
        return GraphNode(id=str(row.id), type="CHECKPOINT", label=row.name, detail={"code": row.code})
    if entity_type == EntityType.VEHICLE:
        row = db.get(VehicleEntity, entity_id)
        if row is None:
            return None
        return GraphNode(id=str(row.id), type="VEHICLE", label=row.plate_number, detail={"description": row.description})
    if entity_type == EntityType.TRAVEL_EVENT:
        row = db.get(TravelEvent, entity_id)
        if row is None:
            return None
        return GraphNode(
            id=str(row.id), type="TRAVEL_EVENT", label=row.occurred_at.isoformat(),
            detail={"checkpoint_id": str(row.checkpoint_id)},
        )
    return None


def _build_graph(db: Session, center: GraphNode, entity_type: EntityType, entity_id: uuid.UUID) -> NetworkGraphResponse:
    nodes = {center.id: center}
    edges: list[GraphEdge] = []
    for rel in relationships_for_entity(db, entity_type, entity_id):
        other_type, other_id = (
            (rel.target_type, rel.target_id) if rel.source_id == entity_id else (rel.source_type, rel.source_id)
        )
        other_node = _resolve_node(db, other_type, other_id)
        if other_node is None:
            continue
        nodes[other_node.id] = other_node
        edges.append(
            GraphEdge(
                id=str(rel.id), source=str(rel.source_id), target=str(rel.target_id),
                relationship_type=rel.relationship_type, explanation=rel.explanation or "",
                evidence_case_id=str(rel.evidence_case_id) if rel.evidence_case_id else None,
                created_at=rel.created_at.isoformat(),
            )
        )
    return NetworkGraphResponse(nodes=list(nodes.values()), edges=edges)


@router.get("/cases/{case_id}", response_model=NetworkGraphResponse, summary="Relationship graph centered on this case's traveler")
def get_case_graph(case_id: uuid.UUID, _user: User = Depends(require_role()), db: Session = Depends(get_db)) -> NetworkGraphResponse:
    person = person_for_case(db, case_id)
    if person is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no network entity recorded for this case")
    center = _resolve_node(db, EntityType.PERSON, person.id)
    graph = _build_graph(db, center, EntityType.PERSON, person.id)

    # Always include the checkpoint(s) this person has actually crossed,
    # even where no NetworkRelationship row exists for it — a travel
    # history is real graph structure, not an "association" to hide.
    known_node_ids = {n.id for n in graph.nodes}
    for event in travel_events_for_person(db, person.id):
        checkpoint_node = _resolve_node(db, EntityType.CHECKPOINT, event.checkpoint_id)
        if checkpoint_node is None:
            continue
        if checkpoint_node.id not in known_node_ids:
            graph.nodes.append(checkpoint_node)
            known_node_ids.add(checkpoint_node.id)
        graph.edges.append(
            GraphEdge(
                id=str(event.id), source=str(person.id), target=str(event.checkpoint_id),
                relationship_type="CROSSED_CHECKPOINT", explanation=f"Crossed on {event.occurred_at.date().isoformat()}",
                evidence_case_id=str(event.case_id) if event.case_id else None,
                created_at=event.occurred_at.isoformat(),
            )
        )
    return graph


@router.get("/persons/search", response_model=list[PersonSearchResult], summary="Search declared identities by name")
def search_persons_route(
    q: str, limit: int = 20, _user: User = Depends(require_role()), db: Session = Depends(get_db)
) -> list[PersonSearchResult]:
    if not q or not q.strip():
        return []
    rows = search_persons(db, q, limit=limit)
    return [
        PersonSearchResult(
            id=str(p.id), full_name=p.full_name, masked_document_number=p.masked_document_number,
            nationality=p.nationality, created_at=p.created_at.isoformat(),
        )
        for p in rows
    ]


@router.get("/entities/{entity_id}", response_model=NetworkGraphResponse, summary="Expand relationships for one graph node")
def get_entity_graph(
    entity_id: uuid.UUID, entity_type: str,
    _user: User = Depends(require_role()), db: Session = Depends(get_db),
) -> NetworkGraphResponse:
    try:
        parsed_type = EntityType(entity_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid entity_type: {entity_type}") from exc
    center = _resolve_node(db, parsed_type, entity_id)
    if center is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="entity not found")
    return _build_graph(db, center, parsed_type, entity_id)


@router.get("/relationships", response_model=list[RelationshipListItem], summary="Filterable list of all recorded relationships")
def list_relationships_route(
    checkpoint_id: uuid.UUID | None = None,
    relationship_type: str | None = None,
    since: date | None = None,
    limit: int = 100,
    _user: User = Depends(require_role()), db: Session = Depends(get_db),
) -> list[RelationshipListItem]:
    limit = max(1, min(limit, 500))
    rows = list_relationships(db, checkpoint_id=checkpoint_id, relationship_type=relationship_type, since=since, limit=limit)
    return [
        RelationshipListItem(
            id=str(r.id), source_type=r.source_type.value, source_id=str(r.source_id),
            target_type=r.target_type.value, target_id=str(r.target_id),
            relationship_type=r.relationship_type, explanation=r.explanation or "",
            evidence_case_id=str(r.evidence_case_id) if r.evidence_case_id else None,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]