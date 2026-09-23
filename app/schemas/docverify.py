"""Request/response schemas for /api/v1 document verification."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

BorderRoute = Literal["INDIA_NEPAL", "INDIA_BHUTAN"]
Direction = Literal["INDIA_TO_NEPAL", "NEPAL_TO_INDIA", "INDIA_TO_BHUTAN", "BHUTAN_TO_INDIA"]
RegionCropLabel = Literal["photograph", "mrz", "qr_code", "barcode", "stamp", "yellow_gold_feature", "text"]

MAX_B64_CHARS = 4_000_000  # ~3 MB per crop


class RegionCrop(BaseModel):
    """One region the device's on-board detector located. `crop_bbox` is the
    padded area actually sent (the detector box plus a margin of at least
    40% of its longest side, so region-vs-surroundings forensics has real
    surroundings); `bbox` is the tight detector box. Both are in the
    original image's pixel coordinates."""
    label: RegionCropLabel
    bbox: list[int] = Field(min_length=4, max_length=4)
    crop_bbox: list[int] = Field(min_length=4, max_length=4)
    confidence: float = Field(default=0.5, ge=0, le=1)
    image_b64: str = Field(max_length=MAX_B64_CHARS)


class RegionDocument(BaseModel):
    image_size: list[int] = Field(min_length=2, max_length=2)
    regions: list[RegionCrop] = Field(min_length=1, max_length=40)
    device_detector: str | None = Field(default=None, max_length=80)
    quality: dict[str, Any] | None = None

    @field_validator("image_size")
    @classmethod
    def _size(cls, v: list[int]) -> list[int]:
        if not (100 <= v[0] <= 8000 and 100 <= v[1] <= 8000):
            raise ValueError("image_size out of range")
        return v


class DeviceTextLine(BaseModel):
    """A line of text the phone's own OCR (ML Kit) read, in original-image
    pixels. Used only to fill fields the server could not read (labelled
    source "device") and to report disagreements — never over the server's
    own reading."""
    document_index: int = Field(default=0, ge=0, le=3)
    text: str = Field(min_length=1, max_length=300)
    bbox: list[int] = Field(min_length=4, max_length=4)
    confidence: float = Field(default=0.8, ge=0, le=1)


class RegionVerificationRequest(BaseModel):
    """ONE request carries every crop of every document (1-4 documents), so
    the device makes a single HTTPS round trip per verification."""
    documents: list[RegionDocument] = Field(min_length=1, max_length=4)
    client_request_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    live_face_b64: str | None = Field(default=None, max_length=MAX_B64_CHARS)
    border_route: BorderRoute | None = None
    direction: Direction | None = None
    declared_nationality: str | None = Field(default=None, max_length=40)
    travel_date: date | None = None
    captured_offline: bool = False
    device_id: str | None = Field(default=None, max_length=128)
    captured_at: datetime | None = None
    # Screening workflow: the document type the officer chose, the phone's
    # OCR lines, and whether to open a screening case for review/decision.
    expected_document_type: str | None = Field(default=None, max_length=40)
    device_text: list[DeviceTextLine] = Field(default_factory=list, max_length=400)
    open_case: bool = False


class ExtractedVerificationRequest(BaseModel):
    """Extracted data only (no pixels) — used when a device submits a case
    that was processed fully on-device (e.g. queued while offline)."""
    documents: list[dict[str, Any]] = Field(min_length=1, max_length=4)
    client_request_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    border_route: BorderRoute | None = None
    direction: Direction | None = None
    declared_nationality: str | None = Field(default=None, max_length=40)
    travel_date: date | None = None
    captured_offline: bool = False
    device_id: str | None = Field(default=None, max_length=128)
    captured_at: datetime | None = None
    device_checks: dict[str, Any] | None = None


OfficerActionValue = Literal["CLEARED", "SEND_TO_OFFICER", "REFERRED_FOR_SECONDARY_INSPECTION", "RECAPTURE_REQUESTED",
                             "OFFICIAL_VERIFICATION_REQUESTED"]


class OfficerActionRequest(BaseModel):
    action: OfficerActionValue
    reason: str | None = Field(default=None, max_length=2000)

    @field_validator("reason")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return v.strip() if v else v


class VerificationListItem(BaseModel):
    id: str
    sequence: int
    created_at: datetime
    source: str
    document_types: list[str]
    country: str | None
    border_route: str | None
    overall_status: str
    risk_score: int
    risk_level: str
    officer_action: str
    sync_status: str
    captured_offline: bool
    # Screening case linked to this verification (no personal fields).
    case_id: str | None = None
    case_number: str | None = None
    case_status: str | None = None
    reviewer_responded: bool = False
    last_update_at: datetime | None = None
    # Names of checks that needed attention (no personal data) — for analytics.
    attention_checks: list[str] = Field(default_factory=list)


class VerificationRecordEnvelope(BaseModel):
    record: VerificationListItem
    integrity: dict[str, bool]
    officer_action: dict[str, Any]
    result: dict[str, Any]
