"""AES-256-GCM envelope encryption for any sensitive column we choose to retain.

Key comes from Settings.encryption_key (env var in dev). In production this
should be sourced from a KMS/HSM instead of a raw env var — swap _load_key()
for a KMS client call; callers don't need to change.
"""
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

_NONCE_SIZE = 12  # 96-bit nonce, recommended size for AES-GCM


def _load_key() -> bytes:
    settings = get_settings()
    key = base64.b64decode(settings.encryption_key)
    if len(key) != 32:
        raise ValueError("ENCRYPTION_KEY must base64-decode to exactly 32 bytes for AES-256-GCM")
    return key


def encrypt(plaintext: bytes, associated_data: bytes | None = None) -> bytes:
    aesgcm = AESGCM(_load_key())
    nonce = os.urandom(_NONCE_SIZE)
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)
    return nonce + ciphertext


def decrypt(blob: bytes, associated_data: bytes | None = None) -> bytes:
    aesgcm = AESGCM(_load_key())
    nonce, ciphertext = blob[:_NONCE_SIZE], blob[_NONCE_SIZE:]
    return aesgcm.decrypt(nonce, ciphertext, associated_data)
