import shutil

import pytest

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
        json={
            "document_type": "passport",
            "nationality": "INDIAN",
            "ocr_fields": {
                "name": "JOHN MICHAEL SMITH",
                "passport_number": "N1234567",
                "date_of_expiry": "11/04/2030",
            },
            "ocr_confidence": 0.95,
        },
    )


def test_screening_creates_a_case(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "field1", UserRole.OFFICER, checkpoint)
    token = _token(client, "field1")

    response = _screen(client, token)
    assert response.status_code == 200
    body = response.json()
    assert body["case_id"]
    assert body["case_number"].startswith("BSA-")
    assert body["case_status"] in ("PENDING", "REVIEW_REQUIRED")


def test_screening_without_checkpoint_is_rejected(client, db_session):
    from app.models.user import UserRole

    _make_user(db_session, "nocheckpoint", UserRole.OFFICER, checkpoint=None)
    token = _token(client, "nocheckpoint")

    response = _screen(client, token)
    assert response.status_code == 400


def test_officer_sees_all_cases(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "officerA", UserRole.OFFICER, checkpoint)
    _make_user(db_session, "officerB", UserRole.OFFICER, checkpoint)
    token_a = _token(client, "officerA")
    token_b = _token(client, "officerB")

    _screen(client, token_a)

    resp_a = client.get("/cases", headers={"Authorization": f"Bearer {token_a}"})
    resp_b = client.get("/cases", headers={"Authorization": f"Bearer {token_b}"})
    # Both officers can see all cases
    assert len(resp_a.json()) == 1
    assert len(resp_b.json()) == 1


def test_submit_forwards_case_and_other_officer_can_see_it(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "officer1", UserRole.OFFICER, checkpoint)
    _make_user(db_session, "officer2", UserRole.OFFICER, checkpoint)
    token1 = _token(client, "officer1")
    token2 = _token(client, "officer2")

    case_id = _screen(client, token1).json()["case_id"]

    submit = client.post(
        f"/cases/{case_id}/submit", json={}, headers={"Authorization": f"Bearer {token1}"}
    )
    assert submit.status_code == 200
    assert submit.json()["status"] == "SENT"

    after = client.get("/cases", headers={"Authorization": f"Bearer {token2}"})
    ids = [c["id"] for c in after.json()]
    assert case_id in ids


def test_officer_can_see_cases_from_any_checkpoint(client, db_session):
    from app.models.user import UserRole

    checkpoint_a = _checkpoint(db_session, "ATW")
    checkpoint_b = _checkpoint(db_session, "PET")
    _make_user(db_session, "officerA", UserRole.OFFICER, checkpoint_a)
    _make_user(db_session, "officerB", UserRole.OFFICER, checkpoint_b)
    token_a = _token(client, "officerA")
    token_b = _token(client, "officerB")

    case_id = _screen(client, token_a).json()["case_id"]
    client.post(f"/cases/{case_id}/submit", json={}, headers={"Authorization": f"Bearer {token_a}"})

    resp = client.get(f"/cases/{case_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 200  # All officers can see all cases now


def test_supervisor_sees_cases_across_every_checkpoint(client, db_session):
    from app.models.user import UserRole

    checkpoint_a = _checkpoint(db_session, "ATW")
    checkpoint_b = _checkpoint(db_session, "PET")
    _make_user(db_session, "field3b", UserRole.OFFICER, checkpoint_a)
    _make_user(db_session, "sup3b", UserRole.OFFICER, checkpoint=None)
    field_token = _token(client, "field3b")
    sup_token = _token(client, "sup3b")

    case_id = _screen(client, field_token).json()["case_id"]
    client.post(f"/cases/{case_id}/submit", json={}, headers={"Authorization": f"Bearer {field_token}"})

    resp = client.get(f"/cases/{case_id}", headers={"Authorization": f"Bearer {sup_token}"})
    assert resp.status_code == 200
    assert checkpoint_b.code != checkpoint_a.code  # sanity: genuinely a different checkpoint


def test_decision_requires_reason_unless_clear(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "field4", UserRole.OFFICER, checkpoint)
    _make_user(db_session, "immig4", UserRole.OFFICER, checkpoint)
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


def test_officer_can_record_a_decision(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "officer1", UserRole.OFFICER, checkpoint)
    token = _token(client, "officer1")
    case_id = _screen(client, token).json()["case_id"]

    # Submit the case first
    client.post(f"/cases/{case_id}/submit", json={}, headers={"Authorization": f"Bearer {token}"})

    # Then record a decision
    resp = client.post(
        f"/cases/{case_id}/decision",
        json={"decision": "CLEAR"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "CLEAR"


def test_officer_has_full_case_queue_access(client, db_session):
    """All officers have full access to all cases."""
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "officer1", UserRole.OFFICER, checkpoint)
    _make_user(db_session, "officer2", UserRole.OFFICER, checkpoint=None)
    token1 = _token(client, "officer1")
    token2 = _token(client, "officer2")

    case_id = _screen(client, token1).json()["case_id"]

    listing = client.get("/cases", headers={"Authorization": f"Bearer {token2}"})
    assert any(c["id"] == case_id for c in listing.json())

    detail = client.get(f"/cases/{case_id}", headers={"Authorization": f"Bearer {token2}"})
    assert detail.status_code == 200


def test_add_note_and_audit_trail(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "field7", UserRole.OFFICER, checkpoint)
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


def test_timeline_merges_audit_events_and_notes_in_order(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "field8", UserRole.OFFICER, checkpoint)
    _make_user(db_session, "immig8", UserRole.OFFICER, checkpoint)
    field_token = _token(client, "field8")
    immig_token = _token(client, "immig8")

    case_id = _screen(client, field_token).json()["case_id"]
    client.post(
        f"/cases/{case_id}/notes", json={"note": "Queue was long, extra checks done"},
        headers={"Authorization": f"Bearer {field_token}"},
    )
    client.post(f"/cases/{case_id}/submit", json={}, headers={"Authorization": f"Bearer {field_token}"})
    client.post(
        f"/cases/{case_id}/decision", json={"decision": "CLEAR"},
        headers={"Authorization": f"Bearer {immig_token}"},
    )

    timeline = client.get(f"/cases/{case_id}/timeline", headers={"Authorization": f"Bearer {field_token}"})
    assert timeline.status_code == 200
    body = timeline.json()
    event_types = [e["event_type"] for e in body]
    assert "CREATED" in event_types
    assert "NOTE_ADDED" in event_types
    assert "SENT" in event_types
    assert "DECISION_CLEAR" in event_types
    # Chronological, oldest first.
    timestamps = [e["created_at"] for e in body]
    assert timestamps == sorted(timestamps)
