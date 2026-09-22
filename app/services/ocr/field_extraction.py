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


def _find_labeled_value(lines: list[str], labels: list[str]) -> str | None:
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
                        return value
                elif after:
                    return after.strip()

            pattern = re.compile(
                rf"(?:^|\s){re.escape(label)}\s*[:\-]\s*(.+)$",
                re.IGNORECASE,
            )
            match = pattern.search(line)
            if match:
                value = match.group(1).strip()
                if value:
                    return value
    return None


def _extract_by_labels(text: str, label_map: _LabelMap) -> dict[str, str]:
    lines = [line for line in text.splitlines() if line.strip()]
    fields: dict[str, str] = {}
    for field, labels in label_map.items():
        value = _find_labeled_value(lines, labels)
        if value:
            fields[field] = value
    return fields


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
    label_map = _DOC_LABEL_MAPS.get(document_type)

    if label_map:
        fields = _extract_by_labels(text, label_map)
    else:
        fields = extract_generic_fields(text)

    regex_fields = _extract_by_regex_fallback(text, document_type)
    for k, v in regex_fields.items():
        if k not in fields:
            fields[k] = v

    return fields
