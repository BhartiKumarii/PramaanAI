import shutil

import pytest

from tests.synthetic_documents import generate_passport_image, generate_visa_image

TESSERACT_AVAILABLE = shutil.which("tesseract") is not None
pytestmark = pytest.mark.skipif(
    not TESSERACT_AVAILABLE, reason="tesseract binary not installed on this host"
)


def _login(client, db_session):
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    user = User(username="ocrtester", hashed_password=hash_password("Str0ngPass!"), role=UserRole.OFFICER)
    db_session.add(user)
    db_session.commit()

    response = client.post("/auth/login", json={"username": "ocrtester", "password": "Str0ngPass!"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_ocr_passport_extracts_fields(client, db_session):
    token = _login(client, db_session)
    image_bytes = generate_passport_image()

    response = client.post(
        "/documents/ocr",
        headers={"Authorization": f"Bearer {token}"},
        data={"document_type": "passport"},
        files={"file": ("passport.png", image_bytes, "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["document_type"] == "passport"
    assert body["ocr_confidence"] > 0.5
    fields = body["fields"]
    assert fields.get("passport_number") == "N1234567"
    assert fields.get("nationality") == "INDIAN"
    assert fields.get("date_of_birth") == "12/04/1990"


def test_ocr_visa_extracts_fields(client, db_session):
    token = _login(client, db_session)
    image_bytes = generate_visa_image()

    response = client.post(
        "/documents/ocr",
        headers={"Authorization": f"Bearer {token}"},
        data={"document_type": "visa"},
        files={"file": ("visa.png", image_bytes, "image/png")},
    )

    assert response.status_code == 200
    fields = response.json()["fields"]
    assert fields.get("visa_number") == "V9988776"
    assert fields.get("stay_duration") == "30 DAYS"


def test_ocr_requires_auth(client):
    image_bytes = generate_passport_image()
    response = client.post(
        "/documents/ocr",
        data={"document_type": "passport"},
        files={"file": ("passport.png", image_bytes, "image/png")},
    )
    assert response.status_code == 401


def test_ocr_rejects_empty_file(client, db_session):
    token = _login(client, db_session)
    response = client.post(
        "/documents/ocr",
        headers={"Authorization": f"Bearer {token}"},
        data={"document_type": "passport"},
        files={"file": ("empty.png", b"", "image/png")},
    )
    assert response.status_code == 400
