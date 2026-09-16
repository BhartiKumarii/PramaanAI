import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class UserRole(str, enum.Enum):
    # Scans documents in the field via the Android app, forwards cases —
    # never makes the final clear/hold decision.
    FIELD_OFFICER = "FIELD_OFFICER"
    # Reviews forwarded cases on the web console and makes the authorised
    # clear / secondary-review / hold decision.
    IMMIGRATION_OFFICER = "IMMIGRATION_OFFICER"
    SUPERVISOR = "SUPERVISOR"
    IT_ADMIN = "IT_ADMIN"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), nullable=False, default=UserRole.FIELD_OFFICER
    )
    checkpoint_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("checkpoints.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
