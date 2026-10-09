"""
Test Suite: Telegram Notification Enhancements (FallGuard AI)
Covers:
- Configuration management (load_notif_config, save_telegram_config)
- HTML alert formatting (format_alert_html, HTML escaping, cloud links)
- Single-message photo/video sending with caption & parse_mode="HTML"
- Detailed error handling (HTTP 400, 401, 403, URLError timeout)
- Service layer (get_telegram_config, update_telegram_config, connect_telegram, test_telegram)
- FastAPI admin router endpoints (GET /api/telegram/config, PUT /api/telegram/config, POST /api/telegram/connect, POST /api/telegram/test)
"""

import json
import io
import os
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import src.web.shared.notifications as notif
from src.web.shared.notifications import (
    load_notif_config,
    save_telegram_config,
    format_alert_html,
    send_telegram_alert,
    send_all_alerts,
)
import src.web.admin.service as admin_service
from src.web.server import app
from src.web.shared.router import require_user


@pytest.fixture
def temp_config_file(tmp_path, monkeypatch):
    """Fixture cung cấp file cấu hình notifications.json tạm thời cho từng test."""
    cfg_file = tmp_path / "configs" / "notifications.json"
    monkeypatch.setattr(notif, "CONFIG_PATH", cfg_file)
    monkeypatch.setattr(admin_service, "CONFIG_PATH", cfg_file)
    return cfg_file


@pytest.fixture
def auth_client():
    """Client test FastAPI với bypass xác thực người dùng."""
    app.dependency_overrides[require_user] = lambda: "admin@nckh.vn"
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# ==============================================================================
# 1. KIỂM THỬ ĐỌC VÀ LƯU CẤU HÌNH (CONFIG MANAGEMENT)
# ==============================================================================

def test_load_notif_config_creates_defaults_when_missing(temp_config_file):
    assert not temp_config_file.exists()
    cfg = load_notif_config()
    assert temp_config_file.exists()
    assert "telegram" in cfg
    assert cfg["telegram"]["enabled"] is False
    assert cfg["telegram"]["bot_token"] == "YOUR_TELEGRAM_BOT_TOKEN"
    assert cfg["telegram"]["chat_id"] == "YOUR_TELEGRAM_CHAT_ID"


def test_load_notif_config_handles_corrupt_file_gracefully(temp_config_file):
    temp_config_file.parent.mkdir(parents=True, exist_ok=True)
    temp_config_file.write_text("{invalid json corrupt content...", encoding="utf-8")
    cfg = load_notif_config()
    assert "telegram" in cfg
    assert cfg["telegram"]["enabled"] is False


def test_save_telegram_config_persists_and_preserves_other_sections(temp_config_file):
    initial = {
        "telegram": {"enabled": False, "bot_token": "old", "chat_id": "old"},
        "email": {"enabled": True, "sender_email": "hello@example.com"}
    }
    temp_config_file.parent.mkdir(parents=True, exist_ok=True)
    temp_config_file.write_text(json.dumps(initial), encoding="utf-8")

    updated = save_telegram_config(
        bot_token="  123456:ABC-Token  ",
        chat_id="  -100987654321  ",
        enabled=True
    )

    assert updated["bot_token"] == "123456:ABC-Token"
    assert updated["chat_id"] == "-100987654321"
    assert updated["enabled"] is True

    # Kiểm tra file trên đĩa
    saved_on_disk = json.loads(temp_config_file.read_text(encoding="utf-8"))
    assert saved_on_disk["telegram"]["bot_token"] == "123456:ABC-Token"
    assert saved_on_disk["telegram"]["chat_id"] == "-100987654321"
    assert saved_on_disk["telegram"]["enabled"] is True
    # Nhánh email không bị mất
    assert saved_on_disk["email"]["sender_email"] == "hello@example.com"


# ==============================================================================
# 2. KIỂM THỬ ĐỊNH DẠNG TIN NHẮN HTML (FORMATTING & SECURITY ESCAPING)
# ==============================================================================

def test_format_alert_html_fall_alert():
    msg = format_alert_html(
        alert_type="fall",
        alert_id="AL-20261001-001",
        camera_name="Phòng Khách",
        camera_id="CAM-01",
        person_name="Ông Bảo",
        timestamp="01/10/2026 09:30:00"
    )
    assert "🚨 <b>CẢNH BÁO TÉ NGÃ KHẨN CẤP!</b>" in msg
    assert "📍 <b>Camera:</b> Phòng Khách (CAM-01)" in msg
    assert "👤 <b>Đối tượng:</b> Ông Bảo" in msg
    assert "⏰ <b>Thời gian:</b> 01/10/2026 09:30:00" in msg
    assert "⚠️ <b>Mã sự cố:</b> <code>AL-20261001-001</code>" in msg
    assert "🔔 <i>Vui lòng kiểm tra người thân ngay lập tức!</i>" in msg


def test_format_alert_html_stranger_alert():
    msg = format_alert_html(
        alert_type="stranger",
        alert_id="STRANGER-20261001-999",
        camera_name="Cổng Trước",
        camera_id="CAM-FRONT",
        person_name="Người chưa đăng ký",
        timestamp="01/10/2026 09:45:00"
    )
    assert "⚠️ <b>CẢNH BÁO NGƯỜI LẠ XÂM NHẬP</b>" in msg
    assert "📍 <b>Camera:</b> Cổng Trước (CAM-FRONT)" in msg
    assert "👤 <b>Nhận diện:</b> Người chưa đăng ký" in msg
    assert "<code>STRANGER-20261001-999</code>" in msg
    assert "📸 <i>Hình ảnh đối tượng đính kèm bên dưới</i>" in msg


def test_format_alert_html_escapes_unsafe_input():
    msg = format_alert_html(
        alert_type="fall",
        alert_id="AL-<123>&",
        camera_name="Camera <Living & Dining>",
        camera_id="CAM <01>",
        person_name="User <Bảo> & 'Guest'",
        timestamp="01/10/2026 <09:00>"
    )
    assert "<script>" not in msg
    assert "&lt;Living &amp; Dining&gt;" in msg
    assert "&lt;Bảo&gt;" in msg
    assert "&lt;123&gt;&amp;" in msg


def test_format_alert_html_includes_cloud_links():
    msg = format_alert_html(
        alert_type="fall",
        alert_id="AL-001",
        cloud_img_url="https://res.cloudinary.com/demo/image/upload/sample.jpg",
        cloud_video_url="https://res.cloudinary.com/demo/video/upload/sample.mp4"
    )
    assert "☁️ <b>Cloud Backup:</b>" in msg
    assert '• <a href="https://res.cloudinary.com/demo/image/upload/sample.jpg">Ảnh sự cố</a>' in msg
    assert '• <a href="https://res.cloudinary.com/demo/video/upload/sample.mp4">Video clip</a>' in msg


# ==============================================================================
# 3. KIỂM THỬ HÀM GỬI TELEGRAM (MOCK HTTP & MULTIPART FORM)
# ==============================================================================

def test_send_telegram_alert_aborts_when_disabled(temp_config_file):
    save_telegram_config("123:TOKEN", "999", enabled=False)
    with patch("urllib.request.urlopen") as mock_url:
        res = send_telegram_alert("Hello")
        assert res["ok"] is False
        assert "bị tắt" in res["detail"]
        mock_url.assert_not_called()


def test_send_telegram_alert_aborts_when_unconfigured(temp_config_file):
    save_telegram_config("YOUR_TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_CHAT_ID", enabled=True)
    with patch("urllib.request.urlopen") as mock_url:
        res = send_telegram_alert("Hello")
        assert res["ok"] is False
        assert "chưa được cấu hình" in res["detail"]
        mock_url.assert_not_called()


def test_send_telegram_alert_text_only_uses_send_message(temp_config_file):
    save_telegram_config("123456:BOT_TOKEN", "987654", enabled=True)

    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps({"ok": True, "result": {"message_id": 101}}).encode("utf-8")
    fake_response.__enter__.return_value = fake_response

    with patch("urllib.request.urlopen", return_value=fake_response) as mock_url:
        res = send_telegram_alert("🚨 <b>Cảnh báo</b>")
        assert res["ok"] is True
        mock_url.assert_called_once()
        req = mock_url.call_args[0][0]
        assert "sendMessage" in req.full_url
        assert "chat_id=987654" in req.data.decode("utf-8")
        assert "parse_mode=HTML" in req.data.decode("utf-8")


def test_send_telegram_alert_photo_with_single_message_caption(tmp_path, temp_config_file):
    save_telegram_config("123456:BOT_TOKEN", "987654", enabled=True)

    # Tạo file ảnh giả lập
    fake_img = tmp_path / "snapshot.jpg"
    fake_img.write_bytes(b"\xff\xd8\xff\xe0FAKE_JPEG_CONTENT")

    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps({"ok": True, "result": {"message_id": 102}}).encode("utf-8")
    fake_response.__enter__.return_value = fake_response

    with patch("urllib.request.urlopen", return_value=fake_response) as mock_url:
        res = send_telegram_alert("🚨 <b>Cảnh báo té ngã</b>", image_path=str(fake_img))
        assert res["ok"] is True
        mock_url.assert_called_once()
        req = mock_url.call_args[0][0]
        assert "sendPhoto" in req.full_url
        # Kiểm tra multipart data có chứa photo, caption và parse_mode="HTML"
        raw_body = req.data.decode("utf-8", errors="ignore")
        assert 'name="caption"' in raw_body
        assert "🚨 <b>Cảnh báo té ngã</b>" in raw_body
        assert 'name="parse_mode"' in raw_body
        assert "HTML" in raw_body
        assert 'name="photo"' in raw_body


def test_send_telegram_alert_video_with_single_message_caption(tmp_path, temp_config_file):
    save_telegram_config("123456:BOT_TOKEN", "987654", enabled=True)

    fake_video = tmp_path / "clip.mp4"
    fake_video.write_bytes(b"FAKE_MP4_CONTENT_1234567890")

    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps({"ok": True, "result": {"message_id": 103}}).encode("utf-8")
    fake_response.__enter__.return_value = fake_response

    with patch("urllib.request.urlopen", return_value=fake_response) as mock_url:
        res = send_telegram_alert("🚨 <b>Cảnh báo video</b>", video_path=str(fake_video))
        assert res["ok"] is True
        mock_url.assert_called_once()
        req = mock_url.call_args[0][0]
        assert "sendVideo" in req.full_url
        raw_body = req.data.decode("utf-8", errors="ignore")
        assert 'name="caption"' in raw_body
        assert 'name="video"' in raw_body


def test_send_telegram_alert_media_fail_falls_back_to_text(tmp_path, temp_config_file):
    save_telegram_config("123456:BOT_TOKEN", "987654", enabled=True)

    fake_img = tmp_path / "snapshot.jpg"
    fake_img.write_bytes(b"JPEG_BYTES")

    text_resp = MagicMock()
    text_resp.read.return_value = json.dumps({"ok": True, "result": {"message_id": 104}}).encode("utf-8")
    text_resp.__enter__.return_value = text_resp

    def mock_urlopen(req, timeout=None):
        if "sendPhoto" in req.full_url:
            raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, io.BytesIO(b'{"description": "Photo upload failed"}'))
        return text_resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen) as mock_url:
        res = send_telegram_alert("Thông báo dự phòng", image_path=str(fake_img))
        assert res["ok"] is True
        # Gửi photo trước -> fail -> gửi sendMessage dự phòng
        assert mock_url.call_count == 2
        last_req = mock_url.call_args_list[1][0][0]
        assert "sendMessage" in last_req.full_url


def test_send_telegram_alert_extracts_detailed_api_errors(temp_config_file):
    save_telegram_config("123456:BOT_TOKEN", "987654", enabled=True)

    # 1. Test lỗi 400 Chat not found
    err_body_400 = json.dumps({"ok": False, "error_code": 400, "description": "Bad Request: chat not found"}).encode("utf-8")
    err_400 = urllib.error.HTTPError("http://tg", 400, "Bad Request", {}, io.BytesIO(err_body_400))
    with patch("urllib.request.urlopen", side_effect=err_400):
        res = send_telegram_alert("Test 400")
        assert res["ok"] is False
        assert "Bad Request: chat not found" in res["detail"]

    # 2. Test lỗi 401 Unauthorized
    err_body_401 = json.dumps({"ok": False, "error_code": 401, "description": "Unauthorized"}).encode("utf-8")
    err_401 = urllib.error.HTTPError("http://tg", 401, "Unauthorized", {}, io.BytesIO(err_body_401))
    with patch("urllib.request.urlopen", side_effect=err_401):
        res = send_telegram_alert("Test 401")
        assert res["ok"] is False
        assert "Unauthorized" in res["detail"]


def test_send_telegram_alert_handles_url_timeout_error(temp_config_file):
    save_telegram_config("123456:BOT_TOKEN", "987654", enabled=True)

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection timed out")):
        res = send_telegram_alert("Test Timeout")
        assert res["ok"] is False
        assert "Lỗi kết nối máy chủ Telegram" in res["detail"]


def test_send_all_alerts_integrates_cleanly(temp_config_file):
    save_telegram_config("123456:BOT_TOKEN", "987654", enabled=True)

    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps({"ok": True, "result": {"message_id": 105}}).encode("utf-8")
    fake_response.__enter__.return_value = fake_response

    with patch("urllib.request.urlopen", return_value=fake_response) as mock_url:
        res = send_all_alerts(
            alert_id="AL-TEST-001",
            alert_type="fall",
            camera_name="Sân Thượng",
            camera_id="CAM-ROOF",
            person_name="Bà Lan"
        )
        assert res["ok"] is True
        mock_url.assert_called_once()
        req = mock_url.call_args[0][0]
        data = req.data.decode("utf-8")
        assert "S%C3%A2n+Th%C6%B0%E1%BB%A3ng" in data or "Sân Thượng" in urllib.parse.unquote(data)


# ==============================================================================
# 4. KIỂM THỬ SERVICE LAYER & FASTAPI REST ENDPOINTS
# ==============================================================================

def test_api_get_and_put_telegram_config(auth_client, temp_config_file):
    # Ban đầu
    save_telegram_config("TOKEN-1", "CHAT-1", enabled=False)

    # 1. GET /api/telegram/config
    get_res = auth_client.get("/api/telegram/config")
    assert get_res.status_code == 200
    cfg = get_res.json()
    assert cfg["bot_token"] == "TOKEN-1"
    assert cfg["chat_id"] == "CHAT-1"
    assert cfg["enabled"] is False

    # 2. PUT /api/telegram/config
    put_res = auth_client.put("/api/telegram/config", json={
        "bot_token": "TOKEN-NEW-2",
        "chat_id": "-5177087463",
        "enabled": True
    })
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["ok"] is True
    assert updated["bot_token"] == "TOKEN-NEW-2"
    assert updated["chat_id"] == "-5177087463"
    assert updated["enabled"] is True

    # 3. GET lại để kiểm tra tính bền vững
    get_res_2 = auth_client.get("/api/telegram/config")
    assert get_res_2.json()["chat_id"] == "-5177087463"
    assert get_res_2.json()["enabled"] is True


def test_api_telegram_connect_auto_detects_chat_id(auth_client, temp_config_file):
    save_telegram_config("8169554639:AAGY0eo5ZC6Nd6-b0p7PPHxyZxOOLdQdqjk", "YOUR_TELEGRAM_CHAT_ID", enabled=False)

    fake_updates = {
        "ok": True,
        "result": [
            {
                "update_id": 1,
                "message": {
                    "message_id": 50,
                    "chat": {"id": -5177087463, "title": "Gia đình Bác An", "type": "group"},
                    "text": "Hello bot"
                }
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(fake_updates).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = auth_client.post("/api/telegram/connect")
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert data["chat_id"] == "-5177087463"
        assert data["username"] == "Gia đình Bác An"

    # Đảm bảo cấu hình đã được cập nhật tự động vào file
    on_disk = json.loads(temp_config_file.read_text(encoding="utf-8"))
    assert on_disk["telegram"]["chat_id"] == "-5177087463"
    assert on_disk["telegram"]["enabled"] is True


def test_api_telegram_connect_no_updates_returns_helpful_guidance(auth_client, temp_config_file):
    save_telegram_config("123456:VALID_TOKEN", "CHAT_ID", enabled=False)

    fake_updates = {"ok": True, "result": []}
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(fake_updates).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = auth_client.post("/api/telegram/connect")
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is False
        assert "Chưa tìm thấy tin nhắn nào" in data["detail"]


def test_api_telegram_connect_without_token_returns_error(auth_client, temp_config_file):
    save_telegram_config("YOUR_TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_CHAT_ID", enabled=False)
    res = auth_client.post("/api/telegram/connect")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is False
    assert "Vui lòng nhập Bot Token" in data["detail"]


def test_api_telegram_test_endpoint_success_and_validation(auth_client, temp_config_file):
    # 1. Khi chưa bật
    save_telegram_config("123:TOKEN", "999", enabled=False)
    res_disabled = auth_client.post("/api/telegram/test")
    assert res_disabled.status_code == 400
    assert "bật nút kích hoạt" in res_disabled.json()["detail"]

    # 2. Khi chưa có token
    save_telegram_config("YOUR_TELEGRAM_BOT_TOKEN", "999", enabled=True)
    res_no_tok = auth_client.post("/api/telegram/test")
    assert res_no_tok.status_code == 400

    # 3. Khi đã bật và cấu hình đầy đủ -> test thành công
    save_telegram_config("123:TOKEN", "999", enabled=True)
    fake_resp = MagicMock()
    fake_resp.read.return_value = json.dumps({"ok": True, "result": {"message_id": 99}}).encode("utf-8")
    fake_resp.__enter__.return_value = fake_resp

    with patch("urllib.request.urlopen", return_value=fake_resp):
        res_ok = auth_client.post("/api/telegram/test")
        assert res_ok.status_code == 200
        assert res_ok.json()["ok"] is True
        assert "Đã gửi tin nhắn cảnh báo thử nghiệm" in res_ok.json()["detail"]


def test_api_notifications_test_channel_telegram(auth_client, temp_config_file):
    save_telegram_config("123:TOKEN", "999", enabled=True)
    fake_resp = MagicMock()
    fake_resp.read.return_value = json.dumps({"ok": True, "result": {"message_id": 100}}).encode("utf-8")
    fake_resp.__enter__.return_value = fake_resp

    with patch("urllib.request.urlopen", return_value=fake_resp):
        res = auth_client.post("/api/notifications/test", json={"channel": "telegram"})
        assert res.status_code == 200
        assert res.json()["ok"] is True
