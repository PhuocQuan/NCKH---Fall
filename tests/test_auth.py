from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api_server import app
from src.auth import (
    AuthConfig,
    AuthUser,
    clear_tokens_for_tests,
    create_provisioned_user,
    create_token,
    delete_provisioned_user,
    list_users_public,
    load_auth_config,
    save_auth_config,
    update_provisioned_user,
    verify_login,
    verify_token,
)

client = TestClient(app)


def setup_function() -> None:
    clear_tokens_for_tests()


def test_verify_login_default_credentials():
    user = verify_login("admin", "nckh2025")
    assert user is not None
    assert user.role == "admin"
    assert verify_login("admin", "wrong") is None


def test_token_lifecycle():
    token = create_token("admin")
    assert verify_token(token) is True
    assert verify_token("invalid") is False


def test_login_endpoint_success():
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "nckh2025"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["token"]
    assert payload["username"] == "admin"


def test_login_endpoint_failure():
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "bad"},
    )
    assert response.status_code == 401


def test_protected_route_requires_auth():
    assert client.get("/api/status").status_code == 401


@pytest.fixture
def auth_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from src import auth

    path = tmp_path / "auth.yaml"
    save_auth_config(
        AuthConfig(
            admin=AuthUser(username="admin", password="nckh2025", role="admin", full_name="Admin"),
            users=(),
        ),
        path,
    )
    monkeypatch.setattr(auth, "DEFAULT_AUTH_PATH", path)
    return path


def test_provisioned_user_crud(auth_path: Path) -> None:
    created = create_provisioned_user(
        username="caregiver.lan",
        password="lan2025",
        full_name="Nguyen Thi Lan",
        role="caregiver",
        path=auth_path,
    )
    assert created.username == "caregiver.lan"

    updated = update_provisioned_user(
        "caregiver.lan",
        full_name="Lan Updated",
        enabled=False,
        path=auth_path,
    )
    assert updated.full_name == "Lan Updated"
    assert updated.enabled is False

    users = list_users_public(auth_path)
    assert any(user["username"] == "caregiver.lan" for user in users)

    delete_provisioned_user("caregiver.lan", path=auth_path)
    assert load_auth_config(auth_path).users == ()


def test_users_api_admin_only(auth_path: Path) -> None:
    create_provisioned_user(
        username="family.tuan",
        password="tuan2025",
        full_name="Anh Tuan",
        role="family",
        path=auth_path,
    )
    assert client.get("/api/users").status_code == 401

    admin_login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "nckh2025"},
    )
    headers = {"Authorization": f"Bearer {admin_login.json()['token']}"}
    listed = client.get("/api/users", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["users"]) >= 2

    user_login = client.post(
        "/api/auth/login",
        json={"username": "family.tuan", "password": "tuan2025"},
    )
    user_headers = {"Authorization": f"Bearer {user_login.json()['token']}"}
    assert client.get("/api/users", headers=user_headers).status_code == 403
