"""Structured field extraction from raw OCR text.

Handles multiple document types with label-driven regex matching.
Each document type has specific expected fields defined by the user:

Passport: Name, Passport Number, Nationality, DOB, Expiry, Gender
Visa: Visa Number, Visa Type, Entry Validity, Stay Duration
National ID (Aadhaar/PAN/Voter): relevant ID fields
Driving Licence: licence-specific fields
Permit: permit-specific fields
"""
import re

_LabelMap = dict[str, list[str]]

_PASSPORT_LABELS: _LabelMap = {
    "name": [
        "name", "full name", "given name", "given names", "surname",
        "holder's name", "holder name", "nom", "prenom",
    ],
    "passport_number": [
        "passport no", "passport number", "document no", "document number",
        "no. of passport", "passport #",
    ],
    "nationality": ["nationality", "nation", "country", "citizenship"],
    "date_of_birth": [
        "date of birth", "dob", "birth date", "d.o.b", "born",
        "date de naissance",
    ],
    "date_of_expiry": [
        "date of expiry", "expiry date", "date of expiration",
        "valid until", "valid till", "expires", "expiry",
    ],
    "gender": ["sex", "gender", "sexe"],
    "place_of_birth": ["place of birth", "birthplace", "born at"],
    "date_of_issue": [
        "date of issue", "issue date", "issued", "date issued",
    ],
    "issuing_authority": [
        "issuing authority", "authority", "issued by", "place of issue",
    ],
}

_VISA_LABELS: _LabelMap = {
    "visa_number": [
        "visa no", "visa number", "visa #", "no. of visa",
    ],
    "visa_type": [
        "visa type", "type of visa", "category", "visa category",
    ],
    "entry_validity": [
        "entry validity", "validity", "entries", "no of entries",
        "number of entries", "valid for entries",
    ],
    "stay_duration": [
        "stay duration", "duration of stay", "period of stay",
        "authorized stay", "duration", "permitted stay",
    ],
    "name": ["name", "full name", "applicant name", "holder name"],
    "nationality": ["nationality", "country"],
    "date_of_issue": ["date of issue", "issue date", "issued"],
    "date_of_expiry": ["date of expiry", "expiry date", "valid until", "expires"],
    "place_of_issue": ["place of issue", "issued at"],
}

_AADHAAR_LABELS: _LabelMap = {
    "name": ["name", "full name"],
    "aadhaar_number": [
        "aadhaar", "aadhaar no", "uid", "aadhaar number",
        "unique identification",
    ],
    "date_of_birth": ["date of birth", "dob", "birth", "year of birth"],
    "gender": ["gender", "sex", "male", "female"],
    "address": ["address", "addr"],
}

_PAN_LABELS: _LabelMap = {
    "name": ["name", "full name"],
    "pan_number": ["permanent account number", "pan", "pan no"],
    "father_name": ["father's name", "father name"],
    "date_of_birth": ["date of birth", "dob"],
}

_VOTER_ID_LABELS: _LabelMap = {
    "name": ["name", "elector name", "elector's name"],
    "voter_id": [
        "epic no", "voter id", "elector id", "epic", "id no",
    ],
    "father_name": ["father's name", "father name", "husband's name"],
    "gender": ["gender", "sex"],
    "date_of_birth": ["date of birth", "dob", "age"],
    "address": ["address", "part no"],
}

_DRIVING_LICENCE_LABELS: _LabelMap = {
    "name": ["name", "full name", "holder name"],
    "licence_number": [
        "dl no", "licence no", "license no", "driving licence",
        "licence number", "license number", "dl number",
    ],
    "date_of_birth": ["date of birth", "dob"],
    "date_of_issue": ["date of issue", "issue date", "issued"],
    "date_of_expiry": [
        "date of expiry", "valid till", "valid upto", "validity",
        "non-transport", "transport",
    ],
    "blood_group": ["blood group", "blood grp", "bg"],
    "vehicle_class": [
        "class of vehicle", "cov", "vehicle class", "authorized to drive",
    ],
    "address": ["address", "addr"],
    "issuing_authority": ["issuing authority", "authority", "rto"],
}

_NEPAL_CITIZENSHIP_LABELS: _LabelMap = {
    "name": ["name", "full name"],
    "citizenship_number": [
        "citizenship no", "nagarikta no", "citizenship certificate no",
        "nagarikta patra", "cert no",
    ],
    "father_name": ["father's name", "father name", "buba ko naam"],
    "mother_name": ["mother's name", "mother name", "aama ko naam"],
    "date_of_birth": ["date of birth", "dob", "janma miti"],
    "gender": ["gender", "sex", "linga"],
    "district": ["district", "jilla"],
    "permanent_address": ["permanent address", "sthayi thegana"],
}

_BHUTAN_CID_LABELS: _LabelMap = {
    "name": ["name", "full name"],
    "cid_number": [
        "cid no", "citizenship identity", "cid", "identity no",
    ],
    "date_of_birth": ["date of birth", "dob"],
    "gender": ["gender", "sex"],
    "dzongkhag": ["dzongkhag", "district"],
    "gewog": ["gewog", "block"],
}

_PERMIT_LABELS: _LabelMap = {
    "name": ["name", "holder name", "applicant name"],
    "permit_number": [
        "permit no", "permit number", "registration no", "reg no",
    ],
    "permit_type": ["permit type", "type of permit", "category"],
    "date_of_issue": ["date of issue", "issue date"],
    "date_of_expiry": [
        "date of expiry", "valid till", "expiry date", "valid until",
    ],
    "issuing_authority": ["issuing authority", "issued by", "authority"],
    "purpose": ["purpose", "reason"],
}

_GENERIC_LINE_PATTERN = re.compile(r"^\s*([A-Za-z][A-Za-z ./]{1,30}?)\s*[:\-]\s*(.+)$")

_DATE_PATTERN = re.compile(r"\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}")
_AADHAAR_NUM_PATTERN = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
_PAN_NUM_PATTERN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_PASSPORT_NUM_PATTERN = re.compile(r"\b[A-Z]\d{7}\b")
_DL_NUM_PATTERN = re.compile(r"\b[A-Z]{2}\d{2}\s?\d{11}\b")


def _validate_field_value(field_name: str, value: str) -> tuple[str | None, float]:
    """Validate and clean extracted field value.

    Returns: (cleaned_value, confidence) where confidence is 0.0-1.0
    Returns (None, 0.0) if value is invalid for the field type.
    """
    if not value or len(value.strip()) < 2:
        return None, 0.0

    value = value.strip()
    confidence = 1.0

    # Name validation
    if field_name in ("name", "full_name", "given_name", "surname", "father_name", "mother_name"):
        # Names should be mostly letters, spaces, and common punctuation
        if not re.match(r"^[A-Za-z\s.'-]+$", value):
            return None, 0.0
        # Names shouldn't be too short (< 2 chars) or too long (> 50 chars)
        if len(value) < 2 or len(value) > 50:
            return None, 0.0
        # Check for common OCR garbage patterns in names
        if re.search(r"\d{4,}|[<>@#$%^&*()]", value):
            return None, 0.0
        # Reject if any "word" is longer than 20 chars (sentence fragment, not a name)
        words = value.split()
        if any(len(w) > 20 for w in words):
            return None, 0.0
        # Reject if more than 5 words (likely a sentence, not a name)
        if len(words) > 5:
            return None, 0.0
        # Reject common false-positive patterns (OCR ran sentences together)
        lower_val = value.lower()
        if any(kw in lower_val for kw in ("passport", "date", "birth", "visa", "number", "valid", "issue")):
            return None, 0.0
        # Single letter is suspicious
        if len(words) == 1 and len(value) == 1:
            confidence = 0.3
        elif len(words) >= 2:
            confidence = 0.9
        else:
            confidence = 0.6
        return value, confidence

    # Nationality validation
    if field_name == "nationality":
        # Nationality should be a country name or 3-letter code
        # Reject if it looks like a document number (contains many digits)
        if re.search(r"\d{4,}", value):
            return None, 0.0
        # Reject if it contains special OCR artifacts
        if re.search(r"[<>@#$%^&*()_+=\[\]{}|\\]", value):
            return None, 0.0
        # Should be reasonable length (2-30 chars)
        if len(value) < 2 or len(value) > 30:
            return None, 0.0
        # 3-letter uppercase code is high confidence
        if re.match(r"^[A-Z]{3}$", value):
            confidence = 0.95
        elif re.match(r"^[A-Za-z\s]+$", value):
            confidence = 0.85
        else:
            confidence = 0.5
        return value, confidence

    # Document number validation
    if field_name in ("passport_number", "document_number", "visa_number", "licence_number",
                      "license_number", "permit_number", "aadhaar_number", "pan_number",
                      "voter_id", "citizenship_number", "cid_number"):
        # Should contain alphanumeric characters
        if not re.search(r"[A-Z0-9]", value.upper()):
            return None, 0.0
        # Reject if it looks like a sentence (contains many spaces/words)
        if len(value.split()) > 3:
            return None, 0.0
        # Clean common OCR artifacts
        value = value.replace(" ", "").replace("-", "").upper()
        if len(value) < 4 or len(value) > 20:
            return None, 0.0
        confidence = 0.9
        return value, confidence

    # Date validation
    if "date" in field_name or field_name in ("dob", "date_of_birth", "date_of_issue",
                                                "date_of_expiry", "expiry", "issue_date", "expiry_date"):
        # Should match date patterns
        if not re.search(r"\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}", value):
            return None, 0.0
        confidence = 0.9
        return value, confidence

    # Gender validation
    if field_name in ("gender", "sex"):
        upper = value.upper()
        if upper in ("M", "MALE", "F", "FEMALE", "MALE", "FEMALE"):
            return upper[0], 0.95  # Normalize to M/F
        return None, 0.0

    # Purpose/generic text fields - just check it's not complete garbage
    # Remove obviously invalid patterns
    if re.match(r"^[^A-Za-z]*$", value):  # No letters at all
        return None, 0.0

    # Default: accept but with lower confidence
    return value, 0.7


def _find_labeled_value(lines: list[str], labels: list[str], field_name: str) -> tuple[str | None, float]:
    """Find value for a labeled field in OCR text.

    Returns: (value, confidence) tuple.
    """
    for line in lines:
        lower = line.lower()
        for label in labels:
            label_lower = label.lower()
            label_nospace = label_lower.replace(" ", "")

            for variant in (label_lower, label_nospace):
                idx = lower.find(variant)
                if idx == -1:
                    continue
                after = line[idx + len(variant):].lstrip()
                if after and after[0] in ":-= ":
                    value = after.lstrip(":-= ").strip()
                    if value:
                        # Validate the extracted value
                        validated, confidence = _validate_field_value(field_name, value)
                        if validated:
                            return validated, confidence
                elif after:
                    value = after.strip()
                    validated, confidence = _validate_field_value(field_name, value)
                    if validated:
                        return validated, confidence

            pattern = re.compile(
                rf"(?:^|\s){re.escape(label)}\s*[:\-]\s*(.+)$",
                re.IGNORECASE,
            )
            match = pattern.search(line)
            if match:
                value = match.group(1).strip()
                if value:
                    validated, confidence = _validate_field_value(field_name, value)
                    if validated:
                        return validated, confidence
    return None, 0.0


def _extract_by_labels(text: str, label_map: _LabelMap) -> tuple[dict[str, str], dict[str, float]]:
    """Extract fields using label matching with validation.

    Returns: (fields_dict, confidence_dict) where confidence_dict maps field_name -> confidence (0.0-1.0)
    """
    lines = [line for line in text.splitlines() if line.strip()]
    fields: dict[str, str] = {}
    confidences: dict[str, float] = {}

    for field, labels in label_map.items():
        value, confidence = _find_labeled_value(lines, labels, field)
        if value:
            fields[field] = value
            confidences[field] = confidence
    return fields, confidences


def _extract_by_regex_fallback(text: str, doc_type: str) -> dict[str, str]:
    """When label matching fails, try regex patterns for known field formats."""
    fields: dict[str, str] = {}
    dates = _DATE_PATTERN.findall(text)

    if doc_type == "passport":
        m = _PASSPORT_NUM_PATTERN.search(text)
        if m:
            fields["passport_number"] = m.group()
        if len(dates) >= 1 and "date_of_birth" not in fields:
            fields["date_of_birth"] = dates[0]
        if len(dates) >= 2 and "date_of_expiry" not in fields:
            fields["date_of_expiry"] = dates[1]
        for token in ["MALE", "FEMALE", "M", "F"]:
            if re.search(rf"\b{token}\b", text, re.IGNORECASE):
                fields.setdefault("gender", "MALE" if token in ("MALE", "M") else "FEMALE")
                break

    elif doc_type == "national_id":
        m = _AADHAAR_NUM_PATTERN.search(text)
        if m:
            fields["aadhaar_number"] = m.group().replace(" ", "")
        m = _PAN_NUM_PATTERN.search(text)
        if m:
            fields["pan_number"] = m.group()
        if dates:
            fields.setdefault("date_of_birth", dates[0])

    elif doc_type in ("driving_license", "driving_licence"):
        m = _DL_NUM_PATTERN.search(text)
        if m:
            fields["licence_number"] = m.group()
        if dates:
            fields.setdefault("date_of_birth", dates[0])
        if len(dates) >= 2:
            fields.setdefault("date_of_expiry", dates[-1])

    elif doc_type == "visa":
        if dates:
            fields.setdefault("date_of_issue", dates[0])
        if len(dates) >= 2:
            fields.setdefault("date_of_expiry", dates[-1])

    return fields


def extract_generic_fields(text: str) -> dict[str, str]:
    """Fallback: parse any 'Label: Value' line."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        match = _GENERIC_LINE_PATTERN.match(line)
        if match:
            key = re.sub(r"\s+", "_", match.group(1).strip().lower())
            value = match.group(2).strip()
            if key and value:
                fields[key] = value
    return fields


_DOC_LABEL_MAPS: dict[str, _LabelMap] = {
    "passport": _PASSPORT_LABELS,
    "visa": _VISA_LABELS,
    "national_id": {
        **_AADHAAR_LABELS, **_PAN_LABELS, **_VOTER_ID_LABELS,
        **_NEPAL_CITIZENSHIP_LABELS, **_BHUTAN_CID_LABELS,
    },
    "driving_license": _DRIVING_LICENCE_LABELS,
    "driving_licence": _DRIVING_LICENCE_LABELS,
    "permit": _PERMIT_LABELS,
}


def extract_fields(document_type: str, text: str) -> dict[str, str]:
    """Extract fields from OCR text using document-type-specific labels and validation.

    Returns dict of field_name -> value. Invalid fields are filtered out.
    """
    label_map = _DOC_LABEL_MAPS.get(document_type)

    if label_map:
        fields, confidences = _extract_by_labels(text, label_map)
        # Log low-confidence extractions for debugging
        for field, conf in confidences.items():
            if conf < 0.6:
                import logging
                logging.getLogger("pramaan.ocr").warning(
                    f"Low confidence extraction: {field}={fields[field]} (confidence: {conf:.2f})"
                )
    else:
        fields = extract_generic_fields(text)

    # Fallback regex extraction for missing fields
    regex_fields = _extract_by_regex_fallback(text, document_type)
    for k, v in regex_fields.items():
        if k not in fields:
            # Validate regex-extracted fields too
            validated, conf = _validate_field_value(k, v)
            if validated and conf >= 0.5:
                fields[k] = validated

    return fields
