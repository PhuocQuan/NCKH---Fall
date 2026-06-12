from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.access_requests import create_request, list_requests, update_request_status
from src.api_server import app
from src.auth import clear_tokens_for_tests

client = TestClient(app)


def setup_function() -> None:
    clear_tokens_for_tests()


def auth_headers() -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "nckh2025"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture
def requests_path(tmp_path: Path) -> Path:
    return tmp_path / "access_requests.json"


def test_create_and_review_request(requests_path: Path) -> None:
    entry = create_request(
        full_name="Tran Van B",
        email="b@example.com",
        phone="0901111111",
        role="family",
        message="Cham soc ong noi",
        path=requests_path,
    )
    assert entry.status == "pending"
    updated = update_request_status(entry.id, status="approved", path=requests_path)
    assert updated.status == "approved"
    assert len(list_requests(status="pending", path=requests_path)) == 0


def test_public_submit_and_admin_list(requests_path: Path, monkeypatch) -> None:
    from src import access_requests as mod

    monkeypatch.setattr(mod, "DEFAULT_REQUESTS_PATH", requests_path)

    created = client.post(
        "/api/access-requests",
        json={
            "full_name": "Le Thi C",
            "email": "c@example.com",
            "phone": "0902222222",
            "role": "caregiver",
            "message": "Yeu cau truy cap",
        },
    )
    assert created.status_code == 200

    denied = client.get("/api/access-requests")
    assert denied.status_code == 401

    listed = client.get("/api/access-requests", headers=auth_headers())
    assert listed.status_code == 200
    assert listed.json()["pending_count"] >= 1
