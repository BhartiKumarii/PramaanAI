from sqlalchemy.orm import Session

from app.repositories.registry_repository import find_by_document_number, list_all_entries
from app.services.registry.base import RegistryHit, RegistryLookupResult
from app.services.registry.fuzzy import DEFAULT_FUZZY_THRESHOLD, name_similarity


def lookup_registry(
    db: Session,
    document_number: str | None,
    name: str | None,
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
) -> RegistryLookupResult:
    hits: list[RegistryHit] = []

    if document_number:
        exact = find_by_document_number(db, document_number)
        if exact is not None:
            hits.append(
                RegistryHit(
                    document_number=exact.document_number,
                    full_name=exact.full_name,
                    registry_reason=exact.reason,
                    severity=exact.severity,
                    match_type="EXACT",
                    confidence=1.0,
                    matched_field="document_number",
                    explanation=(
                        f"document number {document_number!r} exactly matches registry "
                        f"entry {exact.document_number!r} ({exact.full_name})"
                    ),
                )
            )

    if name:
        for entry in list_all_entries(db):
            similarity = name_similarity(name, entry.full_name)
            if similarity >= fuzzy_threshold:
                hits.append(
                    RegistryHit(
                        document_number=entry.document_number,
                        full_name=entry.full_name,
                        registry_reason=entry.reason,
                        severity=entry.severity,
                        match_type="FUZZY",
                        confidence=round(similarity, 4),
                        matched_field="full_name",
                        explanation=(
                            f"name {name!r} is {similarity:.2%} similar to registry entry "
                            f"name {entry.full_name!r} (threshold {fuzzy_threshold:.0%})"
                        ),
                    )
                )

    return RegistryLookupResult(status="HIT" if hits else "NO_HIT", hits=hits)
