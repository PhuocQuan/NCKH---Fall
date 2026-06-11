from fastapi.testclient import TestClient

from src.api_server import app
from src.auth import clear_tokens_for_tests, create_token, verify_login, verify_token

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
