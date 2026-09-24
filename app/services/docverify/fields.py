"""Field extraction from OCR rows, keeping per-field confidence and bbox.

Label-anchored: a value is only taken from the same row as its printed label
or from the row directly beneath it. Regex fallbacks exist only for values
with a distinctive, self-identifying shape (Aadhaar number, Indian DL number,
passport number). Nothing is guessed — an absent field is simply absent.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from difflib import SequenceMatcher

from app.services.docverify.ocr import group_rows
from app.services.docverify.types import DocumentType, FieldValue, OcrLine, VISA_TYPES

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}

_DATE_PATTERNS = [
    (re.compile(r"(?<!\d)(\d{1,2})[/\-. ](\d{1,2})[/\-. ](\d{4})(?!\d)"), "dmy"),
    (re.compile(r"(?<!\d)(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})(?!\d)"), "ymd"),
    (re.compile(r"(?<!\d)(\d{1,2})[ \-/]?([A-Z]{3})[A-Z]*[ \-/,]*(\d{4})(?!\d)"), "dMy"),
]


def find_dates(text: str) -> list[tuple[str, int]]:
    """All parseable dates in `text` as (ISO date, start offset), in order."""
    found: list[tuple[str, int]] = []
    upper = text.upper()
    for pattern, kind in _DATE_PATTERNS:
        for m in pattern.finditer(upper):
            try:
                if kind == "dmy":
                    d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                elif kind == "ymd":
                    d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                else:
                    month = _MONTHS.get(m.group(2)[:3])
                    if not month:
                        continue
                    d = date(int(m.group(3)), month, int(m.group(1)))
            except ValueError:
                continue
            if 1900 <= d.year <= 2100 and not any(abs(s - m.start()) < 3 for _, s in found):
                found.append((d.isoformat(), m.start()))
    return sorted(found, key=lambda x: x[1])


def normalize_date(text: str | None) -> str | None:
    if not text:
        return None
    dates = find_dates(text)
    return dates[0][0] if dates else None


# field -> label phrases (lower-case). Order within a list = preference.
_LABELS: dict[str, list[str]] = {
    "surname": ["surname"],
    "given_names": ["given names", "given name"],
    "name": ["name of holder", "name of bearer", "name of the bearer", "name of the holder", "bearer's name",
             "full name", "holder's name", "name"],
    "nationality": ["nationality"],
    "sex": ["sex", "gender"],
    "date_of_birth": ["date of birth", "d.o.b", "dob", "birth date"],
    "date_of_issue": ["date of issue", "issue date", "issued on", "doi", "issued"],
    "date_of_expiry": ["date of expiry", "expiry date", "valid until", "valid till", "validity", "valid upto", "expiry"],
    "valid_from": ["valid from"],
    "visa_number": ["visa no", "visa number"],
    "visa_type": ["visa type", "type of visa", "visa plan"],
    "visa_category": ["category"],
    "entries": ["no. of entries", "number of entries", "entries"],
    "duration": ["duration of stay", "duration", "stay"],
    "issuing_authority": ["issuing authority", "licencing authority", "licensing authority", "issued by", "authority"],
    "place_of_issue": ["place of issue", "issued at"],
    "permit_number": ["permit no", "permit number"],
    "purpose": ["purpose of visit", "purpose"],
    "vehicle_classes": ["class of vehicle", "vehicle class", "cov"],
    "passport_number": ["passport no", "passport number"],
    "document_number": ["licence no", "license no", "dl no", "d.l. no", "d.l.no", "document no", "card no", "id no"],
    "address": ["address"],
    "place_of_birth": ["place of birth"],
    "personal_number": ["personal no", "personal number"],
}

# Header/label text on an Aadhaar card, never a holder's name. Long words
# match inside glued OCR text ("GOVERNMENTOFINDIA"); short ones only as whole
# words, so names such as KAMALESH or INDIRA are not rejected.
_AADHAAR_NOT_NAME = re.compile(r"GOVERNMENT|AADHAAR|UNIQUE|AUTHORITY|SPECIMEN|OFINDIA|"
                               r"\b(?:MALE|FEMALE|DOB|INDIA|BIRTH|YEAR)\b")
_AADHAAR_RE = re.compile(r"\b([2-9]\d{3})\s?(\d{4})\s?(\d{4})\b")
_DL_RE = re.compile(r"\b([A-Z]{2})[ -]?(\d{2})[ -]?((?:19|20)\d{2})[ -]?(\d{7})\b")
_PASSPORT_RE = re.compile(r"\b([A-Z][0-9]{7})\b")

_DATE_FIELDS = {"date_of_birth", "date_of_issue", "date_of_expiry", "valid_from"}
_TEXT_FIELDS = {"name", "surname", "given_names", "nationality", "place_of_issue", "place_of_birth",
                "issuing_authority", "visa_type", "visa_category", "purpose"}
_NUMBER_FIELDS = {"document_number", "passport_number", "visa_number", "permit_number", "personal_number"}


def _compact(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


_LABEL_INDEX = [(f, l, _compact(l)) for f, ls in _LABELS.items() for l in ls if len(_compact(l)) >= 3]


def match_label(text: str) -> tuple[str, str, int] | None:
    """(field, label, value_start) for a box that begins with a printed
    label. Tolerant to what PP-OCR does to real cards: dropped spaces
    ("DATEOFBIRTH"), a few junk characters from a bilingual prefix
    ("TTISURNAME"), and one or two misread letters ("Date ofbsue").
    The longest/most specific label wins ("surname" over "name")."""
    c = _compact(text)
    if not c:
        return None
    best: tuple[float, str, str, bool] | None = None
    for field, label, lc in _LABEL_INDEX:
        pos = c.find(lc)
        if pos != -1 and pos <= 5:
            score, exact = len(lc) - 0.5 * pos, True
        elif len(lc) >= 8:
            ratio = max(SequenceMatcher(None, lc, c[st:st + len(lc)]).ratio() for st in range(0, min(6, len(c))))
            if ratio < 0.82:
                continue
            score, exact = len(lc) * ratio - 2.0, False
        else:
            continue
        if best is None or score > best[0]:
            best = (score, field, label, exact)
    if best is None:
        return None
    _, field, label, exact = best
    value_start = len(text)
    if exact:
        letters = [re.escape(ch) for ch in _compact(label)]
        m = re.search(r"[^A-Za-z]*".join(letters), text, re.IGNORECASE)
        if m:
            value_start = m.end()
    return field, label, value_start


def _valid_value(field: str, value: str) -> bool:
    v = value.strip(" :;,.-/|")
    if not v or match_label(v):
        return False
    # Reject a "value" that is really another label run together with junk
    # (e.g. "DepartmenPassport No").
    cv = _compact(v)
    if any(len(lc) >= 6 and lc in cv for _, _, lc in _LABEL_INDEX):
        return False
    if field in _DATE_FIELDS:
        return bool(find_dates(v))
    if field in _TEXT_FIELDS:
        # Leftover label words ("OF BEARER", "OFTHEHOLDER") are never a value.
        if re.fullmatch(r"(?:OF|THE|BEARER|HOLDER|S|'|\s)+", v.upper().replace(" ", "")) or \
                re.fullmatch(r"(?:OF|THE|BEARER|HOLDER|\s)+", v.upper()):
            return False
        letters = sum(ch.isalpha() for ch in v)
        return letters >= 2 and letters / max(1, len(v.replace(" ", ""))) >= 0.6 and not find_dates(v)
    if field in _NUMBER_FIELDS:
        return any(ch.isdigit() for ch in v) and len(re.sub(r"[^A-Za-z0-9]", "", v)) >= 4
    if field == "sex":
        return v.upper()[:1] in ("M", "F", "X") and len(v) <= 8
    return True


def extract_fields(lines: list[OcrLine], document_type: DocumentType) -> dict[str, FieldValue]:
    rows = group_rows(lines)
    fields: dict[str, FieldValue] = {}
    is_travel_auth = document_type in VISA_TYPES or document_type == DocumentType.BHUTAN_ENTRY_PERMIT

    for r_idx, row in enumerate(rows):
        for b_idx, box in enumerate(row):
            hit = match_label(box.text)
            if hit is None:
                continue
            field, label, value_start = hit
            if field == "passport_number" and not is_travel_auth:
                field = "document_number"
            if field in fields:
                continue
            height = max(8, box.bbox[3] - box.bbox[1])
            candidates: list[tuple[str, OcrLine]] = []
            same_box = box.text[value_start:].strip(" :;,.-/|")
            if same_box:
                candidates.append((same_box, box))
            # Same visual row, but only if close to the label (a value 140px
            # away usually belongs to a different column's label).
            for nxt in row[b_idx + 1:]:
                if nxt.bbox[0] - box.bbox[2] <= 4 * height + 30:
                    candidates.append((nxt.text, nxt))
                break
            # The row beneath, aligned with the label's left edge.
            for below_row in rows[r_idx + 1:r_idx + 2]:
                aligned = sorted(below_row, key=lambda b: abs(b.bbox[0] - box.bbox[0]))
                if aligned and abs(aligned[0].bbox[0] - box.bbox[0]) < 3 * height + 40:
                    candidates.append((aligned[0].text, aligned[0]))
            for value, src in candidates:
                if _valid_value(field, value):
                    fields[field] = FieldValue(value=value.strip(" :;,"), confidence=src.confidence, source="ocr",
                                               bbox=src.bbox, raw=f"{box.text} {value}" if src is not box else box.text)
                    break

    full_text = "\n".join(l.text for l in lines)

    # Date-valued fields are normalised to ISO; "10/10/2022 to 24/10/2022"
    # style validity ranges are split into valid_from / date_of_expiry.
    for key in ("date_of_birth", "date_of_issue", "date_of_expiry", "valid_from"):
        if key in fields:
            dates = find_dates(fields[key].value)
            if key == "date_of_expiry" and len(dates) >= 2 and "valid_from" not in fields:
                fields["valid_from"] = fields[key].model_copy(update={"value": dates[0][0]})
                fields[key] = fields[key].model_copy(update={"value": dates[-1][0]})
            elif dates:
                fields[key] = fields[key].model_copy(update={"value": dates[0][0]})
            else:
                del fields[key]

    # Regex fallbacks for self-identifying numbers only.
    if document_type == DocumentType.AADHAAR and "aadhaar_number" not in fields:
        for line in lines:
            m = _AADHAAR_RE.search(line.text)
            if m:
                fields["aadhaar_number"] = FieldValue(value="".join(m.groups()), confidence=line.confidence,
                                                      source="ocr", bbox=line.bbox, raw=line.text)
                break
    if document_type == DocumentType.DRIVING_LICENCE:
        # The Indian DL number has a self-identifying shape (SS RR YYYY NNNNNNN);
        # prefer it over whatever followed a "No." label.
        for line in lines:
            m = _DL_RE.search(line.text.upper())
            if m:
                fields["document_number"] = FieldValue(value="".join(m.groups()), confidence=line.confidence,
                                                       source="ocr", bbox=line.bbox, raw=line.text)
                break
        classes = sorted({t for t in re.findall(r"\b(MCWOG|MCWG|LMV-NT|LMV-TR|LMV|HMV|HGMV|HPMV|TRANS|MGV|INVCRG)\b",
                                                full_text.upper())})
        if classes:
            fields["vehicle_classes"] = FieldValue(value=",".join(classes), confidence=0.9, source="ocr")
    if document_type in (DocumentType.INDIAN_PASSPORT,) and "document_number" not in fields:
        for line in lines:
            m = _PASSPORT_RE.search(line.text.upper())
            if m:
                fields["document_number"] = FieldValue(value=m.group(1), confidence=line.confidence,
                                                       source="ocr", bbox=line.bbox, raw=line.text)
                break

    if document_type == DocumentType.AADHAAR and "name" not in fields:
        # Aadhaar prints the holder's name, unlabelled, on the line directly
        # above the DOB line. Only a Latin-letter, 2-4 word line qualifies.
        rows_text = group_rows(lines)
        for r_idx, row in enumerate(rows_text):
            if any(re.search(r"\bDOB\b|YEAR OF BIRTH|जन्म", b.text, re.IGNORECASE) for b in row) and r_idx > 0:
                # 1-4 words: PP-OCR sometimes drops the spaces of a printed
                # name ("MEERASYNTHETICRAO"); it is kept exactly as read,
                # never re-split by guesswork. Header/label words never count.
                cand = [b for b in rows_text[r_idx - 1] if re.fullmatch(r"[A-Za-z .]{3,40}", b.text.strip())
                        and 1 <= len(b.text.split()) <= 4
                        and not _AADHAAR_NOT_NAME.search(b.text.upper())
                        and not _AADHAAR_NOT_NAME.search(b.text.replace(" ", "").upper())]
                if cand:
                    fields["name"] = FieldValue(value=cand[0].text.strip(), confidence=cand[0].confidence,
                                                source="ocr", bbox=cand[0].bbox, raw="line above DOB (Aadhaar layout)")
                for b in row:
                    dates = find_dates(b.text)
                    if dates and "date_of_birth" not in fields:
                        fields["date_of_birth"] = FieldValue(value=dates[0][0], confidence=b.confidence, source="ocr", bbox=b.bbox)
                        # The DOB line was mis-labelled as an issue date by the generic matcher.
                        if fields.get("date_of_issue") and fields["date_of_issue"].value == dates[0][0]:
                            del fields["date_of_issue"]
                break

    if document_type == DocumentType.AADHAAR and "sex" not in fields:
        # Aadhaar prints gender unlabelled ("FEMALE") or as "Gender: Female".
        for line in lines:
            m = re.search(r"(?:GENDER\s*[:/]?\s*)?\b(MALE|FEMALE|TRANSGENDER)\b", line.text.upper())
            if m:
                fields["sex"] = FieldValue(value={"MALE": "M", "FEMALE": "F", "TRANSGENDER": "X"}[m.group(1)],
                                           confidence=line.confidence, source="ocr", bbox=line.bbox, raw=line.text)
                break

    if "name" not in fields and ("surname" in fields or "given_names" in fields):
        parts = [fields[k].value for k in ("given_names", "surname") if k in fields]
        src = fields.get("surname") or fields["given_names"]
        fields["name"] = FieldValue(value=" ".join(parts), confidence=src.confidence, source="ocr", bbox=src.bbox)

    for key in ("document_number", "visa_number", "passport_number", "permit_number"):
        if key in fields:
            fields[key] = fields[key].model_copy(update={"value": re.sub(r"[\s]", "", fields[key].value.upper())})
    return fields


def age_on(dob_iso: str | None, on: date) -> int | None:
    if not dob_iso:
        return None
    try:
        dob = datetime.strptime(dob_iso, "%Y-%m-%d").date()
    except ValueError:
        return None
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


# --- Devanagari (Nepali / Hindi) -------------------------------------------
# Read from the separate Devanagari OCR pass. These go into their own field
# keys and are never compared with the (Latin-script) registry: a Devanagari
# name would always "differ" from a Latin one, and Nepali documents give
# dates in Bikram Sambat (BS 2044 ≈ AD 1987), which must not be read as a
# Gregorian date.
_DEVA_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_DEVA_LABELS: list[tuple[str, re.Pattern]] = [
    # OCR often misspells conjuncts (नामधर for नामथर, राषट्टिय for राष्ट्रिय),
    # so labels are matched loosely.
    ("national_id_number", re.compile(r"^रा\S*\s*परिचय\s*(?:पत्र\s*)?(?:न\S*|नं\.?)?\s*(?:NIN)?\s*[:ः/]?\s*")),
    ("citizenship_number", re.compile(r"^(?:ना\.?\s*प्र\.?\s*न[ं]?\.?|नागरिकता\s*(?:प्रमाणपत्र\s*)?(?:नं\.?|नम्बर))\s*[:ः/]?\s*")),
    ("date_of_birth_bs", re.compile(r"^(?:जन्म\s*मिति|जन्ममिति)\s*[:ः/]?\s*")),
    ("name_native", re.compile(r"^(?:नाम\s*[,/]?\s*[थधश]र|नाम[थधश]र|नाम)\s*[:ः/]?\s*")),
]
_DEVA_LABEL_WORDS = re.compile(r"जन्म|जन्स|स्थान|ठेगाना|जिल्ला|सरकार|परिचय|नागरिकता|मिति|नाम|लिङ्ग|बाबु|आमा|पति")
_DEVA_SEX = {"पुरुष": "M", "महिला": "F", "पुरूष": "M", "स्त्री": "F"}
_BS_DATE = re.compile(r"(\d{4})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{1,2})")


def _value_near(label: OcrLine, lines: list[OcrLine]) -> OcrLine | None:
    """The value printed next to a label that stands alone: to its right on
    the same row, else directly below it (within about two line heights)."""
    lh = max(1, label.bbox[3] - label.bbox[1])
    cy = (label.bbox[1] + label.bbox[3]) / 2
    right = [l for l in lines if l is not label and l.bbox[0] > label.bbox[2] - lh
             and abs((l.bbox[1] + l.bbox[3]) / 2 - cy) < 0.6 * lh and l.bbox[0] - label.bbox[2] < 12 * lh]
    if right:
        return min(right, key=lambda l: l.bbox[0])
    below = [l for l in lines if l is not label and 0 < l.bbox[1] - label.bbox[1] <= 2.2 * lh
             and abs(l.bbox[0] - label.bbox[0]) < 1.5 * lh]
    return min(below, key=lambda l: l.bbox[1]) if below else None


def extract_native_fields(lines: list[OcrLine]) -> dict[str, FieldValue]:
    """Fields read from Devanagari text: label on the line, value after it
    (or next to / under the label when it stands alone)."""
    out: dict[str, FieldValue] = {}
    for line in lines:
        text = line.text.strip()
        for word, code in _DEVA_SEX.items():
            if "sex_native" not in out and re.search(rf"(?:^|[\s/:ः]){word}(?:$|[\s/])", text):
                out["sex_native"] = FieldValue(value=code, confidence=round(line.confidence * 0.9, 4),
                                               source="ocr_devanagari", bbox=line.bbox)
        for field, label in _DEVA_LABELS:
            m = label.match(text)
            if not m:
                continue
            if field in out:
                break
            value, src = text[m.end():].strip(" :ः-|"), line
            if field == "national_id_number" or field == "citizenship_number":
                value = re.sub(r"[^0-9\-/]", "", value.translate(_DEVA_DIGITS)).strip("-/")
            if not value or (field == "name_native" and len(re.findall(r"[\u0900-\u097F]", value)) < 3):
                near = _value_near(line, lines)
                if near is None or near.text.strip().endswith((":", "ः")):  # another label
                    break
                src, value = near, near.text.strip(" :ः-|")
            if field == "date_of_birth_bs":
                d = _BS_DATE.search(value.translate(_DEVA_DIGITS))
                if not d or not (1 <= int(d.group(2)) <= 12 and 1 <= int(d.group(3)) <= 32):
                    break
                value = f"{d.group(1)}-{int(d.group(2)):02d}-{int(d.group(3)):02d} BS"
            elif field in ("national_id_number", "citizenship_number"):
                value = re.sub(r"[^0-9\-/]", "", value.translate(_DEVA_DIGITS)).strip("-/")
                if len(re.sub(r"\D", "", value)) < 5:
                    break
            elif len(re.findall(r"[\u0900-\u097F]", value)) < 3 or _DEVA_LABEL_WORDS.search(value) \
                    or re.search(r"\d", value.translate(_DEVA_DIGITS)):
                break
            out[field] = FieldValue(value=value, confidence=round(src.confidence * 0.9, 4),
                                    source="ocr_devanagari", bbox=src.bbox)
            break  # one label per line
    return out

