"""Security conditions for /api/v1: authentication, RBAC, input validation,
audit trail, password storage and sensitive-data minimisation."""
import io
import json
from datetime import timedelta

from PIL import Image

from tests.test_docverify_api import _extracted, _token


def _png(size=(300, 200), fmt="PNG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, "white").save(buf, fmt)
    return buf.getvalue()


def test_invalid_jwt_is_rejected(client):
    r = client.post("/api/v1/verify/extracted", json=_extracted(), headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401


def test_expired_jwt_is_rejected(client, db_session):
    from app.core.security import _create_token
    from app.models.user import User

    _token(client, db_session, "expiring")
    user = db_session.query(User).filter_by(username="expiring").one()
    expired = _create_token(str(user.id), user.role.value, timedelta(minutes=-5), "access")
    r = client.get("/api/v1/verification", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401


def test_deactivated_account_is_rejected(client, db_session):
    from app.models.user import User

    h = _token(client, db_session, "leaver")
    user = db_session.query(User).filter_by(username="leaver").one()
    user.is_active = False
    db_session.commit()
    assert client.get("/api/v1/verification", headers=h).status_code == 401


def test_field_officer_cannot_make_reviewer_decisions(client, db_session):
    """RBAC: final case decisions are REVIEWER-only (tested end to end in
    test_cases); here, a forged role claim in a token is not trusted over
    the database role."""
    from app.core.security import _create_token
    from app.models.user import User

    _token(client, db_session, "officer9")
    user = db_session.query(User).filter_by(username="officer9").one()
    forged = _create_token(str(user.id), "REVIEWER", timedelta(minutes=5), "access")
    r = client.post("/cases/00000000-0000-0000-0000-000000000000/decision", json={"decision": "CLEAR"},
                    headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 403


def test_oversized_upload_is_rejected(client, db_session):
    h = _token(client, db_session)
    big = b"\xff\xd8" + b"0" * (10 * 1024 * 1024 + 10)
    r = client.post("/api/v1/verify/document", headers=h, files={"files": ("big.jpg", big, "image/jpeg")})
    assert r.status_code == 413


def test_unsupported_file_type_is_rejected(client, db_session):
    h = _token(client, db_session)
    r = client.post("/api/v1/verify/document", headers=h, files={"files": ("a.gif", _png(fmt="GIF"), "image/gif")})
    assert r.status_code == 415


def test_invalid_api_requests_are_rejected(client, db_session):
    h = _token(client, db_session)
    assert client.post("/api/v1/verify/document", headers=h, data={"border_route": "INDIA_CHINA"},
                       files={"files": ("a.png", _png(), "image/png")}).status_code == 422
    assert client.post("/api/v1/verify/extracted", headers=h, json={"documents": []}).status_code == 422
    assert client.post("/api/v1/verify/extracted", headers=h,
                       json=_extracted(client_request_id="bad id with spaces")).status_code == 422
    assert client.post("/api/v1/verify/regions", headers=h, json={"documents": [{"image_size": [10, 10],
                                                                                  "regions": []}]}).status_code == 422


def test_audit_event_is_written_for_every_verification(client, db_session):
    from app.models.audit import AuditEvent

    h = _token(client, db_session)
    vid = client.post("/api/v1/verify/extracted", headers=h, json=_extracted()).json()["id"]
    client.get(f"/api/v1/verification/{vid}", headers=h)
    events = {e.event_type for e in db_session.query(AuditEvent).all() if vid in (e.reason or "")}
    assert {"DOCVERIFY_CREATED", "DOCVERIFY_VIEWED"} <= events


def test_passwords_are_stored_as_argon2_hashes(client, db_session):
    from app.models.user import User

    _token(client, db_session, "hashcheck")
    stored = db_session.query(User).filter_by(username="hashcheck").one().hashed_password
    assert stored.startswith("$argon2") and "Str0ngPass!" not in stored


def test_sensitive_data_is_minimised(client, db_session):
    h = _token(client, db_session)
    body = _extracted()
    body["documents"] = [{"document_type": "AADHAAR", "country": "INDIA",
                          "fields": {"aadhaar_number": {"value": "234567890124"}, "name": {"value": "SYNTHETIC PERSON"}}}]
    out = client.post("/api/v1/verify/extracted", headers=h, json=body).json()
    raw = json.dumps(out)
    assert "234567890124" not in raw and "XXXX XXXX 0124" in raw  # Aadhaar never returned in full
    def vectors(node):
        if isinstance(node, list) and len(node) >= 64 and all(isinstance(v, (int, float)) for v in node):
            yield node
        elif isinstance(node, dict):
            for v in node.values():
                yield from vectors(v)
        elif isinstance(node, list):
            for v in node:
                yield from vectors(v)
    assert not list(vectors(out))  # no biometric (embedding-like) vectors in responses
    listing = client.get("/api/v1/verification", headers=h).json()
    assert listing and "fields" not in json.dumps(listing)  # list view is summary-only
