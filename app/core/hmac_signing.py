"""HMAC-SHA256 signing for stored risk score records: sign on write,
verify on read. Canonicalizes the payload (sorted keys, no whitespace) so
signing and verification always hash the exact same bytes regardless of
dict ordering.
"""
import hashlib
import hmac
import json
from typing import Any

from app.core.config import get_settings


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def sign(payload: dict[str, Any]) -> str:
    settings = get_settings()
    key = settings.hmac_secret_key.encode("utf-8")
    return hmac.new(key, _canonical_bytes(payload), hashlib.sha256).hexdigest()


def verify(payload: dict[str, Any], signature: str) -> bool:
    expected = sign(payload)
    return hmac.compare_digest(expected, signature)
