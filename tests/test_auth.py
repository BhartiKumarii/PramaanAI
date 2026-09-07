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
