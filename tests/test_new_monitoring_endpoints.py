import shutil

import pytest

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


def _screen(client, token, name="JOHN MICHAEL SMITH"):
    return client.post(
        "/documents/screen",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "document_type": "passport",
            "nationality": "INDIAN",
            "ocr_fields": {"name": name, "passport_number": "N1234567"},
            "ocr_confidence": 0.95,
        },
    )


def test_supervisor_can_search_persons_by_name(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    field = _make_user(db_session, "personfield1", UserRole.OFFICER, checkpoint)
    supervisor = _make_user(db_session, "personsup1", UserRole.OFFICER, checkpoint=None)
    field_token = _token(client, "personfield1")
    sup_token = _token(client, "personsup1")

    assert _screen(client, field_token, name="JANE ANNE DOE").status_code == 200

    resp = client.get("/network/persons/search", params={"q": "jane"}, headers={"Authorization": f"Bearer {sup_token}"})
    assert resp.status_code == 200
    results = resp.json()
    assert any("JANE" in r["full_name"] for r in results)


def test_officer_can_search_persons(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "officer1", UserRole.OFFICER, checkpoint)
    token = _token(client, "officer1")

    resp = client.get("/network/persons/search", params={"q": "a"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_officer_roster_shows_real_case_count(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    field = _make_user(db_session, "rosterfield1", UserRole.OFFICER, checkpoint)
    admin = _make_user(db_session, "rosteradmin1", UserRole.OFFICER, checkpoint=None)
    field_token = _token(client, "rosterfield1")
    admin_token = _token(client, "rosteradmin1")

    assert _screen(client, field_token).status_code == 200

    resp = client.get("/admin/officers", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    rows = {r["username"]: r for r in resp.json()}
    assert rows["rosterfield1"]["case_count"] >= 1
    assert rows["rosterfield1"]["role"] == "OFFICER"


def test_officer_can_list_officers(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    _make_user(db_session, "officer1", UserRole.OFFICER, checkpoint)
    token = _token(client, "officer1")

    resp = client.get("/admin/officers", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_analytics_dashboard_reflects_real_screenings(client, db_session):
    from app.models.user import UserRole

    checkpoint = _checkpoint(db_session)
    field = _make_user(db_session, "analyticsfield1", UserRole.OFFICER, checkpoint)
    supervisor = _make_user(db_session, "analyticssup1", UserRole.OFFICER, checkpoint=None)
    field_token = _token(client, "analyticsfield1")
    sup_token = _token(client, "analyticssup1")

    assert _screen(client, field_token).status_code == 200

    resp = client.get("/dashboard/analytics", headers={"Authorization": f"Bearer {sup_token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_screenings"] >= 1
    assert any(bucket["key"] == "passport" for bucket in body["by_document_type"])


def test_admin_sees_real_risk_config(client, db_session):
    from app.models.user import UserRole

    _make_user(db_session, "riskadmin1", UserRole.OFFICER, checkpoint=None)
    token = _token(client, "riskadmin1")

    resp = client.get("/system/risk-config", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    from app.services.risk.engine import _WEIGHTS

    assert body["weights"]["checksum"] == _WEIGHTS["checksum"]
    from app.services.risk.engine import _LOW_RISK_CEILING
    assert body["low_risk_ceiling"] == _LOW_RISK_CEILING  # live constant (recalibrated in 07a2113)


def test_officer_can_see_risk_config(client, db_session):
    from app.models.user import UserRole

    _make_user(db_session, "officer1", UserRole.OFFICER, checkpoint=None)
    token = _token(client, "officer1")

    resp = client.get("/system/risk-config", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
