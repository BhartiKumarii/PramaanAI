"""Blockchain fingerprint verification endpoint — a local mock hash
chain, not a real distributed ledger (see
app/services/blockchain/local_hash_chain.py)."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_blockchain_service
from app.core.security import get_current_user
from app.models.user import User
from app.services.blockchain.base import BlockchainService

router = APIRouter(prefix="/blockchain", tags=["blockchain"])


class BlockchainVerifyRequest(BaseModel):
    verification_id: str


class BlockchainVerifyResponse(BaseModel):
    verification_id: str
    chain_valid: bool
    record: dict | None


@router.post(
    "/verify",
    response_model=BlockchainVerifyResponse,
    summary="Recompute the mock hash chain up to this verification's block and confirm it's unbroken",
)
def verify_blockchain_record(
    payload: BlockchainVerifyRequest,
    _user: User = Depends(get_current_user),
    blockchain_service: BlockchainService = Depends(get_blockchain_service),
) -> BlockchainVerifyResponse:
    record = blockchain_service.get_verification_record(payload.verification_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="no blockchain record for this verification_id"
        )
    chain_valid = blockchain_service.verify_record(payload.verification_id)
    return BlockchainVerifyResponse(verification_id=payload.verification_id, chain_valid=chain_valid, record=record)
