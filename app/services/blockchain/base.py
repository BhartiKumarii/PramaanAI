"""Blockchain adapter interface. Concrete implementation (local/mock
hash-chained ledger — no PII, fingerprint only) is Module 8, not yet
built."""
from abc import ABC, abstractmethod

from pydantic import BaseModel


class BlockchainRecordResult(BaseModel):
    recorded: bool
    fingerprint: str
    block_reference: str | None = None


class BlockchainService(ABC):
    @abstractmethod
    def create_verification_record(
        self, verification_id: str, document_hash: str, issuer_reference: str, event_type: str
    ) -> BlockchainRecordResult:
        """Append a hash-only verification fingerprint to the (mock/local) chain."""

    @abstractmethod
    def verify_record(self, verification_id: str) -> bool:
        """Recompute/compare the stored fingerprint to detect audit-trail tampering."""

    @abstractmethod
    def get_verification_record(self, verification_id: str) -> dict | None:
        """Fetch a stored blockchain record by verification id."""
