"""Importing this package registers every model's table with
Base.metadata — required so that Base.metadata.create_all() (tests) and
alembic autogenerate see tables that aren't yet referenced by any route,
not just the ones already wired into app.main via repositories."""
from app.models.audit import AuditEvent  # noqa: F401
from app.models.blockchain import BlockchainBlock  # noqa: F401
from app.models.case import Case, CaseNote, OfficerDecision, SyncQueueItem  # noqa: F401
from app.models.checkpoint import Checkpoint  # noqa: F401
from app.models.citizen_registry import MockCitizenRegistryEntry  # noqa: F401
from app.models.device import Device  # noqa: F401
from app.models.identity_embedding import IdentityEmbeddingRecord  # noqa: F401
from app.models.network import (  # noqa: F401
    NetworkRelationship,
    PersonEntity,
    TravelEvent,
    VehicleEntity,
)
from app.models.registry import MockCentralRegistryEntry  # noqa: F401
from app.models.user import User, UserRole  # noqa: F401
from app.models.verification import VerificationRecord  # noqa: F401
