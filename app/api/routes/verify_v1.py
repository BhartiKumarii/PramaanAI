"""/api/v1 — modular, evidence-based document verification.

Every endpoint requires authentication (JWT) and runs through the existing
RBAC dependency. Results are decision support: the officer records the
actual decision via POST /api/v1/verification/{id}/officer-action.

Privacy: uploaded images and device region crops are processed in memory and
never written to disk or the database — only their SHA-256 hashes are kept.
"""
from __future__ import annotations

import hashlib
import io
import json
import uuid
from datetime import date

import anyio

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories import document_verification_repository as repo
from app.repositories.audit_repository import log_event
from app.schemas.docverify import (ExtractedVerificationRequest, OfficerActionRequest, RegionVerificationRequest,
                                   VerificationListItem, VerificationRecordEnvelope)
from app.services.docverify import concurrency, reference, screening
from app.services.docverify.concurrency import ServerBusy, run_heavy
from app.services.docverify.photo import verify_faces
from app.services.docverify.pipeline import (CropCoverageError, reference_dataset_hash, verify_extracted, verify_images,
                                             verify_region_crops)
from app.services.docverify.types import DocumentType, VerificationOutcome

router = APIRouter(prefix="/api/v1", tags=["document-verification-v1"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 40_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
BORDER_ROUTES = {"INDIA_NEPAL", "INDIA_BHUTAN"}
DIRECTIONS = {"INDIA_TO_NEPAL", "NEPAL_TO_INDIA", "INDIA_TO_BHUTAN", "BHUTAN_TO_INDIA"}

Officer = Depends(require_role(UserRole.OFFICER, UserRole.REVIEWER))


async def _read_image(upload: UploadFile, field: str) -> bytes:
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{field}: empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"{field}: larger than 10 MB")
    try:
        with Image.open(io.BytesIO(data)) as im:
            fmt = im.format
            w, h = im.size
            im.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{field}: not a valid image")
    if fmt not in ALLOWED_FORMATS:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"{field}: only JPEG, PNG or WEBP accepted")
    if w * h > MAX_PIXELS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{field}: image dimensions too large")
    return data


def _route_params(border_route: str | None, direction: str | None, travel_date: str | None) -> tuple[str | None, str | None, date | None]:
    if border_route and border_route not in BORDER_ROUTES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "border_route must be INDIA_NEPAL or INDIA_BHUTAN")
    if direction and direction not in DIRECTIONS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"direction must be one of {sorted(DIRECTIONS)}")
    try:
        on = date.fromisoformat(travel_date) if travel_date else None
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "travel_date must be YYYY-MM-DD")
    return border_route, direction, on


def _busy() -> HTTPException:
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                         "verification capacity is saturated on this instance — retry shortly",
                         headers={"Retry-After": str(ServerBusy.retry_after_seconds)})


async def _run(fn, *args, **kwargs):
    """Pipeline work: worker thread under the concurrency limiter."""
    try:
        return await run_heavy(fn, *args, **kwargs)
    except ServerBusy:
        raise _busy()


async def _db(fn, *args, **kwargs):
    """Blocking DB work off the event loop (not counted against the limiter)."""
    return await anyio.to_thread.run_sync(lambda: fn(*args, **kwargs))


def _replay(db: Session, client_request_id: str | None) -> VerificationOutcome | None:
    """Idempotency: a retried request (e.g. an offline-queue sync whose first
    response was lost) returns the stored result instead of a duplicate."""
    if not client_request_id:
        return None
    rec = repo.get_by_client_request_id(db, client_request_id)
    return _with_links(db, rec, VerificationOutcome.model_validate(json.loads(rec.result_json))) if rec else None


def _officer_post(db: Session, user: User) -> dict | None:
    """The officer's assigned checkpoint, matched to the checkpoint reference
    (name, type, border). None when unassigned or not a reference checkpoint
    (e.g. a post outside the India–Nepal/India–Bhutan borders)."""
    if not user.checkpoint_id:
        return None
    from app.models.checkpoint import Checkpoint
    cp = db.get(Checkpoint, str(user.checkpoint_id))
    if cp is None:
        return None
    match = reference.match_checkpoint(cp.name.split("/")[0])
    return match["record"] if match else None


def _with_links(db: Session, rec, outcome: VerificationOutcome) -> VerificationOutcome:
    """Attach the screening case (current status, reviewer responses) and
    identity findings — kept outside the hash-chained result."""
    return outcome.model_copy(update={"id": str(rec.id), "case": screening.case_summary(db, rec),
                                      "identity": screening.identity_of(rec)})


def _persist(db: Session, user: User, outcome: VerificationOutcome, source: str, hashes: list[str], *,
             open_case: bool = False, region_payload: dict | None = None, **kw) -> VerificationOutcome:
    version = outcome.pipeline.get("reference_data_version", "")
    repo.register_reference_snapshot(db, version, _reference_manifest())
    rec, created = repo.create(db, outcome, user_id=user.id, source=source, input_hashes=hashes, **kw)
    if not created:  # an identical idempotent request committed first — return what was stored
        return _with_links(db, rec, VerificationOutcome.model_validate(json.loads(rec.result_json)))
    log_event(db, None, "DOCVERIFY_CREATED", user.id,
              reason=f"document_verification:{rec.id} status={rec.overall_status} risk={rec.risk_score}")
    if open_case:
        case, identity = screening.open_case(db, user, outcome, rec, region_payload)
        return outcome.model_copy(update={"id": str(rec.id), "case": case, "identity": identity})
    return outcome.model_copy(update={"id": str(rec.id)})


def _reference_manifest() -> dict:
    root = reference.reference_root()
    files = {}
    for p in sorted(root.rglob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        files[p.relative_to(root).as_posix()] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                                                 "data_classification": data.get("data_classification")}
    return {"files": files}


async def _verify_upload(db: Session, user: User, files: list[UploadFile], *, expected: DocumentType | None,
                         border_route: str | None, direction: str | None, declared_nationality: str | None,
                         travel_date: str | None, live_face: UploadFile | None,
                         reference_face: UploadFile | None) -> VerificationOutcome:
    if not 1 <= len(files) <= 4:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "send 1 to 4 document images")
    route, direction, on = _route_params(border_route, direction, travel_date)
    images = [await _read_image(f, f"files[{i}]") for i, f in enumerate(files)]
    live = await _read_image(live_face, "live_face") if live_face else None
    ref = await _read_image(reference_face, "reference_face") if reference_face else None
    outcome = await _run(verify_images, images, db=db, border_route=route, direction=direction,
                         declared_nationality=declared_nationality, travel_date=on, live_face=live,
                         reference_face=ref, expected_type=expected)
    hashes = [hashlib.sha256(b).hexdigest() for b in images + [x for x in (live, ref) if x]]
    return await _db(_persist, db, user, outcome, "SERVER_IMAGE", hashes)


def _make_single(path: str, expected: DocumentType | None, summary: str):
    @router.post(path, response_model=VerificationOutcome, summary=summary)
    async def endpoint(file: UploadFile = File(...), border_route: str | None = Form(None),
                       direction: str | None = Form(None), declared_nationality: str | None = Form(None),
                       travel_date: str | None = Form(None), live_face: UploadFile | None = File(None),
                       reference_face: UploadFile | None = File(None), user: User = Officer,
                       db: Session = Depends(get_db)) -> VerificationOutcome:
        return await _verify_upload(db, user, [file], expected=expected, border_route=border_route,
                                    direction=direction, declared_nationality=declared_nationality,
                                    travel_date=travel_date, live_face=live_face, reference_face=reference_face)
    endpoint.__name__ = "verify_" + path.rsplit("/", 1)[-1].replace("-", "_")
    return endpoint


@router.post("/verify/document", response_model=VerificationOutcome,
             summary="Verify 1-4 document images together (type auto-detected, cross-document checks)")
async def verify_document(files: list[UploadFile] = File(...), border_route: str | None = Form(None),
                          direction: str | None = Form(None), declared_nationality: str | None = Form(None),
                          travel_date: str | None = Form(None), live_face: UploadFile | None = File(None),
                          reference_face: UploadFile | None = File(None), user: User = Officer,
                          db: Session = Depends(get_db)) -> VerificationOutcome:
    return await _verify_upload(db, user, files, expected=None, border_route=border_route, direction=direction,
                                declared_nationality=declared_nationality, travel_date=travel_date,
                                live_face=live_face, reference_face=reference_face)


_make_single("/verify/passport", None, "Verify a passport data page (MRZ, layout, validity, registry, face)")
_make_single("/verify/visa", None, "Verify a visa (fields, validity, stamps, passport link)")
_make_single("/verify/driving-licence", DocumentType.DRIVING_LICENCE,
             "Verify an Indian driving licence (format, QR, yellow/gold visual feature, registry)")
_make_single("/verify/aadhaar", DocumentType.AADHAAR,
             "Aadhaar: Verhoeff + layout only; Secure QR requires UIDAI official verification")
_make_single("/verify/stamp", None, "Detect and identify immigration stamps against the checkpoint reference")


@router.post("/verify/regions", response_model=VerificationOutcome,
             summary="Device path: ONE request with every on-device-detected REGION CROP (never the full image)")
async def verify_regions(req: RegionVerificationRequest, user: User = Officer,
                         db: Session = Depends(get_db)) -> VerificationOutcome:
    if (cached := await _db(_replay, db, req.client_request_id)) is not None:
        return cached
    payload = req.model_dump(mode="json")
    payload["post_checkpoint"] = await _db(_officer_post, db, user)
    try:
        outcome, hashes = await _run(verify_region_crops, payload, db=db)
    except CropCoverageError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"invalid region crop: {exc}")
    return await _db(_persist, db, user, outcome, "DEVICE_REGIONS", hashes, captured_offline=req.captured_offline,
                     device_id=req.device_id, captured_at=req.captured_at, client_request_id=req.client_request_id,
                     open_case=req.open_case, region_payload=payload if req.open_case else None)


@router.post("/verify/extracted", response_model=VerificationOutcome,
             summary="Device path: verify extracted data only (fields, MRZ text, decoded codes, stamp text)")
async def verify_extracted_endpoint(req: ExtractedVerificationRequest, user: User = Officer,
                                    db: Session = Depends(get_db)) -> VerificationOutcome:
    if (cached := await _db(_replay, db, req.client_request_id)) is not None:
        return cached
    payload = req.model_dump(mode="json")
    outcome = await _run(verify_extracted, payload, db=db)
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return await _db(_persist, db, user, outcome, "DEVICE_EXTRACTED", [digest], captured_offline=req.captured_offline,
                     device_id=req.device_id, captured_at=req.captured_at, client_request_id=req.client_request_id)


@router.get("/status", summary="Instance load (for operators / load balancers)")
def instance_status(user: User = Officer) -> dict:
    from app.services.docverify.detection import get_region_detector
    return {"load": concurrency.load(), "region_detector": get_region_detector().name,
            "reference_data_version": reference_dataset_hash()}


@router.post("/verify/face", summary="Face verification only: document photo vs presented person / authorised reference")
async def verify_face(document_image: UploadFile = File(...), live_image: UploadFile | None = File(None),
                      reference_image: UploadFile | None = File(None), user: User = Officer) -> dict:
    from app.services.docverify.detection import decode_image, detect_faces
    from app.services.docverify.photo import crop

    doc = await _read_image(document_image, "document_image")
    live = await _read_image(live_image, "live_image") if live_image else None
    ref = await _read_image(reference_image, "reference_image") if reference_image else None
    def work():
        bgr, _ = decode_image(doc)
        faces = detect_faces(bgr)
        doc_face = crop(bgr, max(faces, key=lambda f: f[1])[0]) if faces else None
        return faces, verify_faces(doc_face, live, ref)
    faces, result = await _run(work)
    # Biometric minimisation: no embeddings, no face crops are returned.
    return {"face_detected": bool(faces), "face_count": len(faces), **{k: v for k, v in result.items()},
            "note": "Similarity is a model score, not an identity decision. The officer compares in person."}


@router.get("/checkpoints", summary="Official-source land-border checkpoint reference (versioned)")
def list_checkpoints(country: str | None = None, border: str | None = None, user: User = Officer) -> dict:
    return {"reference_data_version": reference_dataset_hash(),
            "checkpoints": reference.list_checkpoints(country=country, border=border)}


@router.get("/reference/rules/{route}", summary="Border-rule configuration for INDIA_NEPAL or INDIA_BHUTAN")
def get_rules(route: str, user: User = Officer) -> dict:
    if route.upper() not in BORDER_ROUTES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown route")
    return reference.border_rules(route)


def _item(rec, case: dict | None = None) -> VerificationListItem:
    return VerificationListItem(id=str(rec.id), sequence=rec.sequence, created_at=rec.created_at, source=rec.source,
                                document_types=json.loads(rec.document_types), country=rec.country,
                                border_route=rec.border_route, overall_status=rec.overall_status,
                                risk_score=rec.risk_score, risk_level=rec.risk_level,
                                officer_action=rec.officer_action, sync_status=rec.sync_status,
                                captured_offline=rec.captured_offline,
                                attention_checks=_attention_checks(rec), **(case or {}))


def _attention_checks(rec) -> list[str]:
    try:
        checks = json.loads(rec.result_json).get("checks") or {}
    except ValueError:
        return []
    return sorted(name for name, status in checks.items() if status in ("REVIEW_REQUIRED", "FAIL"))


@router.get("/verification", response_model=list[VerificationListItem],
            summary="Recent verifications (summary only — no personal fields)")
def list_verifications(limit: int = 50, mine: bool = False, user: User = Officer,
                       db: Session = Depends(get_db)) -> list[VerificationListItem]:
    recs = repo.list_recent(db, limit=min(max(limit, 1), 200), created_by=str(user.id) if mine else None)
    return [_item(r, screening.case_brief(db, r.case_id)) for r in recs]


@router.get("/verification/chain/verify", summary="Walk the local tamper-evident hash chain")
def verify_chain(user: User = Officer, db: Session = Depends(get_db)) -> dict:
    return repo.verify_chain(db)


@router.get("/verification/by-case/{case_id}", response_model=VerificationRecordEnvelope,
            summary="The document verification behind a screening case (web case review)")
def get_verification_for_case(case_id: uuid.UUID, user: User = Officer,
                              db: Session = Depends(get_db)) -> VerificationRecordEnvelope:
    rec = repo.get_by_case_id(db, str(case_id))
    if rec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no document verification is linked to this case")
    return get_verification(rec.id, user, db)


@router.get("/verification/{verification_id}", response_model=VerificationRecordEnvelope,
            summary="Stored verification with integrity check (hash + HMAC)")
def get_verification(verification_id: uuid.UUID, user: User = Officer,
                     db: Session = Depends(get_db)) -> VerificationRecordEnvelope:
    rec = repo.get(db, verification_id)
    if rec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "verification not found")
    log_event(db, None, "DOCVERIFY_VIEWED", user.id, reason=f"document_verification:{rec.id}")
    return VerificationRecordEnvelope(
        record=_item(rec), integrity=repo.integrity(rec),
        officer_action={"action": rec.officer_action, "reason": rec.officer_action_reason,
                        "by": rec.officer_action_by, "at": rec.officer_action_at},
        result={**json.loads(rec.result_json), "id": str(rec.id), "case": screening.case_summary(db, rec),
                "identity": screening.identity_of(rec)})


def _apply_to_case(db: Session, rec, req: OfficerActionRequest, user: User) -> None:
    """The field officer's two screening actions on the linked case:
    CLEARED — their own recorded decision (the system never decides);
    SEND_TO_OFFICER — the case goes to the reviewing officers' queue on the
    web console with the reason as a note; their written response comes back
    through GET /verification/{id} (case.decisions / case.notes)."""
    from app.models.case import Case, CaseStatus
    from app.repositories.case_repository import add_note, record_decision, submit_case
    case = db.get(Case, uuid.UUID(rec.case_id))
    if case is None:
        return
    open_states = (CaseStatus.PENDING, CaseStatus.REVIEW_REQUIRED)
    officer = uuid.UUID(str(user.id))
    if req.action == "SEND_TO_OFFICER":
        if case.status not in open_states:
            raise HTTPException(status.HTTP_409_CONFLICT, f"case is already {case.status.value}")
        add_note(db, case.id, officer, req.reason or "")
        submit_case(db, case)
        log_event(db, case.verification_id, "SENT", user.id, reason=req.reason, case_id=case.id)
    elif req.action == "CLEARED":
        if case.status not in open_states:
            raise HTTPException(status.HTTP_409_CONFLICT, f"case is already {case.status.value}")
        record_decision(db, case, officer, "CLEAR", req.reason)
        log_event(db, case.verification_id, "DECISION_CLEAR", user.id, reason=req.reason, case_id=case.id)


@router.post("/verification/{verification_id}/officer-action", response_model=VerificationListItem,
             summary="Record the officer's own decision (a reason is required unless CLEARED)")
def officer_action(verification_id: uuid.UUID, req: OfficerActionRequest, user: User = Officer,
                   db: Session = Depends(get_db)) -> VerificationListItem:
    rec = repo.get(db, verification_id)
    if rec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "verification not found")
    if req.action != "CLEARED" and not req.reason:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "a reason is required for this action")
    if rec.case_id:
        _apply_to_case(db, rec, req, user)
    rec = repo.set_officer_action(db, rec, req.action, req.reason, user.id)
    log_event(db, None, "DOCVERIFY_OFFICER_ACTION", user.id,
              reason=f"document_verification:{rec.id} action={req.action} reason={req.reason or ''}"[:2000])
    return _item(rec)
