import uuid
from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class StoredImage(Base):
    __tablename__ = "stored_images"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    verification_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    image_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False, default="image/jpeg")
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
