"""Concrete validation engine (Module 2): expiry check, nationality-aware
checksum validation (MRZ/ICAO 9303 for foreign nationals, Verhoeff/Aadhaar
for Indian nationals), and front/back cross-validation. Every finding
carries a real reason built from the actual values compared — nothing
here is a hardcoded pass.
"""
import re
from datetime import date

from app.services.validation.base import ValidationEngine, ValidationFinding, ValidationResult
from app.services.validation.cross_check import cross_validate
from app.services.validation.mrz import MRZResult
from app.services.validation.verhoeff import VerhoeffFormatError, validate_verhoeff

_DDMMYYYY = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")


def _parse_ddmmyyyy(date_str: str) -> date | None:
    match = _DDMMYYYY.match(date_str.strip())
    if not match:
        return None
    day, month, year = match.groups()
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


class DefaultValidationEngine(ValidationEngine):
    def validate(
        self,
        ocr_result: dict,
        mrz_result: MRZResult | None = None,
        nationality: str | None = None,
        aadhaar_number: str | None = None,
    ) -> ValidationResult:
        findings: list[ValidationFinding] = []

        findings.append(self._check_expiry(ocr_result))

        # Nationality decides which document a checkpoint *expects*
        # (Aadhaar for Indian nationals, MRZ for foreign nationals), but
        # both checks run whenever their evidence is actually supplied —
        # an Indian national presenting a passport still has a real MRZ
        # that must validate; nationality shouldn't suppress that.
        if aadhaar_number:
            findings.append(self._check_verhoeff(aadhaar_number))
        if mrz_result is not None:
            findings.extend(self._check_mrz(mrz_result))

        if mrz_result is not None:
            findings.extend(cross_validate(ocr_result, mrz_result))

        overall = "FAIL" if any(f.status == "FAIL" for f in findings) else "PASS"
        return ValidationResult(status=overall, findings=findings)

    def _check_expiry(self, ocr_result: dict) -> ValidationFinding:
        expiry_str = ocr_result.get("date_of_expiry")
        if not expiry_str:
            return ValidationFinding(
                check="expiry",
                status="FAIL",
                severity="MEDIUM",
                reason="no date_of_expiry field was extracted from the document",
            )
        expiry_date = _parse_ddmmyyyy(expiry_str)
        if expiry_date is None:
            return ValidationFinding(
                check="expiry",
                status="FAIL",
                severity="MEDIUM",
                reason=f"date_of_expiry {expiry_str!r} is not in DD/MM/YYYY format",
            )
        today = date.today()
        expired = expiry_date < today
        return ValidationFinding(
            check="expiry",
            status="FAIL" if expired else "PASS",
            severity="HIGH" if expired else "LOW",
            reason=f"document expiry {expiry_date.isoformat()} vs today {today.isoformat()}: "
            + ("expired" if expired else "not expired"),
        )

    def _check_verhoeff(self, aadhaar_number: str) -> ValidationFinding:
        digits_only = aadhaar_number.replace(" ", "")
        try:
            valid = len(digits_only) == 12 and validate_verhoeff(digits_only)
        except VerhoeffFormatError as exc:
            return ValidationFinding(
                check="aadhaar_checksum",
                status="FAIL",
                severity="HIGH",
                reason=f"Aadhaar number {aadhaar_number!r} is not valid for Verhoeff checksumming: {exc}",
            )
        return ValidationFinding(
            check="aadhaar_checksum",
            status="PASS" if valid else "FAIL",
            severity="LOW" if valid else "HIGH",
            reason=f"Aadhaar number {digits_only} Verhoeff checksum: "
            + ("valid" if valid else "invalid — checksum digit does not match"),
        )

    def _check_mrz(self, mrz_result: MRZResult) -> list[ValidationFinding]:
        findings = []
        for check_digit in mrz_result.check_digits:
            findings.append(
                ValidationFinding(
                    check=f"mrz_checksum_{check_digit.field}",
                    status="PASS" if check_digit.valid else "FAIL",
                    severity="LOW" if check_digit.valid else "HIGH",
                    reason=(
                        f"MRZ field {check_digit.field}={check_digit.value!r}: printed check "
                        f"digit {check_digit.printed_check_digit!r}, computed "
                        f"{check_digit.computed_check_digit}: "
                        + ("valid" if check_digit.valid else "invalid — checksum mismatch")
                    ),
                )
            )
        return findings
