"""Real Verhoeff checksum algorithm, used for Aadhaar-format (12-digit,
last digit is the Verhoeff check digit) validation for Indian nationals.

Standard multiplication (d), permutation (p), and inverse (inv) tables —
this is the same algorithm UIDAI uses for Aadhaar numbers. No shortcuts:
the check digit is computed digit-by-digit exactly as specified.
"""

_D_TABLE = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

_P_TABLE = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]

_INV_TABLE = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


class VerhoeffFormatError(ValueError):
    pass


def _digits(number: str) -> list[int]:
    if not number.isdigit():
        raise VerhoeffFormatError(f"expected a digit string, got {number!r}")
    return [int(c) for c in number]


def compute_verhoeff_checksum(number_without_check_digit: str) -> int:
    """Compute the Verhoeff check digit to append to `number_without_check_digit`.

    The check digit itself occupies position 0 when `validate_verhoeff` walks
    the full number in reverse, so the base digits must be processed starting
    at position 1 to land in the same permutation-table slots they'll occupy
    once the check digit is appended.
    """
    digits = _digits(number_without_check_digit)[::-1]
    checksum = 0
    for i, digit in enumerate(digits, start=1):
        checksum = _D_TABLE[checksum][_P_TABLE[i % 8][digit]]
    return _INV_TABLE[checksum]


def validate_verhoeff(number_with_check_digit: str) -> bool:
    """True if the last digit of `number_with_check_digit` is a valid
    Verhoeff check digit for the digits preceding it."""
    digits = _digits(number_with_check_digit)[::-1]
    checksum = 0
    for i, digit in enumerate(digits):
        checksum = _D_TABLE[checksum][_P_TABLE[i % 8][digit]]
    return checksum == 0
