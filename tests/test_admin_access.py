"""Admin routes that change or delete data are admin-only (REVIEWER);
synthetic test cases can be removed without breaking the audit chain."""
from tests.test_new_monitoring_endpoints import _checkpoint, _make_user, _token


def _users(db_session):
    from app.models.user import UserRole
    cp = _checkpoint(db_session)
    _make_user(db_session, "acc_officer", UserRole.OFFICER, cp)
    _make_user(db_session, "acc_admin", UserRole.REVIEWER, None)


def test_officer_cannot_change_or_delete_admin_data(client, db_session):
    _users(db_session)
    h = {"Authorization": f"Bearer {_token(client, 'acc_officer')}"}
    assert client.delete("/admin/reset-screening", headers=h).status_code == 403
    assert client.delete("/admin/purge-demo-cases", headers=h).status_code == 403
    assert client.request("DELETE", "/admin/test-cases", headers=h, json={"case_numbers": ["X"]}).status_code == 403
    assert client.get("/admin/users", headers=h).status_code == 403
    assert client.post("/admin/users", headers=h, json={"username": "x", "password": "Str0ng!Pass", "role": "OFFICER"}).status_code == 403
    # read-only lists stay available to officers
    assert client.get("/admin/officers", headers=h).status_code == 200
    assert client.get("/admin/checkpoints", headers=h).status_code == 200


def test_admin_can_manage(client, db_session):
    _users(db_session)
    h = {"Authorization": f"Bearer {_token(client, 'acc_admin')}"}
    assert client.get("/admin/users", headers=h).status_code == 200


def test_test_case_removal_refuses_unknown_or_real_cases(client, db_session):
    _users(db_session)
    h = {"Authorization": f"Bearer {_token(client, 'acc_admin')}"}
    r = client.request("DELETE", "/admin/test-cases", headers=h, json={"case_numbers": ["BSA-00000000-0000"]})
    assert r.status_code == 400 and r.json()["detail"]["missing"] == ["BSA-00000000-0000"]
