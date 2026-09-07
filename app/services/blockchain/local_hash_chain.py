from sqlalchemy.orm import Session

from app.repositories.blockchain_repository import (
    GENESIS_HASH,
    append_block,
    compute_block_hash,
    compute_data_hash,
    find_block_by_verification_id,
    list_blocks_up_to,
)
from app.services.blockchain.base import BlockchainRecordResult, BlockchainService


class LocalHashChainBlockchainService(BlockchainService):
    """Real hash-chain append + real chain-integrity recomputation — a
    local mock, explicitly not a distributed ledger."""

    def __init__(self, db: Session):
        self._db = db

    def create_verification_record(
        self, verification_id: str, document_hash: str, issuer_reference: str, event_type: str
    ) -> BlockchainRecordResult:
        block = append_block(self._db, verification_id, document_hash, issuer_reference, event_type)
        return BlockchainRecordResult(recorded=True, fingerprint=block.block_hash, block_reference=str(block.id))

    def verify_record(self, verification_id: str) -> bool:
        block = find_block_by_verification_id(self._db, verification_id)
        if block is None:
            return False

        previous_hash = GENESIS_HASH
        for entry in list_blocks_up_to(self._db, block.id):
            expected_data_hash = compute_data_hash(
                entry.verification_id, entry.document_hash, entry.issuer_reference, entry.event_type
            )
            expected_block_hash = compute_block_hash(previous_hash, expected_data_hash)
            if entry.previous_hash != previous_hash or entry.block_hash != expected_block_hash:
                return False
            previous_hash = entry.block_hash
        return True

    def get_verification_record(self, verification_id: str) -> dict | None:
        block = find_block_by_verification_id(self._db, verification_id)
        if block is None:
            return None
        return {
            "verification_id": block.verification_id,
            "event_type": block.event_type,
            "issuer_reference": block.issuer_reference,
            "document_hash": block.document_hash,
            "previous_hash": block.previous_hash,
            "block_hash": block.block_hash,
            "block_reference": str(block.id),
            "created_at": block.created_at.isoformat(),
        }
