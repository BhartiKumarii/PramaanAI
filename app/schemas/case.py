from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.verification import VerificationRecordResponse

DecisionValue = Literal["CLEAR", "SECONDARY_REVIEW", "HOLD_REFER"]


class CaseListItemResponse(BaseModel):
    id: str
    case_number: str
    status: str
    priority: str
    checkpoint_code: str
    field_officer_username: str
    assigned_officer_username: str | None = None
    document_type: str
    nationality: str
    traveler_name: str | None = None
    created_at: str
    sent_at: str | None = None
    risk_level: str | None = None
    risk_score: int | None = None


class CaseDecisionSummary(BaseModel):
    decision: str
    officer_username: str | None = None
    reason: str | None = None
    created_at: str


class CaseNoteResponse(BaseModel):
    id: str
    author_username: str | None = None
    note: str
    created_at: str


class CaseDetailResponse(CaseListItemResponse):
    verification: VerificationRecordResponse | None = None
    notes: list[CaseNoteResponse] = Field(default_factory=list)
    decisions: list[CaseDecisionSummary] = Field(default_factory=list)
    decided_at: str | None = None


class CaseSubmitRequest(BaseModel):
    note: str | None = None


class CaseDecisionRequest(BaseModel):
    decision: DecisionValue
    reason: str | None = None


class CaseAssignRequest(BaseModel):
    officer_id: str | None = None
    priority: Literal["LOW", "MEDIUM", "HIGH"] | None = None


class CaseNoteRequest(BaseModel):
    note: str = Field(..., min_length=1)


class CaseTimelineEvent(BaseModel):
    event_type: str
    action: str  # human-readable label
    actor_username: str | None = None
    detail: str | None = None
    created_at: str
