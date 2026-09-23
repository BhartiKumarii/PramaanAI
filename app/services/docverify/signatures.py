"""Digital-signature verification — strictly separated from visual signatures.

Three different things, never conflated:

  VISUAL_SIGNATURE   a picture of a handwritten signature in the image.
                     Proves nothing cryptographically; reported as such.
  CRYPTOGRAPHIC      a real digital signature over document data, verified
                     with the `cryptography` library against a configured
                     trust anchor (reference_data/trust/). Checks key
                     trust/validity and whether the data changed after signing.
  OFFICIAL_ONLY      signatures that may only be verified by the issuing
                     authority's official mechanism (UIDAI Secure QR,
                     ePassport chip PKI). Never opened or bypassed here ->
                     OFFICIAL_VERIFICATION_REQUIRED.

PDF signatures: presence is detected from the /ByteRange + /Contents
structure; full CMS/PAdES validation needs `pyhanko` plus configured trust
roots. Without them the result is NOT_VERIFIED — never a pass.

Trust anchors in this build are SYNTHETIC test issuers only (see
reference_data/trust/synthetic_issuers.json). A real deployment must replace
them with the issuing authorities' published certificates.
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import date
from functools import lru_cache
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from app.services.docverify import reference

SIGNED_SCHEMA = "PRAMAAN-SYNTHETIC-SIGNED-v1"


def canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def synthetic_issuer_private_key(key_id: str) -> Ed25519PrivateKey:
    """TEST-ONLY deterministic key for the synthetic issuer — derived from a
    public seed so the test-set generator can sign fixtures. Never a real
    authority's key, and worthless as a secret by design."""
    seed = hashlib.sha256(f"PRAMAAN-SYNTHETIC-TEST-ISSUER::{key_id}".encode()).digest()
    return Ed25519PrivateKey.from_private_bytes(seed)


def sign_synthetic(payload: dict[str, Any], key_id: str = "SYNTHETIC-ISSUER-1") -> str:
    sig = synthetic_issuer_private_key(key_id).sign(canonical(payload))
    return json.dumps({"schema": SIGNED_SCHEMA, "kid": key_id, "payload": payload,
                       "sig": base64.b64encode(sig).decode()}, separators=(",", ":"))


@lru_cache
def trust_anchors() -> dict[str, dict[str, Any]]:
    path = reference.reference_root() / "trust/synthetic_issuers.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k["key_id"]: {**k, "data_classification": data["data_classification"]} for k in data["keys"]}


def verify_signed_payload(raw: str, on: date) -> dict[str, Any]:
    result = {"signature_kind": "CRYPTOGRAPHIC", "digital_signature_present": True,
              "cryptographic_signature_verified": False, "certificate_status": "UNKNOWN",
              "document_integrity": "UNKNOWN"}
    try:
        envelope = json.loads(raw)
        payload, sig = envelope["payload"], base64.b64decode(envelope["sig"])
        key_id = envelope.get("kid", "")
    except (ValueError, KeyError, TypeError):
        return {**result, "status": "FAIL", "document_integrity": "UNKNOWN",
                "reason": "signed payload is malformed and cannot be verified"}
    anchor = trust_anchors().get(key_id)
    if anchor is None:
        return {**result, "status": "NOT_VERIFIED", "certificate_status": "UNKNOWN_SIGNER",
                "reason": f"signer key {key_id!r} is not in the configured trust store"}
    if not reference.in_period(anchor.get("valid_from"), anchor.get("valid_to"), on):
        result["certificate_status"] = "KEY_NOT_VALID_ON_DATE"
    elif anchor.get("revoked"):
        result["certificate_status"] = "REVOKED"
    else:
        result["certificate_status"] = f"TRUSTED ({anchor['data_classification']})"
    public = Ed25519PublicKey.from_public_bytes(base64.b64decode(anchor["public_key_b64"]))
    try:
        public.verify(sig, canonical(payload))
    except InvalidSignature:
        return {**result, "status": "FAIL", "document_integrity": "MODIFIED_AFTER_SIGNING_OR_WRONG_KEY",
                "signed_fields": payload,
                "reason": "cryptographic signature does not verify: the signed data was altered after signing, "
                          "or it was not signed by the stated issuer"}
    ok_cert = result["certificate_status"].startswith("TRUSTED")
    return {**result, "cryptographic_signature_verified": True, "document_integrity": "INTACT",
            "signed_fields": payload, "status": "PASS" if ok_cert else "REVIEW_REQUIRED",
            "reason": ("signature verified with issuer key " + key_id if ok_cert else
                       f"signature is mathematically valid but the signer key status is {result['certificate_status']}")}


def detect_pdf_signature(data: bytes) -> dict[str, Any] | None:
    if not data.startswith(b"%PDF"):
        return None
    present = b"/ByteRange" in data and b"/Contents" in data and (b"/Sig" in data or b"adbe.pkcs7" in data)
    if not present:
        return {"signature_kind": "NONE", "digital_signature_present": False, "status": "NOT_APPLICABLE",
                "reason": "PDF contains no digital signature dictionary"}
    try:
        import pyhanko  # noqa: F401
        available = True
    except ImportError:
        available = False
    return {"signature_kind": "CRYPTOGRAPHIC", "digital_signature_present": True,
            "cryptographic_signature_verified": False, "certificate_status": "NOT_CHECKED",
            "document_integrity": "UNKNOWN", "status": "NOT_VERIFIED",
            "reason": ("PDF signature present; PAdES validation requires issuer trust roots, which are not configured"
                       if available else
                       "PDF signature present; the PAdES validation library (pyhanko) and issuer trust roots are not installed")}


def assess(codes: list[Any], raw_codes: dict[str, str], has_visual_signature: bool, on: date) -> dict[str, Any]:
    """Summarise every signature-like element in one document."""
    items: list[dict[str, Any]] = []
    for code in codes:
        raw = raw_codes.get(code.region_id, "")
        if code.payload_kind == "SIGNED_STRUCTURED":
            items.append({"region_id": code.region_id, **verify_signed_payload(raw, on)})
        elif code.payload_kind == "SIGNED_SECURE_QR":
            items.append({"region_id": code.region_id, "signature_kind": "OFFICIAL_ONLY",
                          "digital_signature_present": True, "cryptographic_signature_verified": False,
                          "certificate_status": "NOT_CHECKED", "document_integrity": "UNKNOWN",
                          "status": "OFFICIAL_VERIFICATION_REQUIRED",
                          "reason": "issuer-signed Secure QR detected; it is verified only through the issuing "
                                    "authority's official mechanism, which is not connected in this build"})
    if has_visual_signature:
        items.append({"signature_kind": "VISUAL_SIGNATURE", "digital_signature_present": False,
                      "cryptographic_signature_verified": False, "status": "NOT_APPLICABLE",
                      "reason": "a handwritten-signature image is present; an image of a signature is not a "
                                "digital signature and is not treated as verified"})
    crypto = [i for i in items if i["signature_kind"] in ("CRYPTOGRAPHIC", "OFFICIAL_ONLY")]
    return {"items": items, "digital_signature_present": bool(crypto),
            "cryptographic_signature_verified": any(i.get("cryptographic_signature_verified") for i in crypto)}
