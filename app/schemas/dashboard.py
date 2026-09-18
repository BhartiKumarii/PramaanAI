from pydantic import BaseModel


class ImmigrationDashboardResponse(BaseModel):
    new_cases: int
    pending_review: int
    high_priority: int
    cleared_cases: int


class CheckpointBreakdown(BaseModel):
    checkpoint_code: str
    pending: int
    cleared: int
    review_required: int


class SupervisorDashboardResponse(BaseModel):
    total_scans: int
    pending_cases: int
    review_required: int
    high_priority_supervisor: int
    active_officers: int
    avg_processing_time_seconds: float | None = None
    offline_sync_queue: int
    checkpoint_breakdown: list[CheckpointBreakdown]


class AdminDashboardResponse(BaseModel):
    registered_users: int
    registered_devices: int
    sync_queue_pending: int


class AnalyticsBucket(BaseModel):
    key: str
    count: int


class AnalyticsDashboardResponse(BaseModel):
    total_screenings: int
    by_document_type: list[AnalyticsBucket]
    by_decision: list[AnalyticsBucket]
    by_risk_level: list[AnalyticsBucket]
    by_day: list[AnalyticsBucket]


class UnifiedDashboardResponse(BaseModel):
    """Combined dashboard response for single OFFICER role with full access"""
    # Immigration dashboard fields
    new_cases: int
    pending_review: int
    high_priority: int
    cleared_cases: int
    # Supervisor dashboard fields
    total_scans: int
    pending_cases: int
    review_required: int
    high_priority_supervisor: int
    active_officers: int
    avg_processing_time_seconds: float | None = None
    offline_sync_queue: int
    checkpoint_breakdown: list[CheckpointBreakdown]
    # Admin dashboard fields
    registered_users: int
    registered_devices: int
    sync_queue_pending: int
    # Analytics dashboard fields
    total_screenings: int
    by_document_type: list[AnalyticsBucket]
    by_decision: list[AnalyticsBucket]
    by_risk_level: list[AnalyticsBucket]
    by_day: list[AnalyticsBucket]