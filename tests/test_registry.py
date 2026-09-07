from app.services.registry.fuzzy import name_similarity
from app.services.registry.lookup import lookup_registry


def _create_user(db_session, username, role):
    from app.core.security import hash_password
    from app.models.user import User

    user = User(username=username, hashed_password=hash_password("Str0ngPass!"), role=role)
    db_session.add(user)
    db_session.commit()
    return user


def _login(client, username):
    response = client.post("/auth/login", json={"username": username, "password": "Str0ngPass!"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _seed_default(client, admin_token):
    response = client.post(
        "/registry/seed", headers={"Authorization": f"Bearer {admin_token}"}, json={}
    )
    assert response.status_code == 200
    return response.json()


# ---- fuzzy matching (pure algorithm) ---------------------------------------


def test_name_similarity_handles_typo():
    assert name_similarity("RAVI KUMAR SHARMA", "RAVI KUMAR SHRMA") > 0.9


def test_name_similarity_handles_name_order_swap():
    assert name_similarity("RAVI KUMAR SHARMA", "SHARMA RAVI KUMAR") > 0.99


def test_name_similarity_low_for_different_names():
    assert name_similarity("RAVI KUMAR SHARMA", "JOHN MICHAEL SMITH") < 0.5


# ---- lookup service (real DB query) ----------------------------------------


def test_lookup_registry_exact_document_number_hit(db_session):
    from app.repositories.registry_repository import insert_entries

    insert_entries(
        db_session,
        [{"document_number": "N7654321", "full_name": "RAVI KUMAR SHARMA", "reason": "lost document", "severity": "MEDIUM"}],
    )
    result = lookup_registry(db_session, document_number="n7654321", name=None)
    assert result.status == "HIT"
    assert len(result.hits) == 1
    assert result.hits[0].match_type == "EXACT"
    assert result.hits[0].confidence == 1.0


def test_lookup_registry_fuzzy_name_hit(db_session):
    from app.repositories.registry_repository import insert_entries

    insert_entries(
        db_session,
        [{"document_number": "N7654321", "full_name": "RAVI KUMAR SHARMA", "reason": "lost document", "severity": "MEDIUM"}],
    )
    result = lookup_registry(db_session, document_number=None, name="RAVI KUMAR SHRMA")
    assert result.status == "HIT"
    assert result.hits[0].match_type == "FUZZY"
    assert 0 < result.hits[0].confidence < 1.0


def test_lookup_registry_no_hit(db_session):
    result = lookup_registry(db_session, document_number="Z0000000", name="NOBODY HERE")
    assert result.status == "NO_HIT"
    assert result.hits == []


def test_lookup_never_collapses_exact_and_fuzzy_into_one_flag(db_session):
    from app.repositories.registry_repository import insert_entries
    from app.models.user import UserRole  # noqa: F401 — ensure metadata registered in isolation

    insert_entries(
        db_session,
        [{"document_number": "N7654321", "full_name": "RAVI KUMAR SHARMA", "reason": "lost document", "severity": "MEDIUM"}],
    )
    # Exact document number AND a fuzzy-matching name in the same request:
    # both signals must appear distinctly, not merged into a single hit.
    result = lookup_registry(db_session, document_number="N7654321", name="RAVI KUMAR SHRMA")
    match_types = {hit.match_type for hit in result.hits}
    assert match_types == {"EXACT", "FUZZY"}


# ---- endpoints --------------------------------------------------------------


def test_seed_requires_admin_role(client, db_session):
    from app.models.user import UserRole

    _create_user(db_session, "officer_noseed", UserRole.OFFICER)
    token = _login(client, "officer_noseed")
    response = client.post("/registry/seed", headers={"Authorization": f"Bearer {token}"}, json={})
    assert response.status_code == 403


def test_seed_and_lookup_endpoint_end_to_end(client, db_session):
    from app.models.user import UserRole

    _create_user(db_session, "admin1", UserRole.ADMIN)
    admin_token = _login(client, "admin1")
    seed_response = _seed_default(client, admin_token)
    assert seed_response["seeded"] == 3

    _create_user(db_session, "officer1", UserRole.OFFICER)
    officer_token = _login(client, "officer1")

    exact_response = client.post(
        "/registry/lookup",
        headers={"Authorization": f"Bearer {officer_token}"},
        json={"document_number": "X1122334"},
    )
    assert exact_response.status_code == 200
    body = exact_response.json()
    assert body["status"] == "HIT"
    assert body["hits"][0]["match_type"] == "EXACT"
    assert body["hits"][0]["registry_reason"] == "overstay violation on prior crossing"

    no_hit_response = client.post(
        "/registry/lookup",
        headers={"Authorization": f"Bearer {officer_token}"},
        json={"document_number": "Q0000000", "name": "NOBODY AT ALL"},
    )
    assert no_hit_response.json()["status"] == "NO_HIT"


def test_lookup_requires_auth(client):
    response = client.post("/registry/lookup", json={"document_number": "N7654321"})
    assert response.status_code == 401
