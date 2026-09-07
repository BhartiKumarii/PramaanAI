from tests.synthetic_documents import generate_face_like_image


def _login(client, db_session):
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    user = User(username="facetester", hashed_password=hash_password("Str0ngPass!"), role=UserRole.OFFICER)
    db_session.add(user)
    db_session.commit()

    response = client.post("/auth/login", json={"username": "facetester", "password": "Str0ngPass!"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_face_verify_matches_same_identity(client, db_session):
    token = _login(client, db_session)
    image_bytes = generate_face_like_image(1)

    response = client.post(
        "/face/verify",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "document_face": ("doc.png", image_bytes, "image/png"),
            "presented_face": ("live.png", image_bytes, "image/png"),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["match"] is True
    assert body["similarity"] > 0.99
    assert "cosine similarity" in body["reason"]


def test_face_verify_flags_different_identities(client, db_session):
    token = _login(client, db_session)

    response = client.post(
        "/face/verify",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "document_face": ("doc.png", generate_face_like_image(1), "image/png"),
            "presented_face": ("live.png", generate_face_like_image(9), "image/png"),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["similarity"] < 0.99


def test_face_verify_requires_auth(client):
    image_bytes = generate_face_like_image(1)
    response = client.post(
        "/face/verify",
        files={
            "document_face": ("doc.png", image_bytes, "image/png"),
            "presented_face": ("live.png", image_bytes, "image/png"),
        },
    )
    assert response.status_code == 401


def test_face_verify_rejects_empty_file(client, db_session):
    token = _login(client, db_session)
    response = client.post(
        "/face/verify",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "document_face": ("doc.png", b"", "image/png"),
            "presented_face": ("live.png", generate_face_like_image(1), "image/png"),
        },
    )
    assert response.status_code == 400
