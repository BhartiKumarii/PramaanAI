from app.core.security import hash_password
from app.models.user import User, UserRole


def _create_user(db_session, username="officer1", password="Str0ngPass!", role=UserRole.OFFICER):
    user = User(username=username, hashed_password=hash_password(password), role=role)
    db_session.add(user)
    db_session.commit()
    return user


def test_login_success(client, db_session):
    _create_user(db_session)
    response = client.post("/auth/login", json={"username": "officer1", "password": "Str0ngPass!"})
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "OFFICER"
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


def test_login_wrong_password(client, db_session):
    _create_user(db_session)
    response = client.post("/auth/login", json={"username": "officer1", "password": "wrong"})
    assert response.status_code == 401


def test_login_unknown_user(client):
    response = client.post("/auth/login", json={"username": "nobody", "password": "whatever"})
    assert response.status_code == 401


def test_me_includes_real_assigned_checkpoint(client, db_session):
    from app.models.checkpoint import Checkpoint

    checkpoint = Checkpoint(code="ATW", name="Attari-Wagah")
    db_session.add(checkpoint)
    db_session.commit()
    db_session.refresh(checkpoint)
    _create_user(db_session, username="checkpointed_officer")
    user = db_session.query(User).filter_by(username="checkpointed_officer").first()
    user.checkpoint_id = checkpoint.id
    db_session.commit()

    login = client.post("/auth/login", json={"username": "checkpointed_officer", "password": "Str0ngPass!"})
    token = login.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    body = me.json()
    assert body["checkpoint_code"] == "ATW"
    assert body["checkpoint_name"] == "Attari-Wagah"


def test_me_checkpoint_is_null_when_unassigned(client, db_session):
    _create_user(db_session, username="no_checkpoint_officer")
    login = client.post("/auth/login", json={"username": "no_checkpoint_officer", "password": "Str0ngPass!"})
    token = login.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["checkpoint_code"] is None


def test_refresh_issues_new_tokens_and_rejects_an_access_token(client, db_session):
    _create_user(db_session)
    login = client.post("/auth/login", json={"username": "officer1", "password": "Str0ngPass!"}).json()

    ok = client.post("/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert ok.status_code == 200
    assert ok.json()["access_token"]

    # An access token must never be accepted where a refresh token is required.
    bad = client.post("/auth/refresh", json={"refresh_token": login["access_token"]})
    assert bad.status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": "garbage"}).status_code == 401
