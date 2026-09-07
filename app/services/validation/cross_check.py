"""Front/back cross-validation: compares OCR'd front-of-document fields
against MRZ-parsed back-of-document fields and flags real mismatches with
both values shown. This is the strongest inherited feature from Idswyft's
own design — a document is far more suspicious if its printed front
doesn't agree with its own machine-readable zone than if either alone
looks fine.
"""
import re

from app.services.validation.base import ValidationFinding
from app.services.validation.mrz import MRZResult

_NATIONALITY_TO_ICAO = {
    "INDIAN": "IND",
    "NEPALI": "NPL",
    "NEPALESE": "NPL",
    "BHUTANESE": "BTN",
    "BANGLADESHI": "BGD",
    "PAKISTANI": "PAK",
    "SRI LANKAN": "LKA",
    "AMERICAN": "USA",
    "BRITISH": "GBR",
}

_DDMMYYYY = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")


def _ocr_date_to_yymmdd(date_str: str) -> str | None:
    match = _DDMMYYYY.match(date_str.strip())
    if not match:
        return None
    day, month, year = match.groups()
    return f"{year[2:]}{month}{day}"


def _names_match(ocr_name: str, mrz: MRZResult) -> bool:
    ocr_words = set(ocr_name.upper().split())
    mrz_words = set(mrz.surname.split()) | set(mrz.given_names.split())
    return bool(mrz_words) and mrz_words.issubset(ocr_words)


def cross_validate(front_fields: dict[str, str], mrz: MRZResult) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []

    ocr_name = front_fields.get("name")
    if ocr_name:
        mrz_name = f"{mrz.surname} {mrz.given_names}".strip()
        matched = _names_match(ocr_name, mrz)
        findings.append(
            ValidationFinding(
                check="cross_check_name",
                status="PASS" if matched else "FAIL",
                severity="LOW" if matched else "HIGH",
                reason=(
                    f"front OCR name {ocr_name!r} vs MRZ name {mrz_name!r}: "
                    + ("consistent" if matched else "does not match")
                ),
            )
        )

    ocr_number = front_fields.get("passport_number")
    if ocr_number:
        matched = ocr_number.strip().upper() == mrz.passport_number.strip().upper()
        findings.append(
            ValidationFinding(
                check="cross_check_document_number",
                status="PASS" if matched else "FAIL",
                severity="LOW" if matched else "HIGH",
                reason=(
                    f"front OCR document number {ocr_number!r} vs MRZ document number "
                    f"{mrz.passport_number!r}: " + ("match" if matched else "mismatch")
                ),
            )
        )

    ocr_nationality = front_fields.get("nationality")
    if ocr_nationality:
        expected_code = _NATIONALITY_TO_ICAO.get(ocr_nationality.strip().upper())
        if expected_code is not None:
            matched = expected_code == mrz.nationality
            findings.append(
                ValidationFinding(
                    check="cross_check_nationality",
                    status="PASS" if matched else "FAIL",
                    severity="LOW" if matched else "MEDIUM",
                    reason=(
                        f"front OCR nationality {ocr_nationality!r} (expected ICAO code "
                        f"{expected_code!r}) vs MRZ nationality code {mrz.nationality!r}: "
                        + ("match (EXACT)" if matched else "mismatch (EXACT)")
                    ),
                )
            )
        else:
            prefix_match = ocr_nationality.strip().upper()[:3] == mrz.nationality
            findings.append(
                ValidationFinding(
                    check="cross_check_nationality",
                    status="PASS" if prefix_match else "FAIL",
                    severity="LOW" if prefix_match else "MEDIUM",
                    reason=(
                        f"no known ICAO code mapping for {ocr_nationality!r}; fuzzy prefix "
                        f"comparison against MRZ nationality code {mrz.nationality!r}: "
                        + ("match (FUZZY)" if prefix_match else "mismatch (FUZZY)")
                    ),
                )
            )

    ocr_dob = front_fields.get("date_of_birth")
    if ocr_dob:
        converted = _ocr_date_to_yymmdd(ocr_dob)
        if converted is None:
            findings.append(
                ValidationFinding(
                    check="cross_check_date_of_birth",
                    status="FAIL",
                    severity="MEDIUM",
                    reason=f"front OCR date of birth {ocr_dob!r} is not in DD/MM/YYYY format, cannot compare to MRZ",
                )
            )
        else:
            matched = converted == mrz.date_of_birth
            findings.append(
                ValidationFinding(
                    check="cross_check_date_of_birth",
                    status="PASS" if matched else "FAIL",
                    severity="LOW" if matched else "HIGH",
                    reason=(
                        f"front OCR date of birth {ocr_dob!r} ({converted} YYMMDD) vs MRZ "
                        f"date of birth {mrz.date_of_birth!r}: " + ("match" if matched else "mismatch")
                    ),
                )
            )

    ocr_doe = front_fields.get("date_of_expiry")
    if ocr_doe:
        converted = _ocr_date_to_yymmdd(ocr_doe)
        if converted is None:
            findings.append(
                ValidationFinding(
                    check="cross_check_date_of_expiry",
                    status="FAIL",
                    severity="MEDIUM",
                    reason=f"front OCR date of expiry {ocr_doe!r} is not in DD/MM/YYYY format, cannot compare to MRZ",
                )
            )
        else:
            matched = converted == mrz.date_of_expiry
            findings.append(
                ValidationFinding(
                    check="cross_check_date_of_expiry",
                    status="PASS" if matched else "FAIL",
                    severity="LOW" if matched else "HIGH",
                    reason=(
                        f"front OCR date of expiry {ocr_doe!r} ({converted} YYMMDD) vs MRZ "
                        f"date of expiry {mrz.date_of_expiry!r}: " + ("match" if matched else "mismatch")
                    ),
                )
            )

    return findings
