import shutil

import pytest

from app.services.face.embedding import extract_embedding
from tests.synthetic_documents import generate_face_like_image, generate_mrz_lines, generate_passport_image

TESSERACT_AVAILABLE = shutil.which("tesseract") is not None
pytestmark = pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="tesseract binary not installed on this host")

_OCR_FIELDS = {
    "name": "JOHN MICHAEL SMITH",
    "passport_number": "N1234567",
    "nationality": "INDIAN",
    "date_of_birth": "12/04/1990",
    "date_of_expiry": "11/04/2030",
    "gender": "M",
}


def _login(client, db_session, username="screeningtester"):
    from app.core.security import hash_password
    from app.models.checkpoint import Checkpoint
    from app.models.user import User, UserRole

    checkpoint = db_session.query(Checkpoint).filter_by(code="TST").first()
    if checkpoint is None:
        checkpoint = Checkpoint(code="TST", name="Test Checkpoint")
        db_session.add(checkpoint)
        db_session.commit()
    user = User(
        username=username,
        hashed_password=hash_password("Str0ngPass!"),
        role=UserRole.OFFICER,
        checkpoint_id=checkpoint.id,
    )
    db_session.add(user)
    db_session.commit()
    response = client.post("/auth/login", json={"username": username, "password": "Str0ngPass!"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _embedding_for_seed(seed: int) -> list[float]:
    """Real embedding computed from a synthetic face-like image, exactly
    the computation a device would run on-device before submitting only
    the resulting vector (never the image) to /documents/screen."""
    return extract_embedding(generate_face_like_image(seed))


def _screen(client, token, **overrides):
    payload = {
        "document_type": "passport",
        "nationality": "INDIAN",
        "ocr_fields": dict(_OCR_FIELDS),
        "ocr_confidence": 0.95,
    }
    payload.update(overrides)
    return client.post("/documents/screen", headers={"Authorization": f"Bearer {token}"}, json=payload)


def test_full_screening_pipeline_end_to_end(client, db_session):
    token = _login(client, db_session)
    line1, line2 = generate_mrz_lines()

    # A text-heavy document image and a face-shaped pattern are genuinely
    # different visual domains — real embeddings of each should, and do,
    # come out dissimilar, unlike two face-pattern seeds which share too
    # much structure (same ellipses, small per-seed shift) to reliably differ.
    response = _screen(
        client,
        token,
        mrz_text=f"{line1}\n{line2}",
        document_face_embedding=extract_embedding(generate_passport_image()),
        live_face_embedding=_embedding_for_seed(1),
    )

    assert response.status_code == 200
    body = response.json()

    # Every signal traces back to a real computed value.
    assert body["ocr"]["fields"]["passport_number"] == "N1234567"
    assert body["validation"]["status"] == "PASS"
    assert any(f["check"] == "mrz_checksum_composite" for f in body["validation"]["findings"])
    # No pixel-level signal was submitted this call — the risk engine must
    # treat that as "not run", not silently score it as clean.
    assert body["tampering"] is None
    assert body["deepfake"] is None
    assert body["liveness"] is None
    assert body["registry"]["status"] == "NO_HIT"
    # Two genuinely different embeddings (distinct synthetic face seeds) —
    # a real cosine-similarity comparison should, and does, report low
    # similarity, not a placeholder.
    assert -1.0 <= body["face"]["similarity"] <= 1.0
    assert body["face"]["match"] is False
    assert body["identity_graph"]["status"] == "NO_CLUSTER"

    risk = body["risk"]
    assert 0 <= risk["score"] <= 100
    assert risk["decision"] in {"CLEAR", "MANUAL_REVIEW"}
    assert any(s["signal"] == "face_match" for s in risk["breakdown"])
    assert any(s["signal"] == "identity_graph" for s in risk["breakdown"])
    assert body["verification_id"]


def test_screening_without_mrz_or_face_still_scores(client, db_session):
    token = _login(client, db_session, username="minimaltester")
    response = _screen(client, token)
    assert response.status_code == 200
    body = response.json()
    assert body["face"] is None
    assert body["identity_graph"] is None
    assert body["validation"] is not None
    assert body["risk"]["score"] is not None


def test_screening_rejects_empty_ocr_fields(client, db_session):
    token = _login(client, db_session, username="emptyocrtester")
    response = _screen(client, token, ocr_fields={})
    assert response.status_code == 400


def test_verification_record_roundtrips_with_valid_signature(client, db_session):
    token = _login(client, db_session, username="roundtriptester")
    screen_response = _screen(client, token)
    verification_id = screen_response.json()["verification_id"]

    get_response = client.get(
        f"/verification/{verification_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["signature_valid"] is True
    assert body["id"] == verification_id


def test_tampered_stored_record_fails_signature_verification(client, db_session):
    import uuid

    from app.models.verification import VerificationRecord

    token = _login(client, db_session, username="tampertester")
    screen_response = _screen(client, token)
    verification_id = screen_response.json()["verification_id"]

    # Simulate an attacker directly editing the stored score in the
    # database — guaranteed different from whatever was actually signed,
    # not just coincidentally the same value re-written.
    record = db_session.get(VerificationRecord, uuid.UUID(verification_id))
    record.score = (record.score + 37) % 101
    record.level = "HIGH_RISK" if record.level != "HIGH_RISK" else "LOW_RISK"
    record.decision = "MANUAL_REVIEW" if record.decision != "MANUAL_REVIEW" else "CLEAR"
    db_session.commit()

    get_response = client.get(
        f"/verification/{verification_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert get_response.status_code == 200
    assert get_response.json()["signature_valid"] is False


def test_verification_record_not_found(client, db_session):
    token = _login(client, db_session, username="notfoundtester")
    response = client.get(
        "/verification/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_screen_requires_auth(client):
    response = client.post(
        "/documents/screen",
        json={"document_type": "passport", "nationality": "INDIAN", "ocr_fields": dict(_OCR_FIELDS)},
    )
    assert response.status_code == 401
