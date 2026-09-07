from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.execute(select(User).where(User.username == username)).scalar_one_or_none()
