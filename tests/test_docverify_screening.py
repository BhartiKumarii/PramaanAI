"""The single screening workflow: region crops from the phone -> document
verification -> screening case -> field officer Clear / Send to officer ->
reviewing officer's written response visible to the phone."""
import base64
from pathlib import Path

import cv2
import pytest

from app.services.docverify.detection import decode_image
from app.services.docverify.ocr import ocr_image

SYN = Path(__file__).resolve().parents[1] / "data/synthetic/docverify"
pytestmark = pytest.mark.skipif(not (SYN / "GEN-003_dl.jpg").exists(), reason="synthetic test set not generated")


def _user(client, db_session, username, role="OFFICER"):
    from app.core.security import hash_password
    from app.models.checkpoint import Checkpoint
    from app.models.user import User, UserRole

    cp = db_session.query(Checkpoint).filter_by(code="TST").one_or_none()
    if cp is None:
        cp = Checkpoint(code="TST", name="Test Post")
        db_session.add(cp)
        db_session.commit()
    db_session.add(User(username=username, hashed_password=hash_password("Str0ngPass!"),
                        role=UserRole(role), checkpoint_id=cp.id))
    db_session.commit()
    r = client.post("/auth/login", json={"username": username, "password": "Str0ngPass!"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _text_crops(name: str) -> dict:
    """What the phone sends for a capture with no detector regions: padded
    printed-text blocks only (never the whole image)."""
    data = (SYN / name).read_bytes()
    bgr, rgb = decode_image(data)
    h, w = bgr.shape[:2]
    crops = []
    for line in ocr_image(rgb)[:14]:
        x0, y0, x1, y1 = line.bbox
        x0, y0, x1, y1 = max(0, x0 - 6), max(0, y0 - 6), min(w, x1 + 6), min(h, y1 + 6)
        ok, jpg = cv2.imencode(".jpg", bgr[y0:y1, x0:x1])
        crops.append({"label": "text", "bbox": line.bbox, "crop_bbox": [x0, y0, x1, y1], "confidence": 0.9,
                      "image_b64": base64.b64encode(jpg.tobytes()).decode()})
    return {"documents": [{"image_size": [w, h], "regions": crops}], "travel_date": "2026-09-23"}


def test_screening_opens_a_case_with_reasons_and_idempotent_replay(client, db_session):
    h = _user(client, db_session, "field1")
    body = {**_text_crops("GEN-003_dl.jpg"), "open_case": True, "client_request_id": "scr-1",
            "expected_document_type": "DRIVING_LICENCE"}
    out = client.post("/api/v1/verify/regions", headers=h, json=body).json()
    case = out["case"]
    assert case["case_number"] and case["status"] in ("PENDING", "REVIEW_REQUIRED")
    assert set(out["suggested_reasons"]) == {"clear", "send"} and out["suggested_reasons"]["send"]
    assert out["identity"] is not None and "duplicate_document" in out["identity"]
    again = client.post("/api/v1/verify/regions", headers=h, json=body).json()
    assert again["id"] == out["id"] and again["case"]["case_id"] == case["case_id"]  # no duplicate case


def test_send_to_officer_then_reviewer_response_reaches_the_phone(client, db_session):
    field = _user(client, db_session, "field2")
    reviewer = _user(client, db_session, "reviewer2", role="REVIEWER")
    out = client.post("/api/v1/verify/regions", headers=field,
                      json={**_text_crops("GEN-003_dl.jpg"), "open_case": True}).json()
    vid, case_id = out["id"], out["case"]["case_id"]

    r = client.post(f"/api/v1/verification/{vid}/officer-action", headers=field,
                    json={"action": "SEND_TO_OFFICER", "reason": out["suggested_reasons"]["send"]})
    assert r.status_code == 200
    assert client.get(f"/api/v1/verification/{vid}", headers=field).json()["result"]["case"]["status"] == "SENT"

    r = client.post(f"/cases/{case_id}/decision", headers=reviewer,
                    json={"decision": "SECONDARY_REVIEW", "reason": "Check the licence against the issuing RTO record"})
    assert r.status_code == 200
    case = client.get(f"/api/v1/verification/{vid}", headers=field).json()["result"]["case"]
    assert case["status"] == "SECONDARY_REVIEW"
    assert case["decisions"][-1]["reason"].startswith("Check the licence") and case["decisions"][-1]["username"] == "reviewer2"
    assert case["notes"][0]["note"] == out["suggested_reasons"]["send"]


def test_field_officer_clear_records_their_decision(client, db_session):
    field = _user(client, db_session, "field3")
    out = client.post("/api/v1/verify/regions", headers=field,
                      json={**_text_crops("GEN-003_dl.jpg"), "open_case": True}).json()
    r = client.post(f"/api/v1/verification/{out['id']}/officer-action", headers=field,
                    json={"action": "CLEARED", "reason": out["suggested_reasons"]["clear"]})
    assert r.status_code == 200
    case = client.get(f"/api/v1/verification/{out['id']}", headers=field).json()["result"]["case"]
    assert case["status"] == "CLEAR" and case["decisions"][0]["username"] == "field3"
    # A closed case cannot be sent on afterwards.
    r = client.post(f"/api/v1/verification/{out['id']}/officer-action", headers=field,
                    json={"action": "SEND_TO_OFFICER", "reason": "second thoughts"})
    assert r.status_code == 409


def test_phone_text_fills_only_fields_the_server_could_not_read():
    from datetime import date

    from app.services.docverify.pipeline import Ctx, _merge_device_fields
    from app.services.docverify.types import (DocumentAnalysis, DocumentType, DocumentTypeResult, FieldValue,
                                              OcrLine)
    doc = DocumentAnalysis(document_index=0, image_sha256="x", image_size=[100, 100],
                           document_type=DocumentTypeResult(document_type=DocumentType.AADHAAR, country="INDIA", confidence=0.9),
                           regions=[], ocr_lines=[], ocr_confidence=0.9,
                           fields={"aadhaar_number": FieldValue(value="234567890124", confidence=0.9, source="ocr")},
                           codes=[], stamps=[])
    ctx = Ctx(on=date(2026, 9, 23))
    lines = [OcrLine(text="MEERA SYNTHETIC RAO", confidence=0.9, bbox=[10, 10, 90, 20]),
             OcrLine(text="DOB: 21/08/1999", confidence=0.9, bbox=[10, 25, 90, 35]),
             OcrLine(text="2345 6789 0199", confidence=0.9, bbox=[10, 60, 90, 70])]
    _merge_device_fields(ctx, doc, lines)
    assert doc.fields["aadhaar_number"].value == "234567890124"  # server reading kept
    assert doc.fields["date_of_birth"].source == "device"
    check = next(c for c in ctx.checks if c.name == "device_ocr_agreement")
    assert check.status.value == "REVIEW_REQUIRED" and not check.blocking and "aadhaar_number" in check.details["differ"]
