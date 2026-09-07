"""Regex/keyword-based structured field extraction from raw OCR text.

Deliberately simple and label-driven rather than ML-based — this is the
right tool for printed VIZ (visual inspection zone) fields on a clean
document image. MRZ parsing/checksum validation is a separate concern
(Module 2 — document validation), not handled here.
"""
import re

_LabelMap = dict[str, list[str]]

_PASSPORT_LABELS: _LabelMap = {
    "name": ["name", "full name", "given name", "surname"],
    "passport_number": ["passport no", "passport number", "document no"],
    "nationality": ["nationality"],
    "date_of_birth": ["date of birth", "dob"],
    "date_of_expiry": ["date of expiry", "expiry date"],
    "gender": ["sex", "gender"],
}

_VISA_LABELS: _LabelMap = {
    "visa_number": ["visa no", "visa number"],
    "visa_type": ["visa type"],
    "entry_validity": ["entry validity", "validity"],
    "stay_duration": ["stay duration", "duration of stay"],
}

_GENERIC_LINE_PATTERN = re.compile(r"^\s*([A-Za-z][A-Za-z ./]{1,30}?)\s*[:\-]\s*(.+)$")


def _find_labeled_value(lines: list[str], labels: list[str]) -> str | None:
    for line in lines:
        for label in labels:
            pattern = re.compile(rf"^\s*{re.escape(label)}\s*[:\-]\s*(.+)$", re.IGNORECASE)
            match = pattern.match(line)
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


def extract_generic_fields(text: str) -> dict[str, str]:
    """Fallback for national_id/driving_licence/permit: parse any 'Label: Value' line."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        match = _GENERIC_LINE_PATTERN.match(line)
        if match:
            key = re.sub(r"\s+", "_", match.group(1).strip().lower())
            value = match.group(2).strip()
            if key and value:
                fields[key] = value
    return fields


def extract_fields(document_type: str, text: str) -> dict[str, str]:
    if document_type == "passport":
        return _extract_by_labels(text, _PASSPORT_LABELS)
    if document_type == "visa":
        return _extract_by_labels(text, _VISA_LABELS)
    return extract_generic_fields(text)
