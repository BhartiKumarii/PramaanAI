"""Document-number handling for network/identity matching without
storing (or displaying) the raw number — see CLAUDE.md's data rules
("use document hashes and masked identifiers where possible")."""
import hashlib


def normalize_document_number(value: str) -> str:
    return "".join(value.split()).upper()


def hash_document_number(value: str) -> str:
    """A stable, non-reversible key for exact-match lookups (e.g. "does
    this same document number already have a PersonEntity?") — never
    used for display."""
    return hashlib.sha256(normalize_document_number(value).encode()).hexdigest()


def mask_document_number(value: str) -> str:
    """Display form: first character + last 4, everything else asterisked.
    "P1234567" -> "P***4567"."""
    normalized = normalize_document_number(value)
    if len(normalized) <= 5:
        return "*" * len(normalized)
    return normalized[0] + "*" * (len(normalized) - 5) + normalized[-4:]
