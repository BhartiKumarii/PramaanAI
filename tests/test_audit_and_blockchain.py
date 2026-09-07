import shutil

import pytest

from app.repositories.blockchain_repository import append_block, find_block_by_verification_id
from app.services.blockchain.local_hash_chain import LocalHashChainBlockchainService
from tests.synthetic_documents import generate_passport_image

TESSERACT_AVAILABLE = shutil.which("tesseract") is not None
pytestmark = pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="tesseract binary not installed on this host")


def _login(client, db_session, username="audittester"):
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    user = User(username=username, hashed_password=hash_password("Str0ngPass!"), role=UserRole.OFFICER)
    db_session.add(user)
    db_session.commit()
    response = client.post("/auth/login", json={"username": username, "password": "Str0ngPass!"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _screen(client, token):
    response = client.post(
        "/documents/screen",
        headers={"Authorization": f"Bearer {token}"},
        data={"document_type": "passport", "nationality": "INDIAN"},
        files={"front_image": ("front.png", generate_passport_image(), "image/png")},
    )
    assert response.status_code == 200
    return response.json()["verification_id"]


# ---- blockchain hash chain (real algorithm) --------------------------------


def test_hash_chain_links_blocks_and_verifies(db_session):
    service = LocalHashChainBlockchainService(db_session)
    service.create_verification_record("v1", "hash1", "officer-a", "SCREENING_CREATED")
    service.create_verification_record("v2", "hash2", "officer-a", "SCREENING_CREATED")

    assert service.verify_record("v1") is True
    assert service.verify_record("v2") is True

    block2 = find_block_by_verification_id(db_session, "v2")
    block1 = find_block_by_verification_id(db_session, "v1")
    assert block2.previous_hash == block1.block_hash


def test_hash_chain_detects_tampering(db_session):
    service = LocalHashChainBlockchainService(db_session)
    service.create_verification_record("v1", "hash1", "officer-a", "SCREENING_CREATED")
    service.create_verification_record("v2", "hash2", "officer-a", "SCREENING_CREATED")
    assert service.verify_record("v2") is True

    # Simulate an attacker editing an earlier block's data directly.
    block1 = find_block_by_verification_id(db_session, "v1")
    block1.document_hash = "tampered-hash-value"
    db_session.commit()

    assert service.verify_record("v1") is False
    assert service.verify_record("v2") is False  # tampering an earlier block breaks the whole chain


def test_verify_record_unknown_id_returns_false(db_session):
    service = LocalHashChainBlockchainService(db_session)
    assert service.verify_record("does-not-exist") is False


# ---- endpoints: audit trail + dispute/clear + blockchain -------------------


def test_screening_auto_logs_created_event_and_blockchain_record(client, db_session):
    import uuid

    from app.models.audit import AuditEvent

    token = _login(client, db_session)
    verification_id = _screen(client, token)

    events = db_session.query(AuditEvent).filter_by(verification_id=uuid.UUID(verification_id)).all()
    assert any(e.event_type == "CREATED" for e in events)

    blockchain_response = client.post(
        "/blockchain/verify",
        headers={"Authorization": f"Bearer {token}"},
        json={"verification_id": verification_id},
    )
    assert blockchain_response.status_code == 200
    body = blockchain_response.json()
    assert body["chain_valid"] is True
    assert body["record"]["verification_id"] == verification_id


def test_get_verification_logs_viewed_event(client, db_session):
    token = _login(client, db_session, username="viewtester")
    verification_id = _screen(client, token)

    client.get(f"/verification/{verification_id}", headers={"Authorization": f"Bearer {token}"})
    client.get(f"/verification/{verification_id}", headers={"Authorization": f"Bearer {token}"})

    audit_response = client.get(
        f"/verification/{verification_id}/audit", headers={"Authorization": f"Bearer {token}"}
    )
    assert audit_response.status_code == 200
    event_types = [e["event_type"] for e in audit_response.json()]
    assert event_types.count("VIEWED") == 2
    assert event_types[0] == "CREATED"  # chronological order


def test_dispute_requires_reason_and_is_logged(client, db_session):
    token = _login(client, db_session, username="disputetester")
    verification_id = _screen(client, token)

    missing_reason = client.post(
        f"/verification/{verification_id}/dispute",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": ""},
    )
    assert missing_reason.status_code == 422

    with_reason = client.post(
        f"/verification/{verification_id}/dispute",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "photo does not resemble the presented traveler"},
    )
    assert with_reason.status_code == 200
    body = with_reason.json()
    assert body["event_type"] == "DISPUTED"
    assert body["reason"] == "photo does not resemble the presented traveler"

    audit_response = client.get(
        f"/verification/{verification_id}/audit", headers={"Authorization": f"Bearer {token}"}
    )
    disputed = [e for e in audit_response.json() if e["event_type"] == "DISPUTED"]
    assert len(disputed) == 1
    assert disputed[0]["reason"] == "photo does not resemble the presented traveler"


def test_clear_is_logged(client, db_session):
    token = _login(client, db_session, username="cleartester")
    verification_id = _screen(client, token)

    response = client.post(
        f"/verification/{verification_id}/clear", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["event_type"] == "CLEARED"


def test_audit_and_dispute_require_auth(client):
    fake_id = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/verification/{fake_id}/audit").status_code == 401
    assert client.post(f"/verification/{fake_id}/dispute", json={"reason": "x"}).status_code == 401


def test_blockchain_verify_unknown_verification_is_404(client, db_session):
    token = _login(client, db_session, username="bctester")
    response = client.post(
        "/blockchain/verify",
        headers={"Authorization": f"Bearer {token}"},
        json={"verification_id": "no-such-id"},
    )
    assert response.status_code == 404
