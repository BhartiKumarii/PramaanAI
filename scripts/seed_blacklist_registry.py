"""Idempotent demo seeder for the mock watchlist/blacklist registry (see
app/models/registry.py's MockCentralRegistryEntry) — synthetic flagged-
document entries. Explicitly labeled mock — there is no real INTERPOL/
government watchlist access here or anywhere in this build (see
CLAUDE.md). Skips any document_number that already exists.

One entry ("BLACKLIST001") is deliberately aligned with
app/api/routes/testing.py's TestScenario.BLACKLISTED_DEMO_DOCUMENT,
which was, until this seeder existed, checking a table that had never
actually been seeded — the scenario existed and ran, but the blacklist
lookup it exercises had nothing to ever find a hit against.

Usage (from project root):
    python -m scripts.seed_blacklist_registry
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.registry import MockCentralRegistryEntry

# (document_number, full_name, reason, severity)
DEMO_ENTRIES = [
    (
        "BLACKLIST001",
        "BLACKLISTED PERSON",
        "demo watchlist entry — reported overstay violation (synthetic)",
        "HIGH",
    ),
    ("D5566778", "RAKESH KUMAR MALHOTRA", "demo watchlist entry — reported lost/stolen document (synthetic)", "MEDIUM"),
    ("D9988112", "VIJAY PRATAP SINGH", "demo watchlist entry — reported forged-document history (synthetic)", "HIGH"),
    ("D3344556", "ASHOK KUMAR PANDEY", "demo watchlist entry — reported visa-overstay (synthetic)", "LOW"),
]


def _find_by_document_number(db: Session, document_number: str) -> MockCentralRegistryEntry | None:
    return db.execute(
        select(MockCentralRegistryEntry).where(MockCentralRegistryEntry.document_number == document_number)
    ).scalar_one_or_none()


def seed_blacklist_registry() -> None:
    db = SessionLocal()
    try:
        for document_number, full_name, reason, severity in DEMO_ENTRIES:
            if _find_by_document_number(db, document_number) is not None:
                print(f"Blacklist entry '{document_number}' already exists; skipping.")
                continue
            entry = MockCentralRegistryEntry(
                document_number=document_number, full_name=full_name, reason=reason, severity=severity,
            )
            db.add(entry)
            db.commit()
            print(f"Created blacklist entry '{document_number}' ({full_name}, {severity}).")
    finally:
        db.close()


if __name__ == "__main__":
    seed_blacklist_registry()
