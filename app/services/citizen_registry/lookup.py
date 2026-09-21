from sqlalchemy.orm import Session

from app.repositories.citizen_registry_repository import find_by_document_number
from app.services.citizen_registry.base import CitizenRegistryResult

_NATIONALITY_ALIASES = {
    # ISO 2-letter
    "IN": "INDIAN", "NP": "NEPALI", "BT": "BHUTANESE",
    "ES": "SPANISH", "DE": "GERMAN", "SG": "SINGAPOREAN",
    # ISO 3-letter
    "IND": "INDIAN", "NPL": "NEPALI", "BTN": "BHUTANESE",
    # Full names
    "INDIAN": "INDIAN", "NEPALI": "NEPALI", "NEPALESE": "NEPALI",
    "BHUTANESE": "BHUTANESE", "SPANISH": "SPANISH", "GERMAN": "GERMAN",
}


def _names_match(declared: str, on_file: str) -> bool:
    declared_words = set(declared.upper().split())
    on_file_words = set(on_file.upper().split())
    return bool(on_file_words) and on_file_words.issubset(declared_words)


def _nationality_match(declared: str, on_file: str) -> bool:
    d = _NATIONALITY_ALIASES.get(declared.strip().upper(), declared.strip().upper())
    f = _NATIONALITY_ALIASES.get(on_file.strip().upper(), on_file.strip().upper())
    return d == f


def lookup_citizen_registry(
    db: Session,
    document_number: str | None,
    full_name: str | None,
    date_of_birth: str | None,
    nationality: str | None,
) -> CitizenRegistryResult | None:
    """Real DB lookup against the demo citizen registry — positively
    confirms (or contradicts) the officer's own extracted data, rather
    than only checking a blacklist. Returns None (not run) when there's
    no document number to look up, exactly like every other optional
    screening signal — an absent signal is never scored as clean."""
    if not document_number:
        return None

    record = find_by_document_number(db, document_number)
    if record is None:
        return CitizenRegistryResult(
            status="NO_RECORD",
            reason=(
                f"no citizen registry record for document number {document_number!r} — "
                "not every document is seeded in this demo dataset, so this is not itself a signal"
            ),
        )

    mismatched: list[str] = []
    if full_name and not _names_match(full_name, record.full_name):
        mismatched.append(f"name (declared {full_name!r} vs registry {record.full_name!r})")
    if date_of_birth and date_of_birth.strip() != record.date_of_birth.strip():
        mismatched.append(f"date of birth (declared {date_of_birth!r} vs registry {record.date_of_birth!r})")
    if nationality and not _nationality_match(nationality, record.nationality):
        mismatched.append(f"nationality (declared {nationality!r} vs registry {record.nationality!r})")

    if mismatched:
        return CitizenRegistryResult(
            status="MISMATCH",
            reason=(
                f"document number {document_number!r} is on file for a different identity than declared: "
                + "; ".join(mismatched)
            ),
            mismatched_fields=mismatched,
        )

    if record.status != "ACTIVE":
        return CitizenRegistryResult(
            status="REVOKED_MATCH",
            reason=(
                f"identity matches the citizen registry record for {record.full_name!r}, but that "
                f"document's registry status is {record.status}, not ACTIVE"
            ),
        )

    return CitizenRegistryResult(
        status="MATCH",
        reason=(
            f"document number, name, date of birth, and nationality all match the citizen "
            f"registry record for {record.full_name!r}"
        ),
    )
