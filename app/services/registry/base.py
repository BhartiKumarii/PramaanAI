"""Blacklist/registry lookup result types — Module 5. Every hit is tagged
EXACT (document number) or FUZZY (name similarity); these are never
collapsed into a single flag, since a checkpoint officer needs to weigh
them very differently."""
from pydantic import BaseModel


class RegistryHit(BaseModel):
    document_number: str
    full_name: str
    registry_reason: str  # why the entry is listed, e.g. "overstay violation"
    severity: str  # LOW | MEDIUM | HIGH
    match_type: str  # EXACT | FUZZY
    confidence: float
    matched_field: str  # document_number | full_name
    explanation: str  # specific values compared, never a generic string
    location: None = None  # not spatially applicable — a DB record, not an image region


class RegistryLookupResult(BaseModel):
    status: str  # HIT | NO_HIT
    hits: list[RegistryHit]
