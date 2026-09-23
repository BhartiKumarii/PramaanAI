"""Comprehensive document validation engine (Module 2).

Covers:
- Required field presence per document type
- Document number format validation
- Nationality code validation (ICAO)
- Date format + logical date checks (DOB valid, issue>DOB, expiry>issue, not expired)
- MRZ checksum + MRZ-vs-visual cross-validation
- Aadhaar Verhoeff checksum
- Mock registry checks (exists, name/DOB/number match, lost/stolen, blacklisted)

Every finding carries a specific reason with actual values — never a generic string.
"""
import re
from datetime import date

from app.services.validation.base import ValidationEngine, ValidationFinding, ValidationResult
from app.services.validation.cross_check import cross_validate
from app.services.validation.mrz import MRZResult
from app.services.validation.verhoeff import VerhoeffFormatError, validate_verhoeff

_DDMMYYYY = re.compile(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})$")

# --- ICAO 3-letter nationality codes relevant to India-Nepal-Bhutan borders + common ---
_VALID_ICAO_CODES = {
    "IND", "NPL", "BTN", "BGD", "PAK", "LKA", "MMR", "CHN", "AFG",
    "USA", "GBR", "CAN", "AUS", "NZL", "FRA", "DEU", "ITA", "ESP",
    "JPN", "KOR", "RUS", "BRA", "ZAF", "ARE", "SAU", "SGP", "MYS",
    "THA", "IDN", "PHL", "VNM", "IRN", "IRQ", "TUR", "EGY", "NGA",
    "KEN", "ETH", "GHA", "TZA", "UGA", "MEX", "ARG", "COL", "PER",
    "CHL", "NLD", "BEL", "SWE", "NOR", "DNK", "FIN", "CHE", "AUT",
    "POL", "CZE", "HUN", "ROU", "PRT", "GRC", "ISR", "UKR",
}

_NATIONALITY_TEXT_TO_ICAO = {
    "INDIAN": "IND", "NEPALI": "NPL", "NEPALESE": "NPL",
    "BHUTANESE": "BTN", "BANGLADESHI": "BGD", "PAKISTANI": "PAK",
    "SRI LANKAN": "LKA", "BURMESE": "MMR", "CHINESE": "CHN",
    "AMERICAN": "USA", "BRITISH": "GBR", "CANADIAN": "CAN",
    "AUSTRALIAN": "AUS", "FRENCH": "FRA", "GERMAN": "DEU",
    "JAPANESE": "JPN", "RUSSIAN": "RUS", "BRAZILIAN": "BRA",
}

# --- Document number format patterns per country ---
# India: A1234567 (1 letter + 7 digits)
# Nepal: 01234567 or PA0123456 (8 digits, or 2 letters + 7 digits)
# Bhutan: varies, typically alphanumeric 7-9 chars
_PASSPORT_PATTERNS: dict[str, re.Pattern] = {
    "IND": re.compile(r"^[A-Z]\d{7}$"),
    "NPL": re.compile(r"^(?:\d{8}|[A-Z]{2}\d{7,8})$"),
    "BTN": re.compile(r"^[A-Z0-9]{7,9}$"),
    "_DEFAULT": re.compile(r"^[A-Z0-9]{6,9}$"),
}
_AADHAAR_NUM = re.compile(r"^\d{12}$")
_PAN_NUM = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")
# India DL: XX00 + 11 digits; Nepal DL: alphanumeric
_DL_PATTERNS: dict[str, re.Pattern] = {
    "IND": re.compile(r"^[A-Z]{2}\d{2}\s?\d{11}$"),
    "NPL": re.compile(r"^[A-Z0-9]{5,15}$"),
    "BTN": re.compile(r"^[A-Z0-9]{5,15}$"),
    "_DEFAULT": re.compile(r"^[A-Z0-9]{5,20}$"),
}
# Nepal citizenship certificate number
_NEPAL_CITIZENSHIP = re.compile(r"^\d{2}-\d{2}-\d{2}-\d{5}$")

# --- Required fields per document type ---
_REQUIRED_FIELDS: dict[str, list[str]] = {
    "passport": ["name", "passport_number", "nationality", "date_of_birth", "date_of_expiry", "gender"],
    "visa": ["visa_number", "visa_type", "entry_validity", "stay_duration"],
    "national_id": ["name"],
    "driving_license": ["name", "licence_number"],
    "driving_licence": ["name", "licence_number"],
    "permit": ["name", "permit_number"],
}


def _parse_date(date_str: str) -> date | None:
    if not date_str:
        return None
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
        document_type: str = "passport",
        registry_hits: list | None = None,
    ) -> ValidationResult:
        findings: list[ValidationFinding] = []

        # 1. Required fields present
        findings.extend(self._check_required_fields(ocr_result, document_type))

        # 2. Document number format
        findings.extend(self._check_document_number_format(ocr_result, document_type))

        # 3. Nationality code validation
        findings.extend(self._check_nationality(ocr_result))

        # 4. Date format validation
        findings.extend(self._check_date_formats(ocr_result))

        # 5. Date logic checks
        findings.extend(self._check_date_logic(ocr_result, document_type))

        # 6. Aadhaar Verhoeff checksum
        aadhaar = aadhaar_number or ocr_result.get("aadhaar_number")
        if aadhaar:
            findings.append(self._check_verhoeff(aadhaar))

        # 7. MRZ checks: structure, check digits, cross-validation
        if mrz_result is not None:
            findings.append(self._check_mrz_structure(mrz_result))
            findings.extend(self._check_mrz_checksums(mrz_result))
            findings.extend(cross_validate(ocr_result, mrz_result))

        # 8. Registry checks
        if registry_hits is not None:
            findings.extend(self._check_registry(registry_hits, ocr_result))

        # Determine overall status:
        # - FAIL if any check failed (actual validation failure)
        # - UNCERTAIN if no failures but some checks are NOT_AVAILABLE or UNCERTAIN
        # - PASS if all checks passed
        has_fail = any(f.status == "FAIL" for f in findings)
        has_uncertain = any(f.status in ("NOT_AVAILABLE", "UNCERTAIN") for f in findings)

        if has_fail:
            overall = "FAIL"
        elif has_uncertain:
            overall = "UNCERTAIN"
        else:
            overall = "PASS"

        return ValidationResult(status=overall, findings=findings)

    # ----- 1. Required fields -----

    def _check_required_fields(self, ocr_result: dict, document_type: str) -> list[ValidationFinding]:
        """Check for required fields. Missing fields are marked NOT_AVAILABLE, not FAIL.

        Rationale: If OCR couldn't extract a field, that's an extraction limitation,
        not a document validation failure. The officer should review manually.
        """
        findings = []
        required = _REQUIRED_FIELDS.get(document_type, [])
        present = []
        missing = []
        for field in required:
            value = ocr_result.get(field, "").strip()
            if value:
                present.append(field)
            else:
                missing.append(field)

        if missing:
            findings.append(ValidationFinding(
                check="required_fields",
                status="NOT_AVAILABLE",
                severity="INFO",
                reason=f"Could not extract required fields for {document_type}: {', '.join(missing)}. "
                       f"Officer review required. (Extracted: {', '.join(present) or 'none'})",
            ))
        else:
            findings.append(ValidationFinding(
                check="required_fields",
                status="PASS",
                severity="LOW",
                reason=f"All required fields extracted for {document_type}: {', '.join(present)}",
            ))
        return findings

    # ----- 2. Document number format -----

    def _resolve_country_code(self, ocr_result: dict) -> str:
        nat_text = ocr_result.get("nationality", "").strip().upper()
        code = _NATIONALITY_TEXT_TO_ICAO.get(nat_text)
        if code:
            return code
        if nat_text in _VALID_ICAO_CODES:
            return nat_text
        return "_DEFAULT"

    def _check_document_number_format(self, ocr_result: dict, document_type: str) -> list[ValidationFinding]:
        findings = []
        country = self._resolve_country_code(ocr_result)

        if document_type == "passport":
            number = ocr_result.get("passport_number", "").strip().upper()
            if not number:
                findings.append(ValidationFinding(
                    check="passport_number_format",
                    status="NOT_EVALUATED",
                    severity="INFO",
                    reason="Passport number not extracted — format validation not run",
                ))
                return findings
            pattern = _PASSPORT_PATTERNS.get(country, _PASSPORT_PATTERNS["_DEFAULT"])
            valid = bool(pattern.match(number))
            country_label = {"IND": "India (A1234567)", "NPL": "Nepal (01234567 or PA0123456)",
                             "BTN": "Bhutan (7-9 alphanumeric)"}.get(country, "general")
            findings.append(ValidationFinding(
                check="passport_number_format",
                status="PASS" if valid else "FAIL",
                severity="LOW" if valid else "HIGH",
                reason=f"Passport number {number!r} {'matches' if valid else 'does not match'} "
                       f"expected format for {country_label}",
            ))

        elif document_type == "national_id":
            aadhaar = ocr_result.get("aadhaar_number", "").replace(" ", "")
            pan = ocr_result.get("pan_number", "").strip().upper()
            citizenship = ocr_result.get("citizenship_number", "").strip()
            if aadhaar:
                valid = bool(_AADHAAR_NUM.match(aadhaar))
                findings.append(ValidationFinding(
                    check="aadhaar_number_format",
                    status="PASS" if valid else "FAIL",
                    severity="LOW" if valid else "HIGH",
                    reason=f"Aadhaar number {aadhaar!r} {'matches' if valid else 'does not match'} "
                           f"expected 12-digit format",
                ))
            if pan:
                valid = bool(_PAN_NUM.match(pan))
                findings.append(ValidationFinding(
                    check="pan_number_format",
                    status="PASS" if valid else "FAIL",
                    severity="LOW" if valid else "HIGH",
                    reason=f"PAN number {pan!r} {'matches' if valid else 'does not match'} "
                           f"expected format (AAAAA0000A)",
                ))
            if citizenship and country == "NPL":
                valid = bool(_NEPAL_CITIZENSHIP.match(citizenship))
                findings.append(ValidationFinding(
                    check="nepal_citizenship_format",
                    status="PASS" if valid else "FAIL",
                    severity="LOW" if valid else "MEDIUM",
                    reason=f"Nepal citizenship number {citizenship!r} {'matches' if valid else 'does not match'} "
                           f"expected format (00-00-00-00000)",
                ))

        elif document_type in ("driving_license", "driving_licence"):
            number = ocr_result.get("licence_number", "").strip().upper()
            if number:
                pattern = _DL_PATTERNS.get(country, _DL_PATTERNS["_DEFAULT"])
                valid = bool(pattern.match(number))
                findings.append(ValidationFinding(
                    check="licence_number_format",
                    status="PASS" if valid else "FAIL",
                    severity="LOW" if valid else "MEDIUM",
                    reason=f"licence number {number!r} {'matches' if valid else 'does not match'} "
                           f"expected format for {country}",
                ))

        elif document_type == "visa":
            number = ocr_result.get("visa_number", "").strip()
            if number:
                valid = len(number) >= 4
                findings.append(ValidationFinding(
                    check="visa_number_format",
                    status="PASS" if valid else "FAIL",
                    severity="LOW" if valid else "MEDIUM",
                    reason=f"visa number {number!r}: length {len(number)} "
                           f"{'meets' if valid else 'below'} minimum expected length (4+)",
                ))

        return findings

    # ----- 3. Nationality code -----

    def _check_nationality(self, ocr_result: dict) -> list[ValidationFinding]:
        nat = ocr_result.get("nationality", "").strip().upper()
        if not nat:
            return []

        icao_code = _NATIONALITY_TEXT_TO_ICAO.get(nat, nat[:3] if len(nat) == 3 else None)
        if icao_code and icao_code in _VALID_ICAO_CODES:
            return [ValidationFinding(
                check="nationality_code",
                status="PASS",
                severity="LOW",
                reason=f"nationality {nat!r} maps to valid ICAO code {icao_code!r}",
            )]

        if icao_code:
            return [ValidationFinding(
                check="nationality_code",
                status="FAIL",
                severity="MEDIUM",
                reason=f"nationality {nat!r} maps to ICAO code {icao_code!r} which is not in "
                       f"the known valid set — officer should verify",
            )]

        return [ValidationFinding(
            check="nationality_code",
            status="FAIL",
            severity="MEDIUM",
            reason=f"nationality {nat!r} could not be mapped to a known ICAO nationality code",
        )]

    # ----- 4. Date format validation -----

    def _check_date_formats(self, ocr_result: dict) -> list[ValidationFinding]:
        findings = []
        date_fields = [
            ("date_of_birth", "DOB"),
            ("date_of_issue", "issue date"),
            ("date_of_expiry", "expiry date"),
        ]
        for field, label in date_fields:
            raw = ocr_result.get(field, "").strip()
            if not raw:
                continue
            parsed = _parse_date(raw)
            if parsed is None:
                findings.append(ValidationFinding(
                    check=f"date_format_{field}",
                    status="FAIL",
                    severity="MEDIUM",
                    reason=f"{label} {raw!r} is not a valid date in DD/MM/YYYY format",
                ))
            else:
                findings.append(ValidationFinding(
                    check=f"date_format_{field}",
                    status="PASS",
                    severity="LOW",
                    reason=f"{label} {raw!r} is a valid date ({parsed.isoformat()})",
                ))
        return findings

    # ----- 5. Date logic checks -----

    _NO_EXPIRY_DOC_TYPES = {"national_id"}

    def _check_date_logic(self, ocr_result: dict, document_type: str = "passport") -> list[ValidationFinding]:
        findings = []
        dob = _parse_date(ocr_result.get("date_of_birth", ""))
        doi = _parse_date(ocr_result.get("date_of_issue", ""))
        doe = _parse_date(ocr_result.get("date_of_expiry", ""))
        today = date.today()

        # DOB is a valid plausible date (person 0-150 years old)
        if dob:
            age_days = (today - dob).days
            if age_days < 0:
                findings.append(ValidationFinding(
                    check="dob_plausible",
                    status="FAIL",
                    severity="HIGH",
                    reason=f"date of birth {dob.isoformat()} is in the future",
                ))
            elif age_days > 150 * 365:
                findings.append(ValidationFinding(
                    check="dob_plausible",
                    status="FAIL",
                    severity="HIGH",
                    reason=f"date of birth {dob.isoformat()} implies age > 150 years",
                ))
            else:
                findings.append(ValidationFinding(
                    check="dob_plausible",
                    status="PASS",
                    severity="LOW",
                    reason=f"date of birth {dob.isoformat()} — age ~{age_days // 365} years, plausible",
                ))

        # Issue date > DOB (must be born before document was issued)
        if dob and doi:
            if doi <= dob:
                findings.append(ValidationFinding(
                    check="issue_after_birth",
                    status="FAIL",
                    severity="HIGH",
                    reason=f"issue date {doi.isoformat()} is not after date of birth {dob.isoformat()} — "
                           f"document cannot be issued before holder was born",
                ))
            else:
                findings.append(ValidationFinding(
                    check="issue_after_birth",
                    status="PASS",
                    severity="LOW",
                    reason=f"issue date {doi.isoformat()} is after date of birth {dob.isoformat()} "
                           f"(issued ~{(doi - dob).days // 365} years after birth)",
                ))

        # Expiry date > Issue date
        if doi and doe:
            if doe <= doi:
                findings.append(ValidationFinding(
                    check="expiry_after_issue",
                    status="FAIL",
                    severity="HIGH",
                    reason=f"expiry date {doe.isoformat()} is not after issue date {doi.isoformat()}",
                ))
            else:
                validity_years = (doe - doi).days / 365.25
                findings.append(ValidationFinding(
                    check="expiry_after_issue",
                    status="PASS",
                    severity="LOW",
                    reason=f"expiry date {doe.isoformat()} is {validity_years:.1f} years after "
                           f"issue date {doi.isoformat()}",
                ))

        # Document not expired
        if doe:
            expired = doe < today
            findings.append(ValidationFinding(
                check="expiry",
                status="FAIL" if expired else "PASS",
                severity="HIGH" if expired else "LOW",
                reason=f"document expiry {doe.isoformat()} vs today {today.isoformat()}: "
                       + ("expired" if expired else "not expired"),
            ))
        else:
            expiry_str = ocr_result.get("date_of_expiry", "")
            if expiry_str:
                findings.append(ValidationFinding(
                    check="expiry",
                    status="FAIL",
                    severity="MEDIUM",
                    reason=f"date_of_expiry {expiry_str!r} could not be parsed — cannot verify expiry",
                ))
            else:
                if document_type in self._NO_EXPIRY_DOC_TYPES:
                    findings.append(ValidationFinding(
                        check="expiry",
                        status="PASS",
                        severity="LOW",
                        reason=f"no date_of_expiry expected for {document_type} — national IDs typically do not expire",
                    ))
                else:
                    findings.append(ValidationFinding(
                        check="expiry",
                        status="FAIL",
                        severity="MEDIUM",
                        reason="no date_of_expiry field was extracted from the document",
                    ))

        # Issue date should not be in the future
        if doi:
            if doi > today:
                findings.append(ValidationFinding(
                    check="issue_date_future",
                    status="FAIL",
                    severity="HIGH",
                    reason=f"issue date {doi.isoformat()} is in the future — document not yet valid",
                ))

        return findings

    # ----- 6. Verhoeff (Aadhaar) -----

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

    # ----- 7. MRZ structure + checksums -----

    def _check_mrz_structure(self, mrz_result: MRZResult) -> ValidationFinding:
        if mrz_result.all_checks_valid:
            return ValidationFinding(
                check="mrz_structure",
                status="PASS",
                severity="LOW",
                reason=f"MRZ structure valid: type={mrz_result.document_type}, "
                       f"issuer={mrz_result.issuing_country}, all {len(mrz_result.check_digits)} "
                       f"check digits pass, composite {'valid' if mrz_result.composite_valid else 'invalid'}",
            )
        failed = [cd.field for cd in mrz_result.check_digits if not cd.valid]
        return ValidationFinding(
            check="mrz_structure",
            status="FAIL",
            severity="HIGH",
            reason=f"MRZ structure has {len(failed)} failed check digit(s): {', '.join(failed)} — "
                   f"composite {'valid' if mrz_result.composite_valid else 'invalid'}",
        )

    def _check_mrz_checksums(self, mrz_result: MRZResult) -> list[ValidationFinding]:
        findings = []
        for cd in mrz_result.check_digits:
            findings.append(ValidationFinding(
                check=f"mrz_checksum_{cd.field}",
                status="PASS" if cd.valid else "FAIL",
                severity="LOW" if cd.valid else "HIGH",
                reason=(
                    f"MRZ field {cd.field}={cd.value!r}: printed check digit "
                    f"{cd.printed_check_digit!r}, computed {cd.computed_check_digit}: "
                    + ("valid" if cd.valid else "invalid — checksum mismatch")
                ),
            ))
        return findings

    # ----- 8. Registry checks -----

    def _check_registry(self, registry_hits: list, ocr_result: dict) -> list[ValidationFinding]:
        findings = []

        if not registry_hits:
            findings.append(ValidationFinding(
                check="registry_lookup",
                status="PASS",
                severity="LOW",
                reason="no matches found in mock watchlist/lost-document registry (synthetic data)",
            ))
            return findings

        for hit in registry_hits:
            hit_d = hit if isinstance(hit, dict) else (hit.model_dump() if hasattr(hit, "model_dump") else vars(hit))
            doc_num = str(hit_d.get("document_number", ""))
            full_name = str(hit_d.get("full_name", ""))
            reason_text = str(hit_d.get("registry_reason", ""))
            severity = str(hit_d.get("severity", "MEDIUM"))
            match_type = str(hit_d.get("match_type", "UNKNOWN"))
            confidence = float(hit_d.get("confidence", 0.0))

            is_lost_stolen = "lost" in reason_text.lower() or "stolen" in reason_text.lower()
            is_blacklisted = "blacklist" in reason_text.lower() or "revoked" in reason_text.lower()

            check_name = "registry_lost_stolen" if is_lost_stolen else (
                "registry_blacklisted" if is_blacklisted else "registry_hit"
            )

            findings.append(ValidationFinding(
                check=check_name,
                status="FAIL",
                severity=severity,
                reason=f"registry {match_type} match (confidence {confidence:.0%}): "
                       f"document {doc_num!r}, name {full_name!r} — reason: {reason_text} "
                       f"(mock/synthetic registry data)",
            ))

        # Check field matches if we have both OCR fields and registry hits
        for hit in registry_hits:
            hit_d2 = hit if isinstance(hit, dict) else (hit.model_dump() if hasattr(hit, "model_dump") else vars(hit))
            hit_name = str(hit_d2.get("full_name", ""))
            ocr_name = ocr_result.get("name", "")
            if ocr_name and hit_name:
                from app.services.registry.fuzzy import name_similarity
                sim = name_similarity(ocr_name, hit_name)
                findings.append(ValidationFinding(
                    check="registry_name_match",
                    status="FAIL" if sim > 0.7 else "PASS",
                    severity="HIGH" if sim > 0.9 else ("MEDIUM" if sim > 0.7 else "LOW"),
                    reason=f"OCR name {ocr_name!r} vs registry name {hit_name!r}: "
                           f"similarity {sim:.0%}",
                ))

        return findings
