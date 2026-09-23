"""Registry adapters. Every adapter here is either a FICTIONAL mock or an
explicitly "not configured" official-service placeholder:

  DrivingLicenceRegistry   verify_driving_licence(licence_number) — mock
  TravelAuthorisationRegistry  visa / Bhutan permit lookups — mock
  passport registry        existing mock citizen registry (DB) + watchlist
  AadhaarOfficialVerifier  UIDAI mechanism — NOT configured
  EPassportChipVerifier    authorised chip reader/PKI — NOT configured

Unavailable connectivity or an unconfigured registry yields
REGISTRY_NOT_AVAILABLE / OFFICIAL_VERIFICATION_REQUIRED — never evidence
against the traveller. Offline mode never claims a registry was checked.
"""
from __future__ import annotations

import re
from typing import Any

from app.core.config import get_settings
from app.services.docverify import reference

MOCK_NOTICE = "FICTIONAL MOCK REGISTRY — synthetic records only, not a government database"


def _norm(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


class RegistryUnavailable(Exception):
    pass


class DrivingLicenceRegistry:
    def __init__(self, mode: str | None = None, offline: bool = False):
        self.mode = (mode or get_settings().pramaan_dl_registry_mode).lower()
        self.offline = offline

    def verify_driving_licence(self, licence_number: str) -> dict[str, Any]:
        if self.offline:
            return {"status": "REGISTRY_NOT_AVAILABLE", "reason": "offline — external registry not contacted"}
        if self.mode != "mock":
            return {"status": "REGISTRY_NOT_AVAILABLE", "reason": "no authorised driving-licence registry is configured"}
        data = reference.mock_registry("driving_licence")
        target = _norm(licence_number)
        for rec in data["records"]:
            if _norm(rec["licence_number"]) == target:
                return {"record_found": True, **{k: rec[k] for k in ("licence_number", "name", "dob", "expiry_date",
                                                                         "vehicle_classes", "status")},
                        "source": MOCK_NOTICE}
        return {"record_found": False, "licence_number": licence_number, "status": "NO_RECORD", "source": MOCK_NOTICE}


class TravelAuthorisationRegistry:
    def __init__(self, mode: str | None = None, offline: bool = False):
        self.mode = (mode or get_settings().pramaan_travel_registry_mode).lower()
        self.offline = offline

    def lookup(self, record_type: str, number: str) -> dict[str, Any]:
        if self.offline:
            return {"status": "REGISTRY_NOT_AVAILABLE", "reason": "offline — external registry not contacted"}
        if self.mode != "mock":
            return {"status": "REGISTRY_NOT_AVAILABLE", "reason": "no authorised visa/permit registry is configured"}
        key = "visa_number" if record_type == "VISA" else "permit_number"
        target = _norm(number)
        for rec in reference.mock_registry("travel_authorisations")["records"]:
            if rec["record_type"] == record_type and _norm(rec.get(key)) == target:
                return {"record_found": True, **rec, "source": MOCK_NOTICE}
        return {"record_found": False, "status": "NO_RECORD", "source": MOCK_NOTICE}


def lookup_passport(db, document_number: str, name: str | None, dob_iso: str | None,
                    nationality: str | None, offline: bool = False) -> dict[str, Any]:
    """Existing mock citizen registry (MATCH / MISMATCH / NO_RECORD) plus the
    existing watchlist (EXACT document-number hits only — fuzzy name hits are
    too weak to surface as a registry finding)."""
    if offline:
        return {"status": "REGISTRY_NOT_AVAILABLE", "reason": "offline — external registry not contacted"}
    if db is None:
        return {"status": "REGISTRY_NOT_AVAILABLE", "reason": "registry database session not available"}
    from app.services.citizen_registry.lookup import lookup_citizen_registry
    from app.services.registry.lookup import lookup_registry

    dob_ddmmyyyy = None
    if dob_iso:
        y, m, d = dob_iso.split("-")
        dob_ddmmyyyy = f"{d}/{m}/{y}"
    try:
        citizen = lookup_citizen_registry(db, document_number, name, dob_ddmmyyyy, nationality)
        watch = lookup_registry(db, document_number, None)
    except Exception as exc:  # DB outage is "not available", never a finding
        return {"status": "REGISTRY_NOT_AVAILABLE", "reason": f"registry query failed: {type(exc).__name__}"}
    out: dict[str, Any] = {"source": MOCK_NOTICE}
    if citizen is None:
        out.update(status="NO_RECORD", reason="no document number to look up")
    else:
        out.update(status=citizen.status, reason=citizen.reason, mismatched_fields=citizen.mismatched_fields)
    exact = [h for h in watch.hits if h.match_type == "EXACT"]
    if exact:
        out["watchlist"] = [{"reason": h.registry_reason, "severity": h.severity} for h in exact]
    return out


class AadhaarOfficialVerifier:
    """Placeholder for UIDAI's official verification mechanism. This build
    never decodes, decrypts or parses the Secure QR itself."""
    configured = False

    def verify(self, secure_qr_present: bool) -> dict[str, Any]:
        return {"status": "OFFICIAL_VERIFICATION_REQUIRED",
                "reason": ("Secure QR present — verify through UIDAI's official mechanism (not connected in this build)"
                           if secure_qr_present else
                           "Aadhaar can only be verified through UIDAI's official mechanism (not connected in this build)")}


class EPassportChipVerifier:
    """Placeholder for an authorised ePassport reader + ICAO PKD trust chain."""
    configured = False

    def verify(self) -> dict[str, Any]:
        return {"status": "NOT_VERIFIED",
                "reason": "chip data can only be verified with an authorised reader and PKI trust chain; none is configured"}


DATASET_NOTICE = ("LOCAL TEST REGISTRY built from the project's sample image dataset — "
                  "not a government database; not deployed")


def lookup_dataset_registry(db, document_number: str | None, offline: bool = False) -> dict[str, Any] | None:
    """Records from the local test-fixture registry (dataset_registry_records)
    with this document number. Returns None when the table is empty/absent
    (e.g. any deployment), so the pipeline behaves exactly as before there.
    More than one record with conflicting details -> 'CONFLICT'."""
    if offline or db is None or not document_number:
        return None
    try:
        from app.models.document_verification import DatasetRegistryRecord
        from sqlalchemy import select
        rows = list(db.execute(select(DatasetRegistryRecord)
                               .where(DatasetRegistryRecord.document_number == _norm(document_number))).scalars())
    except Exception:
        db.rollback()  # e.g. table absent — never leave the session in a failed transaction
        return None
    if not rows:
        return None
    keys = ("full_name", "date_of_birth", "date_of_expiry", "nationality")
    distinct = {tuple(getattr(r, k) for k in keys) for r in rows}
    best = rows[0]
    record = {"name": best.full_name, "dob": best.date_of_birth, "expiry_date": best.date_of_expiry,
              "nationality": best.nationality, "record_status": best.record_status,
              "face_embedding": best.face_embedding_json, "source": DATASET_NOTICE}
    if len(distinct) > 1:
        return {"status": "CONFLICT", "record_found": True, "records": len(rows), "record": record,
                "reason": f"{len(rows)} registry records share this number with different details"}
    return {"status": "FOUND", "record_found": True, "records": len(rows), "record": record}
