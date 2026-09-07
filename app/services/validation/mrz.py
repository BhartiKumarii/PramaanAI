"""ICAO 9303 TD3 (passport-size, 2-line, 44-char) MRZ parsing and real
modulo-10 checksum validation.

This is the front/back cross-check feature's back-half: the MRZ zone is
what gets compared against the OCR'd front-of-document fields. Nothing
here is hardcoded — check digits are recomputed from the field values
using the actual ICAO weighting scheme and compared against the digit
printed in the MRZ.
"""
import re

from pydantic import BaseModel

_CHAR_VALUES = {c: i for i, c in enumerate("0123456789")}
_CHAR_VALUES.update({c: 10 + i for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")})
_CHAR_VALUES["<"] = 0

_WEIGHTS = (7, 3, 1)

_MRZ_LINE_PATTERN = re.compile(r"^[A-Z0-9<]{44}$")


class MRZCheckDigit(BaseModel):
    field: str
    value: str
    printed_check_digit: str
    computed_check_digit: int
    valid: bool


class MRZResult(BaseModel):
    document_type: str
    issuing_country: str
    surname: str
    given_names: str
    passport_number: str
    nationality: str
    date_of_birth: str  # YYMMDD as printed in the MRZ
    sex: str
    date_of_expiry: str  # YYMMDD as printed in the MRZ
    personal_number: str
    check_digits: list[MRZCheckDigit]
    composite_valid: bool
    all_checks_valid: bool


class MRZFormatError(ValueError):
    pass


def compute_check_digit(data: str) -> int:
    """Real ICAO 9303 modulo-10 check digit: weights 7,3,1 cycling over
    each character, digits keep their value, letters are 10-35, '<' is 0."""
    total = 0
    for index, char in enumerate(data):
        try:
            value = _CHAR_VALUES[char]
        except KeyError as exc:
            raise MRZFormatError(f"invalid MRZ character {char!r}") from exc
        total += value * _WEIGHTS[index % 3]
    return total % 10


def _check(field: str, value: str, printed: str) -> MRZCheckDigit:
    computed = compute_check_digit(value)
    return MRZCheckDigit(
        field=field,
        value=value,
        printed_check_digit=printed,
        computed_check_digit=computed,
        valid=printed.isdigit() and int(printed) == computed,
    )


def parse_td3(line1: str, line2: str) -> MRZResult:
    line1 = line1.strip().upper()
    line2 = line2.strip().upper()

    if not _MRZ_LINE_PATTERN.match(line1):
        raise MRZFormatError(f"line 1 is not a valid 44-char MRZ line: {line1!r}")
    if not _MRZ_LINE_PATTERN.match(line2):
        raise MRZFormatError(f"line 2 is not a valid 44-char MRZ line: {line2!r}")

    document_type = line1[0:2].rstrip("<")
    issuing_country = line1[2:5]
    name_field = line1[5:44]
    surname_part, _, given_part = name_field.partition("<<")
    surname = surname_part.replace("<", " ").strip()
    given_names = given_part.replace("<", " ").strip()

    passport_number = line2[0:9]
    passport_check = line2[9]
    nationality = line2[10:13]
    dob = line2[13:19]
    dob_check = line2[19]
    sex = line2[20]
    doe = line2[21:27]
    doe_check = line2[27]
    personal_number = line2[28:42]
    personal_check = line2[42]
    composite_check = line2[43]

    check_digits = [
        _check("passport_number", passport_number, passport_check),
        _check("date_of_birth", dob, dob_check),
        _check("date_of_expiry", doe, doe_check),
    ]
    # Personal number field is optional/filler in many real passports; only
    # meaningful to checksum-validate when it's not all filler characters.
    if personal_number.strip("<"):
        check_digits.append(_check("personal_number", personal_number, personal_check))

    composite_input = (
        passport_number + passport_check
        + dob + dob_check
        + doe + doe_check
        + personal_number + personal_check
    )
    composite_computed = compute_check_digit(composite_input)
    composite_valid = composite_check.isdigit() and int(composite_check) == composite_computed
    check_digits.append(
        MRZCheckDigit(
            field="composite",
            value=composite_input,
            printed_check_digit=composite_check,
            computed_check_digit=composite_computed,
            valid=composite_valid,
        )
    )

    return MRZResult(
        document_type=document_type,
        issuing_country=issuing_country,
        surname=surname,
        given_names=given_names,
        passport_number=passport_number.replace("<", ""),
        nationality=nationality,
        date_of_birth=dob,
        sex=sex,
        date_of_expiry=doe,
        personal_number=personal_number.replace("<", ""),
        check_digits=check_digits,
        composite_valid=composite_valid,
        all_checks_valid=all(c.valid for c in check_digits),
    )


def extract_mrz_lines(raw_text: str) -> tuple[str, str] | None:
    """Best-effort pull of the two 44-char MRZ lines out of raw OCR text
    (which will have noise/whitespace around the MRZ block)."""
    candidates = []
    for line in raw_text.splitlines():
        compact = re.sub(r"[^A-Z0-9<]", "", line.upper())
        if len(compact) >= 44:
            candidates.append(compact[:44] if len(compact) > 44 else compact)
        elif len(compact) == 44:
            candidates.append(compact)
    # Keep only well-formed 44-char lines, in original order.
    valid_lines = [c for c in candidates if _MRZ_LINE_PATTERN.match(c)]
    if len(valid_lines) < 2:
        return None
    return valid_lines[-2], valid_lines[-1]
