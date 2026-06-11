from fastapi.testclient import TestClient

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
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["auth_mode"] == "admin_provisioned"


def test_cors_allows_capacitor_app():
    response = client.get(
        "/api/health",
        headers={"Origin": "https://localhost"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "*"


def test_status_requires_auth():
    assert client.get("/api/status").status_code == 401


def test_status_when_idle():
    response = client.get("/api/status", headers=auth_headers())
    assert response.status_code == 200
    payload = response.json()
    assert payload["running"] is False
    assert payload["status"] in {"READY", "STOPPED"}


def test_events_endpoint():
    response = client.get("/api/events?limit=5", headers=auth_headers())
    assert response.status_code == 200
    payload = response.json()
    assert "events" in payload
    assert isinstance(payload["events"], list)


def test_stop_when_idle():
    response = client.post("/api/control/stop", headers=auth_headers())
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_reset_requires_running():
    response = client.post("/api/control/reset", headers=auth_headers())
    assert response.status_code == 409


def test_camera_stream_requires_running():
    response = client.get("/api/camera/stream.mjpg", headers=auth_headers())
    assert response.status_code == 409


def test_camera_frame_requires_running():
    response = client.get("/api/camera/frame.jpg", headers=auth_headers())
    assert response.status_code == 409


def test_ui_config_endpoint():
    response = client.get("/api/ui-config", headers=auth_headers())
    assert response.status_code == 200
    payload = response.json()
    assert payload["status_display"]["ALERT"] == "CANH BAO"
    assert "status_theme" in payload


def test_settings_endpoint_roundtrip():
    response = client.get("/api/settings", headers=auth_headers())
    assert response.status_code == 200
    assert "profile" in response.json()


def test_mobile_web_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "Guardian Watch" in response.text
    assert "Đăng nhập" in response.text
    assert "Thông báo" in response.text


def test_auth_me():
    headers = auth_headers()
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "authenticated"


def test_cameras_crud(tmp_path, monkeypatch):
    from src import camera_registry

    cameras_file = tmp_path / "cameras.yaml"
    monkeypatch.setattr(camera_registry, "DEFAULT_CAMERAS_PATH", cameras_file)
    headers = auth_headers()

    listed = client.get("/api/cameras", headers=headers)
    assert listed.status_code == 200
    assert isinstance(listed.json()["cameras"], list)

    created = client.post(
        "/api/cameras",
        headers=headers,
        json={
            "id": "CAM-77",
            "name": "San thuong",
            "room": "Tang 2",
            "source": "0",
            "enabled": True,
        },
    )
    assert created.status_code == 200
    assert created.json()["camera"]["id"] == "CAM-77"

    updated = client.put(
        "/api/cameras/CAM-77",
        headers=headers,
        json={
            "name": "San thuong moi",
            "room": "Tang 3",
            "source": "1",
            "enabled": False,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["camera"]["enabled"] is False


def test_non_admin_cannot_modify_cameras(tmp_path, monkeypatch):
    from src import auth, camera_registry
    from src.auth import AuthConfig, AuthUser

    cfg = AuthConfig(
        admin=AuthUser(username="admin", password="nckh2025", role="admin", full_name="Admin"),
        users=(
            AuthUser(
                username="caregiver",
                password="pass123",
                role="caregiver",
                full_name="Caregiver",
            ),
        ),
    )
    monkeypatch.setattr(auth, "load_auth_config", lambda path=None: cfg)

    cameras_file = tmp_path / "cameras.yaml"
    monkeypatch.setattr(camera_registry, "DEFAULT_CAMERAS_PATH", cameras_file)

    login = client.post(
        "/api/auth/login",
        json={"username": "caregiver", "password": "pass123"},
    )
    assert login.status_code == 200
    assert login.json()["is_admin"] is False
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    assert client.get("/api/cameras", headers=headers).status_code == 200
    assert client.get("/api/cameras/suggest-id", headers=headers).status_code == 403

    body = {
        "id": "CAM-88",
        "name": "Phong ngu",
        "room": "Tang 1",
        "source": "0",
        "enabled": True,
    }
    assert client.post("/api/cameras", headers=headers, json=body).status_code == 403
    assert client.put("/api/cameras/CAM-88", headers=headers, json=body).status_code == 403
    assert client.delete("/api/cameras/CAM-88", headers=headers).status_code == 403
