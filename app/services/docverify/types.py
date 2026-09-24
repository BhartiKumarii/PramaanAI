"""Shared result types for the modular document-verification pipeline.

Design rules encoded here (see CLAUDE.md "Hard ethical rules"):
  * There is no FAKE/REAL verdict anywhere. Every check returns one of the
    CheckStatus values below, and the overall result is derived from them.
  * Every non-PASS check carries a plain-language `summary` naming the exact
    field or region that triggered it, plus evidence ids pointing at image
    regions / compared values, so the officer can see *why*.
  * The officer makes the decision; these types only describe evidence.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CheckStatus(str, Enum):
    PASS = "PASS"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NOT_VERIFIED = "NOT_VERIFIED"
    REGISTRY_NOT_AVAILABLE = "REGISTRY_NOT_AVAILABLE"
    OFFICIAL_VERIFICATION_REQUIRED = "OFFICIAL_VERIFICATION_REQUIRED"
    REFERENCE_NOT_AVAILABLE = "REFERENCE_NOT_AVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    FAIL = "FAIL"


class DocumentType(str, Enum):
    INDIAN_PASSPORT = "INDIAN_PASSPORT"
    FOREIGN_PASSPORT = "FOREIGN_PASSPORT"
    INDIAN_VISA = "INDIAN_VISA"
    NEPAL_VISA = "NEPAL_VISA"
    BHUTAN_VISA = "BHUTAN_VISA"
    BHUTAN_ENTRY_PERMIT = "BHUTAN_ENTRY_PERMIT"
    DRIVING_LICENCE = "DRIVING_LICENCE"
    AADHAAR = "AADHAAR"
    VOTER_ID = "VOTER_ID"
    IDENTITY_DOCUMENT = "IDENTITY_DOCUMENT"
    OTHER_TRAVEL_DOCUMENT = "OTHER_TRAVEL_DOCUMENT"
    IMMIGRATION_STAMP = "IMMIGRATION_STAMP"
    DOCUMENT_TYPE_UNCERTAIN = "DOCUMENT_TYPE_UNCERTAIN"


PASSPORT_TYPES = {DocumentType.INDIAN_PASSPORT, DocumentType.FOREIGN_PASSPORT}
VISA_TYPES = {DocumentType.INDIAN_VISA, DocumentType.NEPAL_VISA, DocumentType.BHUTAN_VISA}


class RegionLabel(str, Enum):
    DOCUMENT = "DOCUMENT"
    PASSPORT = "PASSPORT"
    VISA = "VISA"
    DRIVING_LICENCE = "DRIVING_LICENCE"
    IDENTITY_DOCUMENT = "IDENTITY_DOCUMENT"
    ENTRY_PERMIT = "ENTRY_PERMIT"
    VISA_STICKER = "VISA_STICKER"
    STAMP = "STAMP"
    PHOTOGRAPH = "PHOTOGRAPH"
    QR_CODE = "QR_CODE"
    BARCODE = "BARCODE"
    MRZ = "MRZ"
    SECURITY_FEATURE = "SECURITY_FEATURE"
    SIGNATURE = "SIGNATURE"


class StampType(str, Enum):
    IMMIGRATION_STAMP = "IMMIGRATION_STAMP"
    VISA_STAMP = "VISA_STAMP"
    ENTRY_STAMP = "ENTRY_STAMP"
    EXIT_STAMP = "EXIT_STAMP"
    PERMIT_MARKING = "PERMIT_MARKING"
    UNKNOWN_STAMP = "UNKNOWN_STAMP"


class Region(BaseModel):
    """A detected image region. bbox is [x0, y0, x1, y1] in source pixels."""
    id: str
    label: RegionLabel
    bbox: list[int]
    confidence: float
    source: str  # e.g. "yolo11:<weights>" or "classical:qr-decoder" — always named honestly
    meta: dict[str, Any] = Field(default_factory=dict)


class OcrLine(BaseModel):
    text: str
    confidence: float
    bbox: list[int]


class FieldValue(BaseModel):
    value: str
    confidence: float
    source: str  # "ocr" | "mrz" | "qr" | "barcode" | "declared" | "device"
    bbox: list[int] | None = None
    raw: str | None = None


class Evidence(BaseModel):
    id: str
    check: str
    description: str
    region_id: str | None = None
    bbox: list[int] | None = None
    document_index: int | None = None
    values: dict[str, Any] = Field(default_factory=dict)


class CheckResult(BaseModel):
    name: str
    status: CheckStatus
    summary: str  # plain language, specific — never a bare score
    blocking: bool = True  # False = advisory; shown to the officer but doesn't drive overall status
    strong_evidence: bool = False  # deterministic check (checksum, registry, exact field compare)
    evidence_ids: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
    document_index: int | None = None


class DocumentTypeResult(BaseModel):
    document_type: DocumentType
    country: str | None
    confidence: float
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    basis: list[str] = Field(default_factory=list)


class StampResult(BaseModel):
    region_id: str
    stamp_type: StampType
    identification: str  # IDENTIFIED | PARTIALLY_IDENTIFIED | UNIDENTIFIED
    country: str | None = None
    authority: str | None = None
    checkpoint: str | None = None
    checkpoint_id: str | None = None
    checkpoint_type: str | None = None
    direction: str | None = None
    date: str | None = None
    visa_number: str | None = None
    permit_number: str | None = None
    reference_number: str | None = None
    ocr_text: str = ""
    ocr_confidence: float = 0.0
    detector_label: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    visual: dict[str, Any] = Field(default_factory=dict)  # shape/geometry/orientation/size/colour — descriptive only
    reference_match: str = "REFERENCE_NOT_AVAILABLE"
    forensic_indicators: list[dict[str, Any]] = Field(default_factory=list)
    bbox: list[int] | None = None
    confidence: float = 0.0


class MachineReadableCode(BaseModel):
    region_id: str
    symbology: str  # QR_CODE | EAN_13 | CODE_128 | ...
    decoded: bool
    payload_kind: str  # STRUCTURED | SIGNED_SECURE_QR | LEGACY_XML | TEXT | UNREADABLE
    fields: dict[str, str] = Field(default_factory=dict)
    raw_length: int = 0


class DocumentAnalysis(BaseModel):
    document_index: int
    image_sha256: str | None = None
    image_size: list[int] | None = None
    document_type: DocumentTypeResult
    template_version: str | None = None
    regions: list[Region] = Field(default_factory=list)
    ocr_lines: list[OcrLine] = Field(default_factory=list)
    ocr_confidence: float = 0.0
    # Extra lines read by the Devanagari (Nepali/Hindi) recogniser; the Latin
    # reading stays in ocr_lines. Empty when the stage did not run.
    native_lines: list[OcrLine] = Field(default_factory=list)
    fields: dict[str, FieldValue] = Field(default_factory=dict)
    mrz: dict[str, Any] | None = None
    codes: list[MachineReadableCode] = Field(default_factory=list)
    stamps: list[StampResult] = Field(default_factory=list)
    photo: dict[str, Any] | None = None
    security_features: list[dict[str, Any]] = Field(default_factory=list)
    tampering: dict[str, Any] | None = None
    quality: dict[str, Any] | None = None


class OfficerLine(BaseModel):
    icon: str  # "ok" | "warn" | "info" | "fail"
    text: str


class OfficerSummary(BaseModel):
    headline: str
    facts: dict[str, str]
    lines: list[OfficerLine]
    responsibility_notice: str = (
        "Decision-support only. The authorised SSB officer makes the final decision "
        "under existing procedure."
    )


class VerificationOutcome(BaseModel):
    id: str | None = None
    overall_status: CheckStatus
    country: str | None
    document_type: str
    checkpoint_type: str | None = None
    border_route: str | None = None
    # Problem-statement risk score (0-100). Always paired with the named
    # contributions in risk_breakdown — a risk indicator, never a verdict.
    confidence: float = 0.0  # how complete/reliable the evidence is — not a genuineness probability
    explanation: str = ""  # one plain-language sentence for the officer
    risk_score: int = 0
    risk_level: str = "LOW"
    risk_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    checks: dict[str, str]
    check_details: list[CheckResult]
    flags: list[str]
    advisories: list[str]
    evidence: list[Evidence]
    documents: list[DocumentAnalysis]
    cross_document: list[dict[str, Any]] = Field(default_factory=list)
    border_rules: dict[str, Any] | None = None
    officer_summary: OfficerSummary
    connectivity: str = "ONLINE"
    pipeline: dict[str, Any] = Field(default_factory=dict)
    advisory_explanation: dict[str, Any] | None = None
    # Pre-written, editable reasons for the officer's two actions, generated
    # deterministically from the checks (never by a model): "clear" and "send".
    suggested_reasons: dict[str, str] = Field(default_factory=dict)
    # Filled after persistence (not part of the hash-chained result): the
    # screening case this verification opened, and identity-graph findings.
    case: dict[str, Any] | None = None
    identity: dict[str, Any] | None = None
    data_notice: str = (
        "Registry lookups in this build use FICTIONAL mock data only — no real government "
        "database is accessed."
    )
    generated_at: str
