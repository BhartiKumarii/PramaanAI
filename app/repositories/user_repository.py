import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.case import Case
from app.models.checkpoint import Checkpoint
from app.models.user import User, UserRole


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.execute(select(User).where(User.username == username)).scalar_one_or_none()


def officer_roster(db: Session) -> list[dict]:
    """Officers with a real case count each — the "Officers" monitoring view. 
    Case counts come from a real GROUP BY, never estimated."""
    officers = list(
        db.execute(
            select(User)
            .where(User.role == UserRole.OFFICER)
            .order_by(User.created_at.desc())
        ).scalars()
    )
    counts = dict(
        db.execute(
            select(Case.field_officer_id, func.count()).group_by(Case.field_officer_id)
        ).all()
    )
    checkpoints = {cp.id: cp.code for cp in db.execute(select(Checkpoint)).scalars()}
    return [
        {
            "id": str(o.id),
            "username": o.username,
            "role": o.role.value,
            "checkpoint_code": checkpoints.get(o.checkpoint_id) if o.checkpoint_id else None,
            "is_active": o.is_active,
            "case_count": counts.get(o.id, 0),
        }
        for o in officers
    ]


def get_user(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def list_users(db: Session) -> list[User]:
    return list(db.execute(select(User).order_by(User.created_at.desc())).scalars())


def create_user(
    db: Session, username: str, password: str, role: UserRole, checkpoint_id: uuid.UUID | None
) -> User:
    user = User(username=username, hashed_password=hash_password(password), role=role, checkpoint_id=checkpoint_id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db: Session,
    user: User,
    role: UserRole | None = None,
    checkpoint_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    new_password: str | None = None,
) -> User:
    if role is not None:
        user.role = role
    if checkpoint_id is not None:
        user.checkpoint_id = checkpoint_id
    if is_active is not None:
        user.is_active = is_active
    if new_password is not None:
        user.hashed_password = hash_password(new_password)
    db.commit()
    db.refresh(user)
    return user
