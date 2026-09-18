from sqlalchemy.orm import Session

from app.repositories.network_repository import find_persons_by_document_hash
from app.services.duplicate.base import DuplicateDocumentResult
from app.utils.masking import hash_document_number


def check_duplicate_document(
    db: Session, document_number: str | None, declared_name: str | None
) -> DuplicateDocumentResult | None:
    """Real DB lookup against every PersonEntity node already recorded for
    this document number (the same table the network graph's
    SAME_DOCUMENT_NUMBER edges read from — see app/api/routes/documents.py's
    _update_network_graph) — run here, before scoring, so the result can
    actually feed the risk engine instead of only appearing after the fact
    on the Network page."""
    if not document_number:
        return None

    doc_hash = hash_document_number(document_number)
    prior = find_persons_by_document_hash(db, doc_hash)
    if not prior:
        return DuplicateDocumentResult(
            status="NO_MATCH", match_count=0, reason="no prior record found for this document number"
        )

    declared = (declared_name or "UNKNOWN").strip().upper()
    same_identity = [p for p in prior if p.full_name.strip().upper() == declared]
    different_identity = [p for p in prior if p.full_name.strip().upper() != declared]

    if different_identity:
        other_names = sorted({p.full_name for p in different_identity})
        return DuplicateDocumentResult(
            status="DIFFERENT_IDENTITY_REUSE",
            match_count=len(different_identity),
            reason=(
                f"this document number was previously declared under {len(other_names)} different "
                f"name(s) ({', '.join(other_names)}) than the current declared name {declared_name!r}"
            ),
        )

    return DuplicateDocumentResult(
        status="SAME_IDENTITY_REUSE",
        match_count=len(same_identity),
        reason=(
            f"this document number has {len(same_identity)} prior screening(s) under the same "
            f"declared name — consistent with a routine repeat crossing, not flagged as risk"
        ),
    )
