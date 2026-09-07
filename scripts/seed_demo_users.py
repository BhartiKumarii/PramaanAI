"""Idempotent demo-account seeder — creates the two accounts the Android
app's officer console has been tested against, if they don't already exist.
Safe to run on every container start (local docker-compose and the Render
deploy both do this): skips any username that's already present rather than
erroring or overwriting.

Password is read from the DEMO_USER_PASSWORD env var so it isn't hardcoded
in source; docker-compose.yml and render.yaml both default it to the value
already used for local testing (BorderShield123) unless overridden.

Usage (from project root):
    python -m scripts.seed_demo_users
"""
import os

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole

DEMO_ACCOUNTS = [
    ("attari_officer", UserRole.OFFICER),
    ("officer1", UserRole.ADMIN),
]


def seed_demo_users() -> None:
    password = os.environ.get("DEMO_USER_PASSWORD", "BorderShield123")
    db = SessionLocal()
    try:
        for username, role in DEMO_ACCOUNTS:
            existing = db.query(User).filter(User.username == username).first()
            if existing:
                print(f"User '{username}' already exists (role={existing.role.value}); skipping.")
                continue
            user = User(username=username, hashed_password=hash_password(password), role=role)
            db.add(user)
            db.commit()
            print(f"Created {role.value} user '{username}'.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_users()
