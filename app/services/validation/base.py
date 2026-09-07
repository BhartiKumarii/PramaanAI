"""Document validation engine interface — Module 2: MRZ checksum,
Verhoeff (Aadhaar) checksum, and front/back cross-validation."""
from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.services.validation.mrz import MRZResult


class ValidationFinding(BaseModel):
    check: str
    status: str  # PASS | FAIL
    severity: str  # LOW | MEDIUM | HIGH
    reason: str  # specific values involved, never a generic string
    location: dict | None = None  # bounding box, or null when not spatial


class ValidationResult(BaseModel):
    status: str  # PASS | FAIL
    findings: list[ValidationFinding]


class ValidationEngine(ABC):
    @abstractmethod
    def validate(
        self,
        ocr_result: dict,
        mrz_result: MRZResult | None = None,
        nationality: str | None = None,
        aadhaar_number: str | None = None,
    ) -> ValidationResult:
        """Cross-check OCR/MRZ fields, formats, expiry, and consistency.
        Branches on `nationality`: Indian nationals get Verhoeff (Aadhaar)
        checksum validation via `aadhaar_number`; others get MRZ/ICAO 9303
        validation via `mrz_result`."""
