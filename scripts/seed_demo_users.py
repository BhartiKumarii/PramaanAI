"""Idempotent demo seeder — checkpoints + demo officer accounts, so the
Android app and web console both have something real to log into. Safe to
run on every container start (local docker-compose and the Render deploy
both do this): skips any checkpoint/username that already exists rather
than erroring or overwriting.

Password is read from the DEMO_USER_PASSWORD env var so it isn't hardcoded
in source; docker-compose.yml and render.yaml both default it to the value
already used for local testing (BorderShield123) unless overridden.

Usage (from project root):
    python -m scripts.seed_demo_users
"""
import os

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.checkpoint import Checkpoint
from app.models.user import User, UserRole

DEMO_CHECKPOINTS = [
    ("SUN", "Sunauli", "Uttar Pradesh, India / Nepal border"),
    ("JGN", "Jaigaon", "West Bengal, India / Bhutan border"),
    ("RAX", "Raxaul", "Bihar, India / Nepal border"),
]

# (username, checkpoint_code | None, role)
DEMO_ACCOUNTS: list[tuple[str, str | None, UserRole]] = [
    ("sunauli_officer", "SUN", UserRole.OFFICER),
    ("jaigaon_officer", "JGN", UserRole.OFFICER),
    ("raxaul_officer", "RAX", UserRole.OFFICER),
    ("officer1", None, UserRole.OFFICER),  # backward compatibility
    ("admin_reviewer", None, UserRole.REVIEWER),  # web admin / verifier
    ("it_admin", None, UserRole.REVIEWER),  # web console login (REVIEWER = full web admin)
]


# Earlier demo posts were outside SSB's borders (Attari-Wagah: Pakistan,
# Petrapole: Bangladesh). Existing rows are renamed in place so their cases,
# devices and audit history stay linked; nothing is deleted.
RENAMED_CHECKPOINTS = {"ATW": "SUN", "PET": "JGN"}
RENAMED_USERS = {"attari_officer": "sunauli_officer", "petrapole_officer": "jaigaon_officer"}


def _rename_earlier_demo_posts(db) -> None:
    new_by_code = {code: (name, location) for code, name, location in DEMO_CHECKPOINTS}
    for old, new in RENAMED_CHECKPOINTS.items():
        row = db.query(Checkpoint).filter(Checkpoint.code == old).first()
        if row and not db.query(Checkpoint).filter(Checkpoint.code == new).first():
            row.code, (row.name, row.location) = new, new_by_code[new]
            db.commit()
            print(f"Renamed checkpoint '{old}' to '{new}' ({row.name}).")
    for old, new in RENAMED_USERS.items():
        row = db.query(User).filter(User.username == old).first()
        if row and not db.query(User).filter(User.username == new).first():
            row.username = new
            db.commit()
            print(f"Renamed user '{old}' to '{new}'.")


def seed_demo_users() -> None:
    password = os.environ.get("DEMO_USER_PASSWORD", "BorderShield123")
    db = SessionLocal()
    try:
        _rename_earlier_demo_posts(db)
        checkpoints_by_code: dict[str, Checkpoint] = {}
        for code, name, location in DEMO_CHECKPOINTS:
            existing = db.query(Checkpoint).filter(Checkpoint.code == code).first()
            if existing:
                checkpoints_by_code[code] = existing
                continue
            checkpoint = Checkpoint(code=code, name=name, location=location)
            db.add(checkpoint)
            db.commit()
            db.refresh(checkpoint)
            checkpoints_by_code[code] = checkpoint
            print(f"Created checkpoint '{code}' ({name}).")

        for username, checkpoint_code, role in DEMO_ACCOUNTS:
            checkpoint_id = checkpoints_by_code[checkpoint_code].id if checkpoint_code else None
            existing = db.query(User).filter(User.username == username).first()
            if existing:
                if existing.checkpoint_id is None and checkpoint_id is not None:
                    existing.checkpoint_id = checkpoint_id
                    db.commit()
                    print(f"User '{username}' already exists; backfilled checkpoint_id.")
                else:
                    print(f"User '{username}' already exists (role={existing.role.value}); skipping.")
                continue
            user = User(
                username=username,
                hashed_password=hash_password(password),
                role=role,
                checkpoint_id=checkpoint_id,
            )
            db.add(user)
            db.commit()
            print(f"Created {role.value} user '{username}'.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_users()