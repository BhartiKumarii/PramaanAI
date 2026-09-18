from pydantic import BaseModel, Field


class AuditEventResponse(BaseModel):
    id: str
    event_type: str
    actor_user_id: str
    actor_username: str | None = None
    reason: str | None
    created_at: str


class DisputeRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class AuditLogEntry(BaseModel):
    id: str
    event_type: str
    actor_user_id: str
    actor_username: str | None = None
    actor_role: str | None = None
    case_id: str | None = None
    case_number: str | None = None
    reason: str | None
    created_at: str
