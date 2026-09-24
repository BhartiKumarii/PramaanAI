"""Persistence for /api/v1 document verifications.

Tamper evidence: each record's `record_hash` = SHA-256 over the previous
record's hash plus this record's canonical content, and the row is also
HMAC-signed with the server key. Altering, deleting or re-ordering any
stored record breaks the chain from that point, which `verify_chain`
reports. This is a LOCAL hash chain — not a distributed ledger.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import threading
import time

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.hmac_signing import sign, verify
from app.models.document_verification import (DocumentVerificationCheck, DocumentVerificationRecord,
                                               ReferenceDataSnapshot)
from app.services.docverify.types import VerificationOutcome

GENESIS = "0" * 64


def _content(rec: DocumentVerificationRecord) -> dict[str, Any]:
    return {"id": str(rec.id), "sequence": rec.sequence, "created_by": rec.created_by, "source": rec.source,
            "document_types": rec.document_types, "overall_status": rec.overall_status, "risk_score": rec.risk_score,
            "result_sha256": hashlib.sha256(rec.result_json.encode()).hexdigest(), "input_hashes": rec.input_hashes,
            "reference_data_version": rec.reference_data_version, "captured_offline": rec.captured_offline,
            "prev_hash": rec.prev_hash}


def _hash(content: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def stored_result(outcome: VerificationOutcome) -> dict[str, Any]:
    """Minimum-necessary retention: drop raw OCR line dumps (the extracted
    fields are kept), keep everything else the officer needs to review."""
    data = outcome.model_dump(mode="json")
    for doc in data.get("documents", []):
        doc["ocr_line_count"] = len(doc.get("ocr_lines", []))
        doc["ocr_lines"] = []
        for fs in doc.get("security_features", []):
            for item in fs.get("items", []) if isinstance(fs, dict) else []:
                item.pop("signed_fields", None)
    return data


_APPEND_LOCK = threading.Lock()  # in-process fast path; the unique sequence protects across processes


def create(db: Session, outcome: VerificationOutcome, *, user_id: str, source: str, input_hashes: list[str],
           captured_offline: bool = False, device_id: str | None = None,
           captured_at: datetime | None = None,
           client_request_id: str | None = None) -> tuple[DocumentVerificationRecord, bool]:
    """Append a record to the chain. Safe under concurrent requests and
    multiple worker processes/instances: a lost race on the unique
    `sequence` rolls back and retries against the new chain head.
    Returns (record, created) — created is False when a concurrent request
    with the same client_request_id had already been stored."""
    for _ in range(8):
        with _APPEND_LOCK:
            last = db.execute(select(DocumentVerificationRecord)
                              .order_by(DocumentVerificationRecord.sequence.desc()).limit(1)).scalar_one_or_none()
            rec_id = uuid.uuid4()
            result_json = json.dumps(stored_result(outcome.model_copy(update={"id": str(rec_id)})), separators=(",", ":"))
            rec = DocumentVerificationRecord(
                id=rec_id, sequence=(last.sequence + 1) if last else 1, client_request_id=client_request_id,
                created_by=str(user_id), source=source,
                document_types=json.dumps([d.document_type.document_type.value for d in outcome.documents]),
                country=outcome.country, border_route=outcome.border_route,
                overall_status=outcome.overall_status.value, risk_score=outcome.risk_score,
                risk_level=outcome.risk_level, confidence=outcome.confidence,
                result_json=result_json,
                input_hashes=json.dumps(input_hashes),
                reference_data_version=str(outcome.pipeline.get("reference_data_version", "")),
                captured_offline=captured_offline, device_id=device_id, captured_at=captured_at,
                sync_status="SYNCED_FROM_DEVICE" if source.startswith("DEVICE") else "SERVER",
                prev_hash=last.record_hash if last else GENESIS, record_hash="", signature="")
            content = _content(rec)
            rec.record_hash = _hash(content)
            rec.signature = sign(content | {"record_hash": rec.record_hash})
            try:
                # The parent row is written first: without an ORM relationship
                # the unit of work does not order the check rows after it, and
                # PostgreSQL enforces the foreign key (SQLite, by default, does not).
                db.add(rec)
                db.flush()
                for c in outcome.check_details:
                    ev = [e.model_dump(mode="json") for e in outcome.evidence if e.id in c.evidence_ids]
                    db.add(DocumentVerificationCheck(verification_id=rec_id, document_index=c.document_index,
                                                     name=c.name, status=c.status.value, blocking=c.blocking,
                                                     strong_evidence=c.strong_evidence, summary=c.summary,
                                                     evidence_json=json.dumps(ev)))
                db.commit()
            except OperationalError:
                db.rollback()  # e.g. SQLite "database is locked" under concurrent writers — retry
                time.sleep(0.05 * (2 ** _))
                continue
            except IntegrityError:
                db.rollback()
                if client_request_id and (existing := get_by_client_request_id(db, client_request_id)):
                    return existing, False  # a concurrent retry of the same request won
                continue  # another writer took this sequence number — retry on the new head
        db.refresh(rec)
        return rec, True
    raise RuntimeError("could not append to the verification chain after repeated contention")


def get_by_client_request_id(db: Session, client_request_id: str) -> DocumentVerificationRecord | None:
    return db.execute(select(DocumentVerificationRecord)
                      .where(DocumentVerificationRecord.client_request_id == client_request_id)).scalar_one_or_none()


def get(db: Session, verification_id: uuid.UUID) -> DocumentVerificationRecord | None:
    return db.get(DocumentVerificationRecord, verification_id)


def list_recent(db: Session, limit: int = 50, created_by: str | None = None) -> list[DocumentVerificationRecord]:
    q = select(DocumentVerificationRecord).order_by(DocumentVerificationRecord.sequence.desc()).limit(limit)
    if created_by:
        q = q.where(DocumentVerificationRecord.created_by == created_by)
    return list(db.execute(q).scalars())


def integrity(rec: DocumentVerificationRecord) -> dict[str, bool]:
    content = _content(rec)
    return {"hash_valid": _hash(content) == rec.record_hash,
            "signature_valid": verify(content | {"record_hash": rec.record_hash}, rec.signature)}


def verify_chain(db: Session) -> dict[str, Any]:
    prev = GENESIS
    checked = 0
    for rec in db.execute(select(DocumentVerificationRecord).order_by(DocumentVerificationRecord.sequence)).scalars():
        ok = integrity(rec)
        if rec.prev_hash != prev or not ok["hash_valid"] or not ok["signature_valid"]:
            return {"chain_valid": False, "records_checked": checked + 1, "broken_at_sequence": rec.sequence,
                    "reason": "record content, signature or link to the previous record does not verify",
                    "note": "Local tamper-evident hash chain (not a distributed ledger)."}
        prev = rec.record_hash
        checked += 1
    return {"chain_valid": True, "records_checked": checked, "head": prev,
            "note": "Local tamper-evident hash chain (not a distributed ledger)."}


def checks_for(db: Session, verification_id: uuid.UUID) -> list[DocumentVerificationCheck]:
    return list(db.execute(select(DocumentVerificationCheck)
                           .where(DocumentVerificationCheck.verification_id == verification_id)).scalars())


def set_officer_action(db: Session, rec: DocumentVerificationRecord, action: str, reason: str | None,
                       user_id: str) -> DocumentVerificationRecord:
    rec.officer_action = action
    rec.officer_action_reason = reason
    rec.officer_action_by = str(user_id)
    rec.officer_action_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rec)
    return rec


def register_reference_snapshot(db: Session, version: str, manifest: dict[str, Any]) -> None:
    if db.get(ReferenceDataSnapshot, version) is None:
        db.add(ReferenceDataSnapshot(version=version, manifest_json=json.dumps(manifest)))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()  # a concurrent request registered the same version first


def count(db: Session) -> int:
    return db.execute(select(func.count(DocumentVerificationRecord.id))).scalar_one()


def get_by_case_id(db: Session, case_id: str) -> DocumentVerificationRecord | None:
    return db.execute(select(DocumentVerificationRecord)
                      .where(DocumentVerificationRecord.case_id == case_id)).scalar_one_or_none()
