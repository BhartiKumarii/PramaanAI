import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class Device(Base):
    """A registered Android field-officer device. `is_disabled` is the
    IT/Admin "disable lost device" control — a disabled device's tokens
    are still valid JWTs (auth isn't wired to device state yet), so this
    is currently advisory/reporting only, not an enforced kill-switch."""

    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_identifier: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    officer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    app_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_disabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
