"""Identity graph result types — Module: real connected-component
detection over stored face embeddings, flagging the same face registered
under more than one declared identity."""
from pydantic import BaseModel


class IdentityClusterMember(BaseModel):
    record_id: str
    reference_name: str
    document_number: str | None


class IdentityGraphResult(BaseModel):
    status: str  # CLUSTER_FOUND | NO_CLUSTER
    cluster_size: int
    members: list[IdentityClusterMember]
    reason: str
    location: None = None  # not spatially applicable — a cross-record graph finding
