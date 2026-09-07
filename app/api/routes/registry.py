"""Mock central registry endpoints (Module 5): dev-only seeding plus a
real SQL lookup — exact document-number match and fuzzy name match
against a seeded `mock_central_registry` table. Never a real government
registry integration.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories.registry_repository import insert_entries
from app.schemas.registry import RegistryLookupRequest, RegistrySeedRequest, RegistrySeedResponse
from app.services.registry.base import RegistryLookupResult
from app.services.registry.lookup import lookup_registry

router = APIRouter(prefix="/registry", tags=["registry"])

_DEFAULT_SEED_ENTRIES = [
    {
        "document_number": "N7654321",
        "full_name": "RAVI KUMAR SHARMA",
        "reason": "reported lost/stolen document",
        "severity": "MEDIUM",
    },
    {
        "document_number": "X1122334",
        "full_name": "MOHAMMED ASIF KHAN",
        "reason": "overstay violation on prior crossing",
        "severity": "HIGH",
    },
    {
        "document_number": "B9988001",
        "full_name": "SITA DEVI THAPA",
        "reason": "watchlist — prior smuggling investigation",
        "severity": "HIGH",
    },
]


@router.post(
    "/seed",
    response_model=RegistrySeedResponse,
    summary="Dev-only: seed mock_central_registry with synthetic entries",
)
def seed_registry(
    payload: RegistrySeedRequest | None = None,
    _user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> RegistrySeedResponse:
    entries = (
        [entry.model_dump() for entry in payload.entries]
        if payload and payload.entries
        else _DEFAULT_SEED_ENTRIES
    )
    count = insert_entries(db, entries)
    return RegistrySeedResponse(seeded=count)


@router.post(
    "/lookup",
    response_model=RegistryLookupResult,
    summary="Look up a document number (exact) and/or name (fuzzy) against mock_central_registry",
)
def lookup(
    payload: RegistryLookupRequest,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RegistryLookupResult:
    return lookup_registry(db, payload.document_number, payload.name)
