"""Dev-only seed script: creates an initial ADMIN user for local testing.
There is no public /auth/register endpoint by design — users are
provisioned out-of-band.

Usage (from project root):
    python -m scripts.seed_admin <username> <password>
"""
import sys

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole


def seed_admin(username: str, password: str) -> None:
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"User '{username}' already exists (role={existing.role.value}); skipping.")
            return
        user = User(username=username, hashed_password=hash_password(password), role=UserRole.ADMIN)
        db.add(user)
        db.commit()
        print(f"Created ADMIN user '{username}'.")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.seed_admin <username> <password>")
        raise SystemExit(1)
    seed_admin(sys.argv[1], sys.argv[2])
