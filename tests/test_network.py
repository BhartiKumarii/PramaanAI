import shutil

import pytest

from app.services.face.embedding import extract_embedding
from tests.synthetic_documents import generate_face_like_image

TESSERACT_AVAILABLE = shutil.which("tesseract") is not None
pytestmark = pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="tesseract binary not installed on this host")


def _make_user(db_session, username, role, checkpoint):
    from app.core.security import hash_password
    from app.models.user import User

    user = User(
        username=username, hashed_password=hash_password("Str0ngPass!"), role=role,
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


def _screen(client, token, *, name="JOHN MICHAEL SMITH", passport_number="N1234567", live_seed=None):
    payload = {
        "document_type": "passport",
        "nationality": "INDIAN",
        "ocr_fields": {"name": name, "passport_number": passport_number, "date_of_expiry": "11/04/2030"},
        "ocr_confidence": 0.95,
    }
    if live_seed is not None:
        payload["live_face_embedding"] = extract_embedding(generate_face_like_image(live_seed))
    return client.post("/documents/screen", headers={"Authorization": f"Bearer {token}"}, json=payload)


def test_same_document_number_creates_a_relationship_visible_in_the_graph(client, db_session):
    """Identity/pattern analysis is a Supervisor+Admin capability — see
    app/api/routes/network.py's role note."""
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "netfield1", UserRole.OFFICER, checkpoint)
    _make_user(db_session, "netsup1", UserRole.OFFICER, checkpoint=None)
    field_token = _token(client, "netfield1")
    sup_token = _token(client, "netsup1")

    case_1 = _screen(client, field_token, passport_number="N1234567").json()["case_id"]
    case_2 = _screen(client, field_token, passport_number="N1234567").json()["case_id"]
    assert case_1 != case_2

    graph = client.get(f"/network/cases/{case_1}", headers={"Authorization": f"Bearer {sup_token}"})
    assert graph.status_code == 200
    body = graph.json()
    assert any(e["relationship_type"] == "SAME_DOCUMENT_NUMBER" for e in body["edges"])
    # Never expose the raw document number, even in the graph's own detail.
    for node in body["nodes"]:
        assert "N1234567" not in str(node.get("detail", {}))


def test_officer_can_access_network_endpoints(client, db_session):
    """All officers can access network/identity-pattern endpoints."""
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "officer1", UserRole.OFFICER, checkpoint)
    _make_user(db_session, "officer2", UserRole.OFFICER, checkpoint)
    token1 = _token(client, "officer1")
    token2 = _token(client, "officer2")
    case_id = _screen(client, token1).json()["case_id"]

    resp = client.get(f"/network/cases/{case_id}", headers={"Authorization": f"Bearer {token1}"})
    assert resp.status_code == 200

    resp2 = client.get(f"/network/cases/{case_id}", headers={"Authorization": f"Bearer {token2}"})
    assert resp2.status_code == 200


def test_relationships_endpoint_lists_the_evidence_case(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "netfield3", UserRole.OFFICER, checkpoint)
    _make_user(db_session, "netsup3", UserRole.OFFICER, checkpoint=None)
    field_token = _token(client, "netfield3")
    sup_token = _token(client, "netsup3")

    _screen(client, field_token, passport_number="N7777777")
    _screen(client, field_token, passport_number="N7777777")

    resp = client.get("/network/relationships", headers={"Authorization": f"Bearer {sup_token}"})
    assert resp.status_code == 200
    types = [r["relationship_type"] for r in resp.json()]
    assert "SAME_DOCUMENT_NUMBER" in types


def test_identity_history_flags_same_face_under_different_names(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "netfield4", UserRole.OFFICER, checkpoint)
    token = _token(client, "netfield4")

    case_1 = _screen(
        client, token, name="AAKASH KUMAR", passport_number="N1111111", live_seed=42
    ).json()["case_id"]
    case_2 = _screen(
        client, token, name="ROHIT SHARMA", passport_number="N2222222", live_seed=42
    ).json()["case_id"]

    history = client.get(f"/cases/{case_2}/identity-history", headers={"Authorization": f"Bearer {token}"})
    assert history.status_code == 200
    body = history.json()
    assert len(body) == 1
    assert body[0]["case_id"] == case_1
    assert body[0]["declared_name"] == "AAKASH KUMAR"
    assert body[0]["similarity"] is not None
    assert body[0]["similarity"] >= 0.75


def test_identity_history_is_empty_without_a_live_capture(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "netfield5", UserRole.OFFICER, checkpoint)
    token = _token(client, "netfield5")
    case_id = _screen(client, token).json()["case_id"]

    history = client.get(f"/cases/{case_id}/identity-history", headers={"Authorization": f"Bearer {token}"})
    assert history.status_code == 200
    assert history.json() == []
