import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.blockchain import BlockchainBlock

GENESIS_HASH = "0" * 64


def compute_data_hash(verification_id: str, document_hash: str, issuer_reference: str, event_type: str) -> str:
    payload = f"{verification_id}|{document_hash}|{issuer_reference}|{event_type}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_block_hash(previous_hash: str, data_hash: str) -> str:
    return hashlib.sha256(f"{previous_hash}|{data_hash}".encode("utf-8")).hexdigest()


def get_latest_block(db: Session) -> BlockchainBlock | None:
    return db.execute(select(BlockchainBlock).order_by(BlockchainBlock.id.desc()).limit(1)).scalar_one_or_none()


def append_block(
    db: Session, verification_id: str, document_hash: str, issuer_reference: str, event_type: str
) -> BlockchainBlock:
    latest = get_latest_block(db)
    previous_hash = latest.block_hash if latest is not None else GENESIS_HASH
    data_hash = compute_data_hash(verification_id, document_hash, issuer_reference, event_type)
    block = BlockchainBlock(
        verification_id=verification_id,
        event_type=event_type,
        issuer_reference=issuer_reference,
        document_hash=document_hash,
        previous_hash=previous_hash,
        block_hash=compute_block_hash(previous_hash, data_hash),
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


def find_block_by_verification_id(db: Session, verification_id: str) -> BlockchainBlock | None:
    return db.execute(
        select(BlockchainBlock).where(BlockchainBlock.verification_id == verification_id)
    ).scalar_one_or_none()


def list_blocks_up_to(db: Session, block_id: int) -> list[BlockchainBlock]:
    return list(
        db.execute(
            select(BlockchainBlock).where(BlockchainBlock.id <= block_id).order_by(BlockchainBlock.id)
        ).scalars()
    )
