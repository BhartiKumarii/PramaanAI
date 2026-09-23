"""API tests for /api/v1 document verification: auth, validation, the
region-crop privacy guard, persistence + tamper-evident chain, officer
actions, and one full image run on a SYNTHETIC licence."""
import base64
import io

import numpy as np
from PIL import Image

from app.services.validation.mrz import compute_check_digit


def _token(client, db_session, username="docverifier"):
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    db_session.add(User(username=username, hashed_password=hash_password("Str0ngPass!"), role=UserRole.OFFICER))
    db_session.commit()
    r = client.post("/auth/login", json={"username": username, "password": "Str0ngPass!"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _mrz():
    num = "Z1234567<"
    dob, exp = "960412", "310509"
    cn, cd, ce = compute_check_digit(num), compute_check_digit(dob), compute_check_digit(exp)
    pers = "<" * 15
    comp = compute_check_digit(f"{num}{cn}{dob}{cd}{exp}{ce}{pers}")
    return ["P<INDSHARMA<<ANANYA<SYNTHETIC".ljust(44, "<"), f"{num}{cn}IND{dob}{cd}F{exp}{ce}{pers}{comp}"]


def _extracted(**over):
    body = {"documents": [{"document_type": "INDIAN_PASSPORT", "country": "INDIA", "mrz_lines": _mrz(),
                           "fields": {"name": {"value": "ANANYA SYNTHETIC SHARMA"},
                                      "document_number": {"value": "Z1234567"},
                                      "date_of_birth": {"value": "12/04/1996"},
                                      "date_of_expiry": {"value": "09/05/2031"}}}],
            "border_route": "INDIA_NEPAL", "direction": "INDIA_TO_NEPAL", "travel_date": "2026-09-23"}
    body.update(over)
    return body


def test_endpoints_require_authentication(client):
    assert client.get("/api/v1/checkpoints").status_code == 401
    assert client.post("/api/v1/verify/extracted", json=_extracted()).status_code == 401


def test_checkpoints_reference_is_versioned(client, db_session):
    r = client.get("/api/v1/checkpoints", params={"border": "INDIA_NEPAL"}, headers=_token(client, db_session))
    assert r.status_code == 200
    body = r.json()
    assert body["reference_data_version"] and any(c["checkpoint_id"] == "NP-KAKARBHITTA" for c in body["checkpoints"])


def test_upload_validation_rejects_non_images(client, db_session):
    h = _token(client, db_session)
    r = client.post("/api/v1/verify/document", headers=h, files={"files": ("x.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 422


def test_region_crops_covering_whole_document_are_rejected(client, db_session):
    h = _token(client, db_session)
    buf = io.BytesIO()
    Image.new("RGB", (400, 300), "white").save(buf, "JPEG")
    crop = {"label": "text", "bbox": [0, 0, 400, 300], "crop_bbox": [0, 0, 400, 300],
            "image_b64": base64.b64encode(buf.getvalue()).decode()}
    r = client.post("/api/v1/verify/regions", headers=h,
                    json={"documents": [{"image_size": [400, 300], "regions": [crop]}]})
    assert r.status_code == 422 and "full image" in r.json()["detail"]


def test_extracted_path_persists_with_valid_chain_and_officer_action(client, db_session):
    h = _token(client, db_session)
    r = client.post("/api/v1/verify/extracted", headers=h, json=_extracted())
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["id"] and out["checks"]["mrz_check_digits"] == "PASS"
    assert out["checks"]["visa_requirement"] == "NOT_APPLICABLE"  # treaty national: no visa finding
    assert out["checks"]["tampering_analysis"] == "NOT_VERIFIED"  # never claimed without pixels
    assert "FICTIONAL" in out["data_notice"]

    got = client.get(f"/api/v1/verification/{out['id']}", headers=h).json()
    assert got["integrity"] == {"hash_valid": True, "signature_valid": True}
    assert got["record"]["source"] == "DEVICE_EXTRACTED"

    bad = client.post(f"/api/v1/verification/{out['id']}/officer-action", headers=h,
                      json={"action": "REFERRED_FOR_SECONDARY_INSPECTION"})
    assert bad.status_code == 422  # reason required
    ok = client.post(f"/api/v1/verification/{out['id']}/officer-action", headers=h, json={"action": "CLEARED"})
    assert ok.status_code == 200 and ok.json()["officer_action"] == "CLEARED"

    client.post("/api/v1/verify/extracted", headers=h, json=_extracted())
    chain = client.get("/api/v1/verification/chain/verify", headers=h).json()
    assert chain["chain_valid"] and chain["records_checked"] == 2 and "not a distributed ledger" in chain["note"]


def test_tampering_with_a_stored_record_breaks_the_chain(client, db_session):
    from app.models.document_verification import DocumentVerificationRecord

    h = _token(client, db_session)
    rid = client.post("/api/v1/verify/extracted", headers=h, json=_extracted()).json()["id"]
    rec = db_session.query(DocumentVerificationRecord).first()
    rec.overall_status = "PASS" if rec.overall_status != "PASS" else "REVIEW_REQUIRED"
    db_session.commit()
    assert client.get(f"/api/v1/verification/{rid}", headers=h).json()["integrity"]["hash_valid"] is False
    assert client.get("/api/v1/verification/chain/verify", headers=h).json()["chain_valid"] is False


def test_mrz_mismatch_is_review_required_with_named_reason(client, db_session):
    h = _token(client, db_session)
    body = _extracted()
    body["documents"][0]["fields"]["document_number"] = {"value": "Z1234568"}
    out = client.post("/api/v1/verify/extracted", headers=h, json=body).json()
    assert out["overall_status"] in ("REVIEW_REQUIRED", "FAIL")
    assert out["checks"]["mrz_consistency"] == "REVIEW_REQUIRED"
    assert any("Z1234568" in e["description"] for e in out["evidence"])


def test_full_image_run_on_synthetic_driving_licence(client, db_session):
    from scripts.docverify.generate_synthetic_testset import dl_qr_payload, driving_licence

    dl = dict(face=2, number="MH1220190012345", name="ARJUN SYNTHETIC MEHTA", dob="1994-03-15", issue="2019-06-10",
              expiry="2039-03-14")
    img = driving_licence({**dl, "qr": dl_qr_payload(dl["number"], dl["name"], dl["dob"], dl["expiry"])})
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    h = _token(client, db_session)
    r = client.post("/api/v1/verify/driving-licence", headers=h,
                    files={"file": ("dl.jpg", buf.getvalue(), "image/jpeg")}, data={"travel_date": "2026-09-23"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["document_type"] == "DRIVING_LICENCE"
    assert out["checks"]["registry"] == "PASS"
    assert out["checks"]["digital_signature"] == "PASS"
    assert out["checks"]["yellow_gold_feature"] == "PASS"
    assert "overall_status" in out and out["officer_summary"]["headline"]
    # stored result keeps no raw OCR dump
    stored = client.get(f"/api/v1/verification/{out['id']}", headers=h).json()["result"]
    assert stored["documents"][0]["ocr_lines"] == []


def test_idempotent_retry_returns_the_same_record(client, db_session):
    h = _token(client, db_session)
    body = _extracted(client_request_id="device-queue-item-42")
    first = client.post("/api/v1/verify/extracted", headers=h, json=body).json()
    second = client.post("/api/v1/verify/extracted", headers=h, json=body).json()
    assert first["id"] == second["id"]
    assert len(client.get("/api/v1/verification", headers=h).json()) == 1


def test_saturated_instance_returns_503_with_retry_after(client, db_session, monkeypatch):
    from app.services.docverify import concurrency

    h = _token(client, db_session)

    async def busy(*a, **kw):
        raise concurrency.ServerBusy()

    monkeypatch.setattr("app.api.routes.verify_v1.run_heavy", busy)
    r = client.post("/api/v1/verify/extracted", headers=h, json=_extracted())
    assert r.status_code == 503 and r.headers["Retry-After"]


def test_concurrent_appends_keep_the_chain_intact(client, db_session, tmp_path):
    """Several requests in flight at once (threads, each with its own pooled
    connection to a file database — as in a real deployment) must still
    produce one unbroken, gap-free chain."""
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.base import Base
    from app.db.session import get_db
    from app.main import app

    engine = create_engine(f"sqlite:///{tmp_path / 'chain.db'}", connect_args={"check_same_thread": False, "timeout": 30})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def file_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = file_db
    try:
        with Session() as s:
            from app.core.security import hash_password
            from app.models.user import User, UserRole
            s.add(User(username="chainer", hashed_password=hash_password("Str0ngPass!"), role=UserRole.OFFICER))
            s.commit()
        token = client.post("/auth/login", json={"username": "chainer", "password": "Str0ngPass!"}).json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}
        with ThreadPoolExecutor(max_workers=4) as pool:
            codes = list(pool.map(lambda _: client.post("/api/v1/verify/extracted", headers=h,
                                                         json=_extracted()).status_code, range(6)))
        assert codes == [200] * 6
        chain = client.get("/api/v1/verification/chain/verify", headers=h).json()
        assert chain["chain_valid"] and chain["records_checked"] == 6
    finally:
        app.dependency_overrides[get_db] = previous
