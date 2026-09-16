from pydantic import BaseModel


class SystemHealthResponse(BaseModel):
    api_status: str
    database_status: str
    # OCR/face/tampering/etc. run in-process, not as a separate monitored
    # service — labeled honestly as such rather than implying an
    # independent health check that doesn't exist.
    analysis_pipeline_status: str
    checked_at: str


class SyncStatusResponse(BaseModel):
    pending: int
    synced: int
    failed: int
    last_successful_sync_at: str | None = None
