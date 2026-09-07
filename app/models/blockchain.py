from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class BlockchainBlock(Base):
    """A local, mock hash-chained ledger — NOT a real blockchain: no
    consensus, no distribution, no network. Each block's `block_hash` is
    SHA-256 of its own data hash plus the previous block's hash, which
    makes retroactively editing any block detectable (every later block's
    hash would stop matching). Stores only hashes/references, never PII.
    """

    __tablename__ = "blockchain_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    verification_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    issuer_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    document_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    block_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
