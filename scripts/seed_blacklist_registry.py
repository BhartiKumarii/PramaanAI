"""Idempotent demo seeder for the mock watchlist/blacklist registry.
All entries are synthetic — explicitly labelled as mock/demo data.
No real government watchlist access exists in this build (see CLAUDE.md).

Document numbers marked FORGERY use real format numbers seen in the test
dataset but are here treated as synthetic demo cases of known fraudulent
use — NOT assertions about the real people in those documents.

Usage:
    python -m scripts.seed_blacklist_registry
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.registry import MockCentralRegistryEntry

# (document_number, full_name, reason, severity)
DEMO_ENTRIES = [
    # ── Baseline demo entry ──────────────────────────────────────────────────
    (
        "BLACKLIST001",
        "BLACKLISTED PERSON",
        "demo watchlist entry — reported overstay violation (synthetic)",
        "HIGH",
    ),

    # ── Synthetic Indian names ───────────────────────────────────────────────
    ("D5566778", "RAKESH KUMAR MALHOTRA",
     "reported lost/stolen document — filed at Attari-Wagah checkpoint (synthetic)",
     "MEDIUM"),
    ("D9988112", "VIJAY PRATAP SINGH",
     "forged document history — same number appeared on two different identity records (synthetic)",
     "HIGH"),
    ("D3344556", "ASHOK KUMAR PANDEY",
     "visa overstay violation — 14 months beyond permitted stay (synthetic)",
     "LOW"),

    # ── India Visa — expired document reported used in forged entry ──────────
    # AF 713645 from dataset (India tourist visa, expired 22-02-2009).
    # Treated as demo case: document number reported used in a forged
    # secondary crossing after original expiry. NOT a statement about
    # the real holder.
    ("AF713645",
     "DEMO — VISA FORGERY CASE",
     "India tourist visa AF713645 (expired Feb 2009) — document number "
     "reported used in attempted border crossing 4 months after expiry; "
     "suspected forged validity date (synthetic demo entry)",
     "HIGH"),

    # ── India DL — expired and reported blacklisted ──────────────────────────
    # GJ05-19940112841 from dataset (Chetan Chauhan, Gujarat DL).
    # Expired 01/01/2024. Demo scenario: reported stolen after expiry.
    ("GJ0519940112841",
     "DEMO — EXPIRED DL REPORTED STOLEN",
     "India Gujarat DL expired 01/01/2024 — reported as stolen document "
     "after expiry; document number flagged for possible fraudulent reuse (synthetic demo entry)",
     "MEDIUM"),

    # MH13-20070019358 from dataset (Suryakant Birajdar, Maharashtra DL).
    # Expired 06/12/2016. Demo scenario: repeated overstay violations.
    ("MH1320070019358",
     "DEMO — MULTIPLE OVERSTAY VIOLATIONS",
     "India Maharashtra DL expired 06/12/2016 — associated with 3 recorded "
     "overstay violations across Raxaul and Sonali checkpoints (synthetic demo entry)",
     "HIGH"),

    # ── Nepal NRI Card — expired and suspected forged reuse ──────────────────
    # KATH-B/1 from dataset (Dev Man Hirachan, NRI Identity Card).
    # Expired 10 FEB 2012. Demo: reported used in forged identity claim.
    ("KATH-B/1",
     "DEMO — EXPIRED NRI CARD FORGERY",
     "Nepal NRI Identity Card KATH-B/1 expired 10/02/2012 — reported used in "
     "an attempted forged identity claim at Raxaul checkpoint (synthetic demo entry)",
     "HIGH"),

    # ── Additional synthetic entries for diverse test coverage ───────────────
    ("NP334455", "KAMAL BAHADUR THAPA",
     "associated with document trafficking network — multiple passports "
     "carrying same biometric data (synthetic)",
     "HIGH"),
    ("IND778899", "RAMESH PRASAD YADAV",
     "reported match on INTERPOL orange notice — financial crimes (synthetic)",
     "MEDIUM"),
    ("BT556677", "TENZIN NORBU WANGDI",
     "overstay violation — Bhutan entry permit expired (synthetic)",
     "LOW"),
    ("VIS001122", "DEMO VISA HOLDER",
     "visa used beyond permitted period — 60 days beyond expiry (synthetic)",
     "MEDIUM"),
    # Permit forgery case
    ("ILP-AR-2024-0091",
     "DEMO — FORGED ILP",
     "Arunachal Pradesh ILP — document number forged; seal does not match "
     "issuing authority records (synthetic demo entry)",
     "HIGH"),
]


def _find_by_document_number(db: Session, document_number: str) -> MockCentralRegistryEntry | None:
    return db.execute(
        select(MockCentralRegistryEntry).where(MockCentralRegistryEntry.document_number == document_number)
    ).scalar_one_or_none()


def seed_blacklist_registry() -> None:
    db = SessionLocal()
    try:
        added = 0
        for document_number, full_name, reason, severity in DEMO_ENTRIES:
            if _find_by_document_number(db, document_number) is not None:
                print(f"  skip  '{document_number}' — already exists.")
                continue
            entry = MockCentralRegistryEntry(
                document_number=document_number, full_name=full_name,
                reason=reason, severity=severity,
            )
            db.add(entry)
            db.commit()
            print(f"  added '{document_number}' ({full_name}, {severity})")
            added += 1
        print(f"Blacklist seeder: {added} new entries added.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_blacklist_registry()
