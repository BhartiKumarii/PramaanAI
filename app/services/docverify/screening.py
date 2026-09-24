"""Screening workflow on top of document verification.

One officer workflow — choose document, capture, extract, verify, decide —
produces BOTH the explainable document-verification record and a screening
case, so the result lands in the same Review/History queues and the web
console's case review as every other screening.

What this module adds after a verification is stored:
  * a signed screening VerificationRecord + Case (existing repositories),
    status/priority taken from the verification's own risk indicator;
  * identity-graph findings, reusing the existing services: the document
    photo's face embedding against earlier screenings (same face under a
    different declared identity), the same document number on other cases,
    and the network-graph relationships built from both.

The face embedding is computed from the photograph crop in memory and kept
only in the existing identity-embedding store that the identity graph
already uses; it is never returned in any response.
"""
from __future__ import annotations

import base64
import json
import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.case import CasePriority, CaseStatus
from app.models.user import User
from app.repositories.audit_repository import log_event
from app.repositories.case_repository import create_case
from app.repositories.verification_repository import create_verification
from app.services.docverify.types import CheckStatus, VerificationOutcome
from app.services.risk.base import RiskResult, RiskSignalBreakdown

logger = logging.getLogger("pramaan.docverify.screening")

_LEVEL = {"HIGH": "HIGH_RISK", "MEDIUM": "MEDIUM_RISK", "LOW": "LOW_RISK"}
_PRIORITY = {"HIGH": CasePriority.HIGH, "MEDIUM": CasePriority.MEDIUM, "LOW": CasePriority.LOW}


def _primary_fields(outcome: VerificationOutcome) -> dict[str, str]:
    for doc in outcome.documents:
        if doc.fields:
            return {k: v.value for k, v in doc.fields.items()}
    return {}


def _risk(outcome: VerificationOutcome) -> RiskResult:
    parts = outcome.risk_breakdown
    return RiskResult(
        score=outcome.risk_score,
        level=_LEVEL.get(outcome.risk_level, "LOW_RISK"),
        decision="CLEAR" if outcome.overall_status == CheckStatus.PASS else "MANUAL_REVIEW",
        top_reason=outcome.explanation or outcome.officer_summary.headline,
        breakdown=[RiskSignalBreakdown(signal=p["check"], weight=round(p["points"] / 100, 3), raw_risk=1.0,
                                       contribution=round(p["points"] / 100, 3), reason=p["reason"])
                   for p in parts],
    )


def _photo_embedding(region_payload: dict[str, Any] | None) -> list[float] | None:
    if not region_payload:
        return None
    for d in region_payload.get("documents", []):
        for r in d.get("regions", []):
            if r.get("label") == "photograph" and r.get("image_b64"):
                try:
                    from app.services.face.mobilefacenet_provider import extract_mobilefacenet_embedding
                    return extract_mobilefacenet_embedding(base64.b64decode(r["image_b64"]))
                except Exception as exc:  # a missing face never blocks the screening
                    logger.info("no document-photo embedding: %s", exc)
                    return None
    return None


def _identity(db: Session, case, name: str | None, number: str | None, nationality: str,
              embedding: list[float] | None) -> dict[str, Any]:
    from app.api.routes.documents import _update_network_graph  # shared relationship builder
    from app.repositories.identity_embedding_repository import insert_embedding, list_all
    from app.repositories.identity_embedding_repository import set_case_id as set_embedding_case_id
    from app.services.duplicate.checker import check_duplicate_document
    from app.services.identity_graph.graph import build_graph, find_multi_identity_cluster

    out: dict[str, Any] = {"face_cluster": None, "duplicate_document": None,
                           "notes": []}
    duplicate = check_duplicate_document(db, number, name)
    if duplicate is not None:
        out["duplicate_document"] = duplicate.model_dump()
    graph_result = None
    if embedding:
        rec = insert_embedding(db, name or "UNKNOWN", number, embedding)
        set_embedding_case_id(db, rec, case.id)
        graph_result = find_multi_identity_cluster(build_graph(list_all(db)), str(rec.id))
        out["face_cluster"] = graph_result.model_dump()
    else:
        out["notes"].append("No face found in the document photo region — face-based linking not run")
    if not number:
        out["notes"].append("No document number read — document-number linking not run")
    _update_network_graph(db, case=case, name=name, document_number=number, nationality=nationality,
                          identity_graph_result=graph_result)
    return out


def open_case(db: Session, user: User, outcome: VerificationOutcome, rec, region_payload: dict[str, Any] | None
              ) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Create the screening case for a freshly stored verification. Returns
    (case summary, identity findings). Idempotent per verification."""
    if rec.case_id:
        return case_summary(db, rec), identity_of(rec)
    if not user.checkpoint_id:
        return {"status": "NOT_OPENED", "reason": "officer has no checkpoint assigned"}, None

    fields = _primary_fields(outcome)
    name = fields.get("name")
    number = fields.get("document_number") or fields.get("visa_number") or fields.get("permit_number")
    nationality = (fields.get("nationality") or outcome.country or "UNKNOWN")[:64]
    doc_type = (outcome.document_type or "UNKNOWN")[:32]

    screening = create_verification(db, doc_type, nationality, _risk(outcome), traveler_name=name)
    case = create_case(
        db, checkpoint_id=user.checkpoint_id, field_officer_id=user.id, verification_id=screening.id,
        document_type=doc_type, nationality=nationality, traveler_name=name,
        initial_status=CaseStatus.PENDING if outcome.overall_status == CheckStatus.PASS else CaseStatus.REVIEW_REQUIRED,
        priority=_PRIORITY.get(outcome.risk_level, CasePriority.LOW),
    )
    log_event(db, screening.id, "CREATED", user.id, case_id=case.id,
              reason=f"document_verification:{rec.id}")

    identity = None
    try:
        identity = _identity(db, case, name, number, nationality, _photo_embedding(region_payload))
    except Exception as exc:  # identity linking is supplementary — never lose the case over it
        db.rollback()
        logger.warning("identity graph failed for case %s: %s", case.case_number, exc)
        identity = {"face_cluster": None, "duplicate_document": None,
                    "notes": [f"Identity graph not available: {type(exc).__name__}"]}

    rec.case_id = str(case.id)
    rec.screening_verification_id = str(screening.id)
    rec.identity_json = json.dumps(identity) if identity is not None else None
    db.commit()
    return case_summary(db, rec), identity


def case_summary(db: Session, rec) -> dict[str, Any] | None:
    if not rec.case_id:
        return None
    from app.models.case import Case, CaseNote, OfficerDecision
    from sqlalchemy import select
    case = db.get(Case, uuid.UUID(rec.case_id))
    if case is None:
        return None
    decisions = list(db.execute(select(OfficerDecision).where(OfficerDecision.case_id == case.id)
                                .order_by(OfficerDecision.created_at)).scalars())
    notes = list(db.execute(select(CaseNote).where(CaseNote.case_id == case.id)
                            .order_by(CaseNote.created_at)).scalars())
    from app.models.user import User as U
    ids = {str(d.officer_id) for d in decisions} | {str(n.author_id) for n in notes}
    # users.id is a string column on SQLite but a native UUID on PostgreSQL:
    # key by the normalised string so the lookup works on both.
    users = {str(u.id): u for u in db.execute(select(U).where(U.id.in_(ids))).scalars()} if ids else {}

    def who(uid) -> dict[str, Any]:
        u = users.get(str(uid))
        return {"username": u.username if u else None, "role": u.role.value if u else None}

    return {
        "case_id": str(case.id), "case_number": case.case_number, "status": case.status.value,
        # The case's screening record id — evidence images for the reviewing
        # admin are attached to it (POST /images/{id}/upload), as elsewhere.
        "screening_verification_id": rec.screening_verification_id,
        "priority": case.priority.value, "sent_at": case.sent_at.isoformat() if case.sent_at else None,
        "decided_at": case.decided_at.isoformat() if case.decided_at else None,
        "decisions": [{"decision": d.decision, "reason": d.reason, "at": d.created_at.isoformat(), **who(d.officer_id)}
                      for d in decisions],
        "notes": [{"note": n.note, "at": n.created_at.isoformat(), **who(n.author_id)} for n in notes],
    }


def identity_of(rec) -> dict[str, Any] | None:
    return json.loads(rec.identity_json) if rec.identity_json else None


def case_brief(db: Session, case_id: str | None) -> dict[str, Any] | None:
    """List-view summary of a linked case: number, status, whether a
    reviewing officer (not the field officer) has decided, and last change."""
    if not case_id:
        return None
    from app.models.case import Case, OfficerDecision
    from sqlalchemy import select
    case = db.get(Case, uuid.UUID(case_id))
    if case is None:
        return None
    responded = any(str(d.officer_id) != str(case.field_officer_id) for d in db.execute(
        select(OfficerDecision).where(OfficerDecision.case_id == case.id)).scalars())
    last = max((t for t in (case.created_at, case.sent_at, case.decided_at) if t is not None), default=None)
    return {"case_id": str(case.id), "case_number": case.case_number, "case_status": case.status.value,
            "reviewer_responded": responded, "last_update_at": last}
