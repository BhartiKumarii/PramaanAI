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
    ("ATW", "Attari-Wagah", "Punjab, India / Pakistan border"),
    ("PET", "Petrapole", "West Bengal, India / Bangladesh border"),
    ("RAX", "Raxaul", "Bihar, India / Nepal border"),
]

# (username, checkpoint_code | None, role)
DEMO_ACCOUNTS: list[tuple[str, str | None, UserRole]] = [
    ("attari_officer", "ATW", UserRole.OFFICER),
    ("petrapole_officer", "PET", UserRole.OFFICER),
    ("raxaul_officer", "RAX", UserRole.OFFICER),
    ("officer1", None, UserRole.OFFICER),  # backward compatibility
    ("admin_reviewer", None, UserRole.REVIEWER),  # web admin / verifier
]


def seed_demo_users() -> None:
    password = os.environ.get("DEMO_USER_PASSWORD", "BorderShield123")
    db = SessionLocal()
    try:
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