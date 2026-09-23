"""Document validation engine interface — Module 2: MRZ checksum,
Verhoeff (Aadhaar) checksum, and front/back cross-validation."""
from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.services.validation.mrz import MRZResult


class ValidationFinding(BaseModel):
    check: str
    status: str  # PASS | FAIL | NOT_AVAILABLE | UNCERTAIN | NOT_EVALUATED
    severity: str  # LOW | MEDIUM | HIGH | INFO
    reason: str  # specific values involved, never a generic string
    location: dict | None = None  # bounding box, or null when not spatial


class ValidationResult(BaseModel):
    status: str  # PASS | FAIL | UNCERTAIN
    findings: list[ValidationFinding]


class ValidationEngine(ABC):
    @abstractmethod
    def validate(
        self,
        ocr_result: dict,
        mrz_result: MRZResult | None = None,
        nationality: str | None = None,
        aadhaar_number: str | None = None,
        document_type: str = "passport",
        registry_hits: list | None = None,
    ) -> ValidationResult:
        """Comprehensive document validation: field presence, format checks,
        date logic, MRZ/Verhoeff checksums, cross-validation, and registry."""
