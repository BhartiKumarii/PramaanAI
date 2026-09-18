"""Citizen-registry lookup result — the positive-verification counterpart
to app/services/registry/base.py's blacklist-only RegistryLookupResult:
"does this document number belong to this declared person" rather than
only "is this person flagged." MATCH/NO_RECORD both carry zero risk (an
unseeded document is not evidence of anything, in a small demo dataset
that was never meant to cover every real document) — only MISMATCH
(same document number, different real attributes on file) is a genuine
signal."""
from pydantic import BaseModel


class CitizenRegistryResult(BaseModel):
    status: str  # MATCH | MISMATCH | NO_RECORD
    reason: str
    mismatched_fields: list[str] = []
    location: None = None  # not spatially applicable — a DB record, not an image region
