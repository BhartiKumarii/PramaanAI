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
    high_priority: int
    active_officers: int
    avg_processing_time_seconds: float | None = None
    offline_sync_queue: int
    checkpoint_breakdown: list[CheckpointBreakdown]


class AdminDashboardResponse(BaseModel):
    registered_users: int
    registered_devices: int
    sync_queue_pending: int
