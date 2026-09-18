"""Duplicate/reused-document result types.

Scoped deliberately: SSB's checkpoints are open, treaty-based borders
where the same traveler legitimately re-presents the same document on
routine repeat crossings (see CLAUDE.md) — "this document number was
seen before" is normal, not fraud, and must never by itself raise risk.
The real, explainable fraud signal is the same document number being
declared under a *different* name than it was before — presented here
as its own distinct status, never collapsed with an ordinary repeat
crossing."""
from pydantic import BaseModel


class DuplicateDocumentResult(BaseModel):
    status: str  # NO_MATCH | SAME_IDENTITY_REUSE | DIFFERENT_IDENTITY_REUSE
    match_count: int
    reason: str
    location: None = None  # not spatially applicable — a DB record, not an image region
