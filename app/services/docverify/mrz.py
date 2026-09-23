"""Multi-format ICAO 9303 MRZ locating, parsing and validation.

TD3 (passports) reuses app.services.validation.mrz.parse_td3 unchanged.
Added here: MRV-A / MRV-B (visa stickers, which have no composite check
digit) and TD1 / TD2 (ID cards). Check digits are always recomputed with the
real ICAO 7-3-1 weighting — never trusted from OCR alone.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.services.docverify.types import OcrLine
from app.services.validation.mrz import MRZFormatError, compute_check_digit, parse_td3

_MRZ_CHARS = re.compile(r"^[A-Z0-9<]+$")


def _clean(text: str) -> str:
    t = text.upper().replace(" ", "").replace("«", "<<").replace("‹", "<").replace("＜", "<")
    return re.sub(r"[^A-Z0-9<]", "", t)


def locate_mrz(lines: list[OcrLine]) -> tuple[list[str], list[int]] | None:
    """Find MRZ lines among OCR output. Returns (lines, union bbox)."""
    cands: list[tuple[str, OcrLine]] = []
    for line in lines:
        compact = _clean(line.text)
        if len(compact) >= 28 and compact.count("<") >= 2 and _MRZ_CHARS.match(compact):
            cands.append((compact, line))
    if len(cands) < 2:
        return None
    cands.sort(key=lambda c: c[1].bbox[1])
    # Prefer the last consecutive group (the MRZ sits at the bottom of the page).
    group = cands[-3:] if len(cands) >= 3 and all(28 <= len(c[0]) <= 32 for c in cands[-3:]) else cands[-2:]
    boxes = [c[1].bbox for c in group]
    union = [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]
    return [c[0] for c in group], union


_TO_LETTER = str.maketrans({"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B", "6": "G"})
_TO_DIGIT = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8", "G": "6"})


def _alpha(seg: str) -> str:
    return seg.translate(_TO_LETTER)


def _digit(seg: str) -> str:
    return seg.translate(_TO_DIGIT)


def correct_ocr(lines: list[str]) -> tuple[list[str], list[str]]:
    """ICAO 9303 fixes each position's character class (letters in names and
    country codes, digits in dates and check digits). OCR routinely confuses
    0/O, 1/I, 5/S, 8/B across those classes, so every position is coerced to
    its class. Document numbers are alphanumeric and left untouched. Returns
    (corrected lines, list of corrections made) — corrections are reported,
    never hidden."""
    fixes: list[str] = []
    out = list(lines)
    def put(i: int, a: int, b: int, fn) -> None:
        seg = out[i][a:b]
        new = fn(seg)
        if new != seg:
            fixes.append(f"line {i + 1} [{a}:{b}] {seg!r}->{new!r}")
            out[i] = out[i][:a] + new + out[i][b:]
    if len(out) == 2 and len(out[0]) >= 44 and len(out[1]) >= 44:  # TD3 / MRV-A
        put(0, 2, 5, _alpha); put(0, 5, 44, _alpha)
        put(1, 9, 10, _digit); put(1, 10, 13, _alpha); put(1, 13, 20, _digit)
        put(1, 21, 28, _digit)
        if out[0].startswith("P"):
            put(1, 43, 44, _digit)
    elif len(out) == 2 and len(out[0]) >= 36 and len(out[1]) >= 36:  # TD2 / MRV-B
        put(0, 2, 5, _alpha); put(0, 5, 36, _alpha)
        put(1, 9, 10, _digit); put(1, 10, 13, _alpha); put(1, 13, 20, _digit); put(1, 21, 28, _digit)
    elif len(out) == 3 and all(len(l) >= 30 for l in out):  # TD1
        put(0, 2, 5, _alpha); put(0, 14, 15, _digit)
        put(1, 0, 7, _digit); put(1, 8, 15, _digit); put(1, 15, 18, _alpha); put(1, 29, 30, _digit)
        put(2, 0, 30, _alpha)
    return out, fixes


def _fit(line: str, length: int) -> str:
    return line[:length] if len(line) >= length else line + "<" * (length - len(line))


def _check(field: str, value: str, printed: str) -> dict[str, Any]:
    computed = compute_check_digit(value)
    return {"field": field, "value": value, "printed_check_digit": printed,
            "computed_check_digit": computed, "valid": printed.isdigit() and int(printed) == computed}


def _names(field: str) -> tuple[str, str]:
    surname, _, given = field.partition("<<")
    return surname.replace("<", " ").strip(), given.replace("<", " ").strip()


def yymmdd_to_iso(value: str, *, is_expiry: bool, today: date | None = None) -> str | None:
    if not re.fullmatch(r"\d{6}", value or ""):
        return None
    today = today or date.today()
    yy, mm, dd = int(value[:2]), int(value[2:4]), int(value[4:])
    if is_expiry:
        year = 2000 + yy if yy < 70 else 1900 + yy
    else:
        year = 2000 + yy if 2000 + yy <= today.year else 1900 + yy
    try:
        return date(year, mm, dd).isoformat()
    except ValueError:
        return None


def _two_line(lines: list[str], length: int, fmt: str) -> dict[str, Any]:
    l1, l2 = _fit(lines[0], length), _fit(lines[1], length)
    surname, given = _names(l1[5:])
    number, n_chk = l2[0:9], l2[9]
    dob, dob_chk = l2[13:19], l2[19]
    doe, doe_chk = l2[21:27], l2[27]
    checks = [_check("document_number", number, n_chk), _check("date_of_birth", dob, dob_chk),
              _check("date_of_expiry", doe, doe_chk)]
    optional = l2[28:length]
    if fmt == "TD2":
        composite_in = l2[0:10] + l2[13:20] + l2[21:35]
        checks.append(_check("composite", composite_in, l2[35]))
    return {"format": fmt, "document_code": l1[0:2].rstrip("<"), "issuing_country": l1[2:5],
            "surname": surname, "given_names": given, "document_number": number.replace("<", ""),
            "nationality": l2[10:13], "date_of_birth": dob, "sex": l2[20], "date_of_expiry": doe,
            "optional_data": optional.replace("<", ""), "check_digits": checks}


def _td1(lines: list[str]) -> dict[str, Any]:
    l1, l2, l3 = (_fit(l, 30) for l in lines[:3])
    number, n_chk = l1[5:14], l1[14]
    dob, dob_chk = l2[0:6], l2[6]
    doe, doe_chk = l2[8:14], l2[14]
    composite_in = l1[5:30] + l2[0:7] + l2[8:15] + l2[18:29]
    surname, given = _names(l3)
    return {"format": "TD1", "document_code": l1[0:2].rstrip("<"), "issuing_country": l1[2:5],
            "surname": surname, "given_names": given, "document_number": number.replace("<", ""),
            "nationality": l2[15:18], "date_of_birth": dob, "sex": l2[7], "date_of_expiry": doe,
            "optional_data": (l1[15:30] + l2[18:29]).replace("<", ""),
            "check_digits": [_check("document_number", number, n_chk), _check("date_of_birth", dob, dob_chk),
                             _check("date_of_expiry", doe, doe_chk), _check("composite", composite_in, l2[29])]}


def parse_mrz(lines: list[str]) -> dict[str, Any]:
    """Parse cleaned MRZ lines of any supported format. Raises MRZFormatError
    with a specific reason when the structure is not a valid MRZ."""
    lines = [_clean(l) for l in lines if _clean(l)]
    is_td1 = len(lines) >= 3 and all(28 <= len(l) <= 32 for l in lines[-3:])
    lines = lines[-3:] if is_td1 else lines[-2:]
    # Structure is judged on the lengths OCR actually produced; lines are
    # only padded/trimmed (by at most 2 characters) after that check.
    target = 30 if is_td1 else 44 if max((len(l) for l in lines), default=0) >= 40 else 36
    if not is_td1 and lines and lines[0].startswith("P"):
        target = 44  # passports are always TD3; a shorter line means a cropped/partial MRZ
    if any(abs(len(l) - target) > 2 for l in lines):
        raise MRZFormatError(f"MRZ line lengths {'/'.join(str(len(l)) for l in lines)} do not match any ICAO format")
    original_lengths = [len(l) for l in lines]
    lines, corrections = correct_ocr([_fit(l, target) for l in lines])
    if len(lines) >= 3 and all(28 <= len(l) <= 32 for l in lines[-3:]):
        result = _td1(lines[-3:])
    elif len(lines) >= 2:
        l1, l2 = lines[-2], lines[-1]
        length = 44 if max(len(l1), len(l2)) >= 40 else 36
        if abs(len(l1) - length) > 2 or abs(len(l2) - length) > 2:
            raise MRZFormatError(f"MRZ line lengths {len(l1)}/{len(l2)} do not match any ICAO format")
        if l1.startswith("P") and length == 44:
            td3 = parse_td3(_fit(l1, 44), _fit(l2, 44))
            result = {"format": "TD3", "document_code": td3.document_type, "issuing_country": td3.issuing_country,
                      "surname": td3.surname, "given_names": td3.given_names,
                      "document_number": td3.passport_number, "nationality": td3.nationality,
                      "date_of_birth": td3.date_of_birth, "sex": td3.sex, "date_of_expiry": td3.date_of_expiry,
                      "optional_data": td3.personal_number,
                      "check_digits": [c.model_dump() for c in td3.check_digits]}
        elif l1.startswith("V"):
            result = _two_line([l1, l2], length, "MRV-A" if length == 44 else "MRV-B")
        else:
            result = _two_line([l1, l2], length, "TD2" if length == 36 else "TD3-like")
    else:
        raise MRZFormatError("fewer than two MRZ lines found")

    result["ocr_corrections"] = corrections
    result["length_ok"] = all(n == target for n in original_lengths)
    result["original_line_lengths"] = original_lengths
    result["all_checks_valid"] = all(c["valid"] for c in result["check_digits"])
    result["failed_checks"] = [c["field"] for c in result["check_digits"] if not c["valid"]]
    result["date_of_birth_iso"] = yymmdd_to_iso(result["date_of_birth"], is_expiry=False)
    result["date_of_expiry_iso"] = yymmdd_to_iso(result["date_of_expiry"], is_expiry=True)
    result["full_name"] = f"{result['given_names']} {result['surname']}".strip()
    return result


def describe_failed_check(check: dict[str, Any]) -> str:
    return (f"MRZ check digit for {check['field'].replace('_', ' ')} failed: printed "
            f"{check['printed_check_digit']!r}, recomputed {check['computed_check_digit']} "
            f"from {check['value']!r}")
