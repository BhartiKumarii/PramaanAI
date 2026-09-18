from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    type: str  # PERSON | DOCUMENT | VEHICLE | CHECKPOINT | TRAVEL_EVENT
    label: str
    detail: dict = {}


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship_type: str
    explanation: str
    evidence_case_id: str | None = None
    created_at: str


class NetworkGraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class RelationshipListItem(BaseModel):
    id: str
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    relationship_type: str
    explanation: str
    evidence_case_id: str | None = None
    created_at: str


class PersonSearchResult(BaseModel):
    id: str
    full_name: str
    masked_document_number: str | None = None
    nationality: str | None = None
    created_at: str


class IdentityHistoryRecord(BaseModel):
    record_id: str
    case_id: str | None = None
    case_number: str | None = None
    checkpoint_code: str | None = None
    declared_name: str
    masked_document_number: str | None = None
    occurred_at: str | None = None
    similarity: float | None = None  # only set when directly compared to the current record
    review_status: str | None = None
