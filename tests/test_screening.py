import shutil

import pytest

from tests.synthetic_documents import (
    generate_face_like_image,
    generate_mrz_lines,
    generate_passport_back_image,
    generate_passport_image,
)

TESSERACT_AVAILABLE = shutil.which("tesseract") is not None
pytestmark = pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="tesseract binary not installed on this host")


def _login(client, db_session, username="screeningtester"):
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    user = User(username=username, hashed_password=hash_password("Str0ngPass!"), role=UserRole.OFFICER)
    db_session.add(user)
    db_session.commit()
    response = client.post("/auth/login", json={"username": username, "password": "Str0ngPass!"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_full_screening_pipeline_end_to_end(client, db_session):
    token = _login(client, db_session)
    line1, line2 = generate_mrz_lines()

    response = client.post(
        "/documents/screen",
        headers={"Authorization": f"Bearer {token}"},
        data={"document_type": "passport", "nationality": "INDIAN"},
        files={
            "front_image": ("front.png", generate_passport_image(), "image/png"),
            "back_image": ("back.png", generate_passport_back_image(line1, line2), "image/png"),
            "live_capture": ("live.png", generate_face_like_image(1), "image/png"),
        },
    )

    assert response.status_code == 200
    body = response.json()

    # Every signal traces back to a real computed value.
    assert body["ocr"]["fields"]["passport_number"] == "N1234567"
    assert body["validation"]["status"] == "PASS"
    assert any(f["check"] == "mrz_checksum_composite" for f in body["validation"]["findings"])
    assert body["tampering"]["tampering_risk"] is not None
    # Deepfake/liveness are real heuristics now (computed from live_capture),
    # not fixed values — check they ran and produced a real 0..1 score.
    assert body["deepfake"]["status"] == "ANALYZED"
    assert 0.0 <= body["deepfake"]["score"] <= 1.0
    assert body["liveness"]["status"] in {"LIVE", "SUSPECTED_SPOOF"}
    assert 0.0 <= body["liveness"]["score"] <= 1.0
    assert body["registry"]["status"] == "NO_HIT"
    # front_image (printed document text) and live_capture (a distinct synthetic
    # face pattern) are genuinely different images here, so a real embedding
    # comparison should — and does — report low similarity, not a placeholder.
    assert -1.0 <= body["face"]["similarity"] <= 1.0
    assert body["face"]["match"] is False
    assert body["identity_graph"]["status"] == "NO_CLUSTER"

    risk = body["risk"]
    assert 0 <= risk["score"] <= 100
    assert risk["decision"] in {"CLEAR", "MANUAL_REVIEW"}
    assert len(risk["breakdown"]) >= 4
    assert any(s["signal"] == "deepfake" for s in risk["breakdown"])
    assert any(s["signal"] == "liveness" for s in risk["breakdown"])
    assert body["verification_id"]


def test_screening_without_back_or_live_capture_still_scores(client, db_session):
    token = _login(client, db_session, username="minimaltester")
    response = client.post(
        "/documents/screen",
        headers={"Authorization": f"Bearer {token}"},
        data={"document_type": "passport", "nationality": "INDIAN"},
        files={"front_image": ("front.png", generate_passport_image(), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["face"] is None
    assert body["identity_graph"] is None
    assert body["validation"] is not None
    assert body["risk"]["score"] is not None


def test_verification_record_roundtrips_with_valid_signature(client, db_session):
    token = _login(client, db_session, username="roundtriptester")
    screen_response = client.post(
        "/documents/screen",
        headers={"Authorization": f"Bearer {token}"},
        data={"document_type": "passport", "nationality": "INDIAN"},
        files={"front_image": ("front.png", generate_passport_image(), "image/png")},
    )
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
    screen_response = client.post(
        "/documents/screen",
        headers={"Authorization": f"Bearer {token}"},
        data={"document_type": "passport", "nationality": "INDIAN"},
        files={"front_image": ("front.png", generate_passport_image(), "image/png")},
    )
    verification_id = screen_response.json()["verification_id"]

    # Simulate an attacker directly editing the stored score in the database.
    record = db_session.get(VerificationRecord, uuid.UUID(verification_id))
    record.score = 0
    record.level = "LOW_RISK"
    record.decision = "CLEAR"
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
        data={"document_type": "passport", "nationality": "INDIAN"},
        files={"front_image": ("front.png", generate_passport_image(), "image/png")},
    )
    assert response.status_code == 401
