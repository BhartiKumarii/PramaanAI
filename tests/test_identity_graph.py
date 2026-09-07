from app.repositories.identity_embedding_repository import insert_embedding, list_all
from app.services.face.embedding import extract_embedding
from app.services.identity_graph.graph import build_graph, find_multi_identity_cluster
from tests.synthetic_documents import generate_face_like_image


def _login(client, db_session, username="identitytester"):
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    user = User(username=username, hashed_password=hash_password("Str0ngPass!"), role=UserRole.OFFICER)
    db_session.add(user)
    db_session.commit()
    response = client.post("/auth/login", json={"username": username, "password": "Str0ngPass!"})
    assert response.status_code == 200
    return response.json()["access_token"]


# ---- graph analysis (pure algorithm, controlled embeddings) ---------------


def test_same_face_under_two_names_forms_cluster(db_session):
    same_face_bytes = generate_face_like_image(1)
    embedding_a = extract_embedding(same_face_bytes)
    embedding_b = extract_embedding(same_face_bytes)  # identical face, re-extracted

    record_a = insert_embedding(db_session, "RAVI KUMAR SHARMA", "N1111111", embedding_a)
    record_b = insert_embedding(db_session, "SANJAY KUMAR VERMA", "N2222222", embedding_b)

    graph = build_graph(list_all(db_session))
    result = find_multi_identity_cluster(graph, str(record_b.id))

    assert result.status == "CLUSTER_FOUND"
    assert result.cluster_size == 2
    names = {m.reference_name for m in result.members}
    assert names == {"RAVI KUMAR SHARMA", "SANJAY KUMAR VERMA"}


def test_different_faces_do_not_cluster(db_session):
    record_a = insert_embedding(
        db_session, "PERSON ONE", "N1111111", extract_embedding(generate_face_like_image(1))
    )
    insert_embedding(db_session, "PERSON TWO", "N2222222", extract_embedding(generate_face_like_image(9)))

    graph = build_graph(list_all(db_session))
    result = find_multi_identity_cluster(graph, str(record_a.id))

    assert result.status == "NO_CLUSTER"
    assert result.cluster_size == 1


def test_same_face_same_identity_is_not_flagged_as_multi_identity(db_session):
    same_face_bytes = generate_face_like_image(1)
    record_a = insert_embedding(db_session, "RAVI KUMAR SHARMA", "N1111111", extract_embedding(same_face_bytes))
    record_b = insert_embedding(db_session, "RAVI KUMAR SHARMA", "N1111111", extract_embedding(same_face_bytes))

    graph = build_graph(list_all(db_session))
    result = find_multi_identity_cluster(graph, str(record_b.id))

    # Same declared name AND same document number for both records in the
    # cluster — that's a repeat screening of the same person, not fraud.
    assert result.status == "NO_CLUSTER"
    assert result.cluster_size == 2


# ---- endpoint ---------------------------------------------------------------


def test_identity_check_endpoint_flags_cluster_across_two_calls(client, db_session):
    token = _login(client, db_session)
    same_face_bytes = generate_face_like_image(1)

    first = client.post(
        "/identity/check",
        headers={"Authorization": f"Bearer {token}"},
        data={"reference_name": "RAVI KUMAR SHARMA", "document_number": "N1111111"},
        files={"file": ("face1.png", same_face_bytes, "image/png")},
    )
    assert first.status_code == 200
    assert first.json()["status"] == "NO_CLUSTER"

    second = client.post(
        "/identity/check",
        headers={"Authorization": f"Bearer {token}"},
        data={"reference_name": "SANJAY KUMAR VERMA", "document_number": "N2222222"},
        files={"file": ("face1_again.png", same_face_bytes, "image/png")},
    )
    assert second.status_code == 200
    body = second.json()
    assert body["status"] == "CLUSTER_FOUND"
    assert body["cluster_size"] == 2


def test_identity_check_requires_auth(client):
    response = client.post(
        "/identity/check",
        data={"reference_name": "SOMEONE"},
        files={"file": ("face.png", generate_face_like_image(1), "image/png")},
    )
    assert response.status_code == 401


def test_deepfake_endpoint_returns_real_heuristic_result(client, db_session):
    token = _login(client, db_session, username="deepfaketester")
    response = client.post(
        "/documents/deepfake",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("live.png", generate_face_like_image(1), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ANALYZED"
    assert 0.0 <= body["score"] <= 1.0
    assert "heuristic" in body["reason"]
