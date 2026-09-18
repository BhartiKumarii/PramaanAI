import shutil

import pytest

TESSERACT_AVAILABLE = shutil.which("tesseract") is not None
pytestmark = pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="tesseract binary not installed on this host")


def _make_user(db_session, username, checkpoint):
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    user = User(
        username=username, hashed_password=hash_password("Str0ngPass!"), role=UserRole.OFFICER,
        checkpoint_id=checkpoint.id if checkpoint else None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _checkpoint(db_session, code="ATW"):
    from app.models.checkpoint import Checkpoint

    existing = db_session.query(Checkpoint).filter_by(code=code).first()
    if existing:
        return existing
    checkpoint = Checkpoint(code=code, name=f"{code} checkpoint")
    db_session.add(checkpoint)
    db_session.commit()
    db_session.refresh(checkpoint)
    return checkpoint


def _token(client, username):
    response = client.post("/auth/login", json={"username": username, "password": "Str0ngPass!"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _screen(client, token):
    return client.post(
        "/documents/screen",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "document_type": "passport",
            "nationality": "INDIAN",
            "ocr_fields": {"name": "JOHN MICHAEL SMITH", "passport_number": "N1234567"},
            "ocr_confidence": 0.95,
        },
    )


def test_officer_sees_system_wide_audit_log(client, db_session):
    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "auditfield1", checkpoint)
    _make_user(db_session, "auditadmin1", checkpoint=None)
    field_token = _token(client, "auditfield1")
    admin_token = _token(client, "auditadmin1")

    case_id = _screen(client, field_token).json()["case_id"]

    resp = client.get("/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    entries = resp.json()
    matching = [e for e in entries if e["case_id"] == case_id]
    assert len(matching) == 1
    assert matching[0]["event_type"] == "CREATED"
    assert matching[0]["actor_username"] == "auditfield1"
    assert matching[0]["actor_role"] == "OFFICER"
    assert matching[0]["case_number"]


def test_officer_can_access_system_audit_log(client, db_session):
    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "auditimmig1", checkpoint)
    token = _token(client, "auditimmig1")

    resp = client.get("/audit-logs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200  # All officers have full access now


def test_audit_log_requires_auth(client):
    resp = client.get("/audit-logs")
    assert resp.status_code == 401