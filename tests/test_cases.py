import shutil

import pytest

from tests.synthetic_documents import generate_passport_image

TESSERACT_AVAILABLE = shutil.which("tesseract") is not None
pytestmark = pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="tesseract binary not installed on this host")


def _make_user(db_session, username, role, checkpoint):
    from app.core.security import hash_password
    from app.models.user import User

    user = User(
        username=username,
        hashed_password=hash_password("Str0ngPass!"),
        role=role,
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
        data={"document_type": "passport", "nationality": "INDIAN"},
        files={"front_image": ("front.png", generate_passport_image(), "image/png")},
    )


def test_screening_creates_a_case(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "field1", UserRole.FIELD_OFFICER, checkpoint)
    token = _token(client, "field1")

    response = _screen(client, token)
    assert response.status_code == 200
    body = response.json()
    assert body["case_id"]
    assert body["case_number"].startswith("BSA-")
    assert body["case_status"] in ("PENDING", "REVIEW_REQUIRED")


def test_screening_without_checkpoint_is_rejected(client, db_session):
    from app.models.user import UserRole

    _make_user(db_session, "nocheckpoint", UserRole.FIELD_OFFICER, checkpoint=None)
    token = _token(client, "nocheckpoint")

    response = _screen(client, token)
    assert response.status_code == 400


def test_field_officer_sees_only_their_own_cases(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "fieldA", UserRole.FIELD_OFFICER, checkpoint)
    _make_user(db_session, "fieldB", UserRole.FIELD_OFFICER, checkpoint)
    token_a = _token(client, "fieldA")
    token_b = _token(client, "fieldB")

    _screen(client, token_a)

    resp_a = client.get("/cases", headers={"Authorization": f"Bearer {token_a}"})
    resp_b = client.get("/cases", headers={"Authorization": f"Bearer {token_b}"})
    assert len(resp_a.json()) == 1
    assert len(resp_b.json()) == 0


def test_submit_forwards_case_and_immigration_officer_can_then_see_it(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "field2", UserRole.FIELD_OFFICER, checkpoint)
    _make_user(db_session, "immig2", UserRole.IMMIGRATION_OFFICER, checkpoint)
    field_token = _token(client, "field2")
    immig_token = _token(client, "immig2")

    case_id = _screen(client, field_token).json()["case_id"]

    # Not visible to the Immigration Officer until it's actually sent.
    before = client.get("/cases", headers={"Authorization": f"Bearer {immig_token}"})
    assert len(before.json()) == 0

    submit = client.post(
        f"/cases/{case_id}/submit", json={}, headers={"Authorization": f"Bearer {field_token}"}
    )
    assert submit.status_code == 200
    assert submit.json()["status"] == "SENT"

    after = client.get("/cases", headers={"Authorization": f"Bearer {immig_token}"})
    assert len(after.json()) == 1
    assert after.json()[0]["id"] == case_id


def test_immigration_officer_cannot_see_another_checkpoints_case(client, db_session):
    from app.models.user import UserRole

    checkpoint_a = _checkpoint(db_session, "ATW")
    checkpoint_b = _checkpoint(db_session, "PET")
    _make_user(db_session, "field3", UserRole.FIELD_OFFICER, checkpoint_a)
    _make_user(db_session, "immig3", UserRole.IMMIGRATION_OFFICER, checkpoint_b)
    field_token = _token(client, "field3")
    immig_token = _token(client, "immig3")

    case_id = _screen(client, field_token).json()["case_id"]
    client.post(f"/cases/{case_id}/submit", json={}, headers={"Authorization": f"Bearer {field_token}"})

    resp = client.get(f"/cases/{case_id}", headers={"Authorization": f"Bearer {immig_token}"})
    assert resp.status_code == 404


def test_decision_requires_reason_unless_clear(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "field4", UserRole.FIELD_OFFICER, checkpoint)
    _make_user(db_session, "immig4", UserRole.IMMIGRATION_OFFICER, checkpoint)
    field_token = _token(client, "field4")
    immig_token = _token(client, "immig4")

    case_id = _screen(client, field_token).json()["case_id"]
    client.post(f"/cases/{case_id}/submit", json={}, headers={"Authorization": f"Bearer {field_token}"})

    no_reason = client.post(
        f"/cases/{case_id}/decision",
        json={"decision": "HOLD_REFER"},
        headers={"Authorization": f"Bearer {immig_token}"},
    )
    assert no_reason.status_code == 400

    with_reason = client.post(
        f"/cases/{case_id}/decision",
        json={"decision": "HOLD_REFER", "reason": "Document number does not match MRZ"},
        headers={"Authorization": f"Bearer {immig_token}"},
    )
    assert with_reason.status_code == 200
    body = with_reason.json()
    assert body["status"] == "HOLD_REFER"
    assert body["decisions"][0]["decision"] == "HOLD_REFER"
    assert body["decisions"][0]["reason"] == "Document number does not match MRZ"


def test_field_officer_cannot_record_a_decision(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "field5", UserRole.FIELD_OFFICER, checkpoint)
    token = _token(client, "field5")
    case_id = _screen(client, token).json()["case_id"]

    resp = client.post(
        f"/cases/{case_id}/decision",
        json={"decision": "CLEAR"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_admin_has_no_case_queue_access(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "field6", UserRole.FIELD_OFFICER, checkpoint)
    _make_user(db_session, "admin6", UserRole.IT_ADMIN, checkpoint=None)
    field_token = _token(client, "field6")
    admin_token = _token(client, "admin6")

    case_id = _screen(client, field_token).json()["case_id"]

    listing = client.get("/cases", headers={"Authorization": f"Bearer {admin_token}"})
    assert listing.json() == []

    detail = client.get(f"/cases/{case_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert detail.status_code == 403


def test_add_note_and_audit_trail(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "field7", UserRole.FIELD_OFFICER, checkpoint)
    token = _token(client, "field7")
    case_id = _screen(client, token).json()["case_id"]

    note = client.post(
        f"/cases/{case_id}/notes", json={"note": "Traveler seemed nervous but documents check out"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert note.status_code == 200
    assert note.json()["author_username"] == "field7"

    audit = client.get(f"/cases/{case_id}/audit", headers={"Authorization": f"Bearer {token}"})
    event_types = [e["event_type"] for e in audit.json()]
    assert "CREATED" in event_types
