"""Idempotent demo seeder for cases and verification records — so the
web console dashboard has real data to display instead of all zeros.
Safe to run on every container start (local docker-compose and Render
both do this): skips any case_number that already exists.
"""
import uuid
from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.models.case import Case, CasePriority, CaseStatus
from app.models.checkpoint import Checkpoint
from app.models.user import User, UserRole
from app.models.verification import VerificationRecord


DEMO_CASES = [
    # (case_number, status, priority, checkpoint_code, field_officer_username,
    #  document_type, nationality, traveler_name, created_days_ago, decided_days_ago)
    ("BSA-20260916-0001", CaseStatus.CLEAR, CasePriority.LOW, "ATW", "attari_officer",
     "passport", "INDIAN", "JOHN MICHAEL SMITH", 5, 4),
    ("BSA-20260916-0002", CaseStatus.REVIEW_REQUIRED, CasePriority.HIGH, "ATW", "attari_officer",
     "passport", "INDIAN", "BLACKLISTED PERSON", 3, None),
    ("BSA-20260916-0003", CaseStatus.SENT, CasePriority.MEDIUM, "ATW", "attari_officer",
     "passport", "INDIAN", "RAKESH KUMAR MALHOTRA", 2, None),
    ("BSA-20260916-0004", CaseStatus.PENDING, CasePriority.LOW, "PET", "petrapole_officer",
     "passport", "INDIAN", "PRIYA RAMESH NAIR", 1, None),
    ("BSA-20260916-0005", CaseStatus.CLEAR, CasePriority.LOW, "PET", "petrapole_officer",
     "passport", "NEPALI", "BIKRAM THAPA MAGAR", 7, 6),
    ("BSA-20260916-0006", CaseStatus.SECONDARY_REVIEW, CasePriority.HIGH, "PET", "petrapole_officer",
     "visa", "INDIAN", "SURESH CHANDRA GUPTA", 4, None),
    ("BSA-20260916-0007", CaseStatus.HOLD_REFER, CasePriority.HIGH, "RAX", "raxaul_officer",
     "passport", "INDIAN", "VIJAY PRATAP SINGH", 2, None),
    ("BSA-20260916-0008", CaseStatus.CLEAR, CasePriority.MEDIUM, "RAX", "raxaul_officer",
     "national_id", "INDIAN", "ARUN PRAKASH TIWARI", 6, 5),
    ("BSA-20260916-0009", CaseStatus.PENDING_SYNC, CasePriority.LOW, "RAX", "raxaul_officer",
     "passport", "BHUTANESE", "TASHI WANGCHUK DORJI", 0, None),
    ("BSA-20260916-0010", CaseStatus.SENT, CasePriority.MEDIUM, "ATW", "officer1",
     "driving_licence", "INDIAN", "SANJAY DUTT BHATIA", 3, None),
    ("BSA-20260916-0011", CaseStatus.REVIEW_REQUIRED, CasePriority.HIGH, "PET", "officer1",
     "passport", "INDIAN", "ASHOK KUMAR PANDEY", 1, None),
    ("BSA-20260916-0012", CaseStatus.CLEAR, CasePriority.LOW, "RAX", "officer1",
     "visa", "INDIAN", "DEEPIKA RANI VERMA", 8, 7),
]


DEMO_VERIFICATIONS = [
    # (document_type, nationality, traveler_name, score, level, decision, top_reason)
    ("passport", "INDIAN", "JOHN MICHAEL SMITH", 15, "LOW_RISK", "CLEAR", "All validation checks passed"),
    ("passport", "INDIAN", "BLACKLISTED PERSON", 85, "HIGH_RISK", "MANUAL_REVIEW", "Blacklisted document number matched"),
    ("passport", "INDIAN", "RAKESH KUMAR MALHOTRA", 45, "MEDIUM_RISK", "MANUAL_REVIEW", "Watchlist entry found - reported lost/stolen document"),
    ("passport", "INDIAN", "PRIYA RAMESH NAIR", 20, "LOW_RISK", "CLEAR", "All validation checks passed"),
    ("passport", "NEPALI", "BIKRAM THAPA MAGAR", 10, "LOW_RISK", "CLEAR", "All validation checks passed"),
    ("visa", "INDIAN", "SURESH CHANDRA GUPTA", 75, "HIGH_RISK", "MANUAL_REVIEW", "Document expired"),
    ("passport", "INDIAN", "VIJAY PRATAP SINGH", 90, "HIGH_RISK", "MANUAL_REVIEW", "Blacklisted document number matched"),
    ("national_id", "INDIAN", "ARUN PRAKASH TIWARI", 18, "LOW_RISK", "CLEAR", "All validation checks passed"),
    ("passport", "BHUTANESE", "TASHI WANGCHUK DORJI", 22, "LOW_RISK", "CLEAR", "All validation checks passed"),
    ("driving_licence", "INDIAN", "SANJAY DUTT BHATIA", 30, "LOW_RISK", "CLEAR", "All validation checks passed"),
    ("passport", "INDIAN", "ASHOK KUMAR PANDEY", 65, "HIGH_RISK", "MANUAL_REVIEW", "Visa overstay reported"),
    ("visa", "INDIAN", "DEEPIKA RANI VERMA", 12, "LOW_RISK", "CLEAR", "All validation checks passed"),
]


def seed_demo_cases() -> None:
    db = SessionLocal()
    try:
        # Get checkpoint and officer mappings
        checkpoints = {cp.code: cp for cp in db.query(Checkpoint).all()}
        officers = {u.username: u for u in db.query(User).filter(User.role == UserRole.OFFICER).all()}

        if not checkpoints:
            print("No checkpoints found; skipping case seeding.")
            return
        if not officers:
            print("No officers found; skipping case seeding.")
            return

        # Import required for breakdown_json
        import json

        for i, (case_number, status, priority, checkpoint_code, field_officer_username,
                document_type, nationality, traveler_name, created_days_ago, decided_days_ago) in enumerate(DEMO_CASES):

            existing = db.query(Case).filter(Case.case_number == case_number).first()
            if existing:
                print(f"Case '{case_number}' already exists; skipping.")
                continue

            checkpoint = checkpoints.get(checkpoint_code)
            field_officer = officers.get(field_officer_username)

            if not checkpoint:
                print(f"Checkpoint '{checkpoint_code}' not found for case '{case_number}'; skipping.")
                continue
            if not field_officer:
                print(f"Officer '{field_officer_username}' not found for case '{case_number}'; skipping.")
                continue

            created_at = datetime.now(timezone.utc) - timedelta(days=created_days_ago)
            decided_at = None
            if decided_days_ago is not None:
                decided_at = datetime.now(timezone.utc) - timedelta(days=decided_days_ago)

            # Create verification record first
            if i < len(DEMO_VERIFICATIONS):
                (v_doc_type, v_nationality, v_traveler_name, v_score, v_level, v_decision, v_top_reason) = DEMO_VERIFICATIONS[i]
            else:
                (v_doc_type, v_nationality, v_traveler_name, v_score, v_level, v_decision, v_top_reason) = DEMO_VERIFICATIONS[0]

            verification = VerificationRecord(
                id=uuid.uuid4(),
                document_type=v_doc_type,
                nationality=v_nationality,
                traveler_name=v_traveler_name,
                score=v_score,
                level=v_level,
                decision=v_decision,
                top_reason=v_top_reason,
                breakdown_json=json.dumps({
                    "signals": [
                        {"signal": "ocr", "weight": 0.15, "raw_risk": 10, "contribution": 1.5, "reason": "OCR validation passed"},
                        {"signal": "validation", "weight": 0.20, "raw_risk": 5, "contribution": 1.0, "reason": "Cross-field validation passed"},
                        {"signal": "tampering", "weight": 0.25, "raw_risk": 5, "contribution": 1.25, "reason": "No tampering detected"},
                        {"signal": "deepfake", "weight": 0.15, "raw_risk": 5, "contribution": 0.75, "reason": "No deepfake detected"},
                        {"signal": "registry", "weight": 0.15, "raw_risk": 5, "contribution": 0.75, "reason": "Registry check passed"},
                        {"signal": "face", "weight": 0.10, "raw_risk": 5, "contribution": 0.5, "reason": "Face match passed"},
                    ]
                }),
                signature="0" * 64,  # placeholder signature
                created_at=created_at,
            )
            db.add(verification)
            db.flush()

            case = Case(
                id=uuid.uuid4(),
                case_number=case_number,
                status=status,
                priority=priority,
                checkpoint_id=checkpoint.id,
                field_officer_id=field_officer.id,
                assigned_officer_id=field_officer.id,
                verification_id=verification.id,
                document_type=document_type,
                nationality=nationality,
                traveler_name=traveler_name,
                created_at=created_at,
                sent_at=created_at + timedelta(hours=1) if status != CaseStatus.PENDING_SYNC else None,
                decided_at=decided_at,
            )
            db.add(case)
            print(f"Created demo case '{case_number}' with verification {verification.id}")

        db.commit()
        print("Demo case seeding complete.")

        _seed_demo_devices(db)
    finally:
        db.close()


DEMO_DEVICES = [
    ("SM-G998B_ATW01", "attari_officer", "1.0.0"),
    ("SM-A545F_ATW02", "attari_officer", "1.0.0"),
    ("Pixel_8_PET01", "petrapole_officer", "1.0.0"),
    ("SM-G991B_RAX01", "raxaul_officer", "0.9.2"),
    ("Redmi_Note_JAI01", "jaigaon_officer", "1.0.0"),
    ("OnePlus_12_GEL01", "gelephu_officer", "1.0.0"),
]


def _seed_demo_devices(db):
    from app.models.device import Device

    for dev_id, officer_username, app_ver in DEMO_DEVICES:
        existing = db.query(Device).filter(Device.device_identifier == dev_id).first()
        if existing:
            continue
        officer = db.query(User).filter(User.username == officer_username).first()
        if not officer:
            continue
        device = Device(
            device_identifier=dev_id,
            officer_id=uuid.UUID(officer.id) if isinstance(officer.id, str) else officer.id,
            app_version=app_ver,
            last_active_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        db.add(device)
        print(f"Created demo device '{dev_id}' for {officer_username}")
    db.commit()
    print("Demo device seeding complete.")


if __name__ == "__main__":
    seed_demo_cases()