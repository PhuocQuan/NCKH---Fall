"""
File: tests/test_multi_camera.py
Chức năng: Kiểm thử tự động tính năng Quản lý & Giám sát Đa Camera RTSP:
- Module MultiCameraManager: Đa luồng, chuyển đổi camera AI chính, decode on-demand.
- Kiểm tra kết nối RTSP & Đo độ trễ (Ping Latency), phân giải thực, FPS, thumbnail.
- Các API endpoints: GET /api/cameras/status, POST /api/cameras/{id}/test,
  POST /api/cameras/test-connection, POST /api/cameras/{id}/set-primary,
  GET /api/cameras/{id}/stream.mjpg, GET /api/cameras/{id}/snapshot.
"""

import socket
import time
from unittest.mock import MagicMock, patch

import jwt
import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.camera.multi_camera_manager import MultiCameraManager, multi_camera_manager
from src.web.server import app
from src.web.shared.auth import JWT_ALGORITHM, JWT_SECRET_KEY


def get_test_token() -> str:
    payload = {"sub": "admin@nckh.vn", "exp": int(time.time() + 3600)}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def test_multi_camera_manager_singleton():
    mgr1 = MultiCameraManager()
    mgr2 = MultiCameraManager()
    assert mgr1 is mgr2
    assert mgr1 is multi_camera_manager


def test_get_and_set_primary_camera():
    fake_cams = [
        {"id": "CAM-001", "name": "Camera Phòng Khách", "rtsp": "rtsp://192.168.1.18:554/live"},
        {"id": "CAM-002", "name": "Camera Cầu Thang", "rtsp": "rtsp://192.168.1.19:554/live"}
    ]
    with patch("src.web.admin.repository.get_all_cameras_db", return_value=fake_cams):
        with patch("src.web.shared.pipeline.pipeline.start") as mock_pipeline_start:
            with patch("src.web.shared.db.get_db_client") as mock_db:
                res = multi_camera_manager.set_primary_camera("CAM-002")
                assert res["ok"] is True
                assert res["camera_id"] == "CAM-002"
                assert res["name"] == "Camera Cầu Thang"
                assert multi_camera_manager.primary_camera_id == "CAM-002"
                mock_pipeline_start.assert_called_once_with("rtsp://192.168.1.19:554/live", camera_id="CAM-002")


def test_get_camera_jpeg_primary():
    fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    multi_camera_manager.primary_camera_id = "CAM-001"
    with patch("src.web.shared.pipeline.pipeline.get_jpeg_frame", return_value=fake_jpeg):
        with patch("src.web.shared.pipeline.pipeline.is_running", return_value=True):
            frame = multi_camera_manager.get_camera_jpeg("CAM-001")
            assert frame == fake_jpeg


def test_get_camera_jpeg_secondary_success():
    fake_frame = np.zeros((360, 640, 3), dtype=np.uint8)
    mock_vs = MagicMock()
    mock_vs.read.return_value = (True, fake_frame)

    multi_camera_manager.primary_camera_id = "CAM-001"
    with patch.object(multi_camera_manager, "_get_secondary_source", return_value=mock_vs):
        frame = multi_camera_manager.get_camera_jpeg("CAM-002")
        assert isinstance(frame, bytes)
        assert len(frame) > 0


def test_get_camera_jpeg_secondary_offline():
    multi_camera_manager.primary_camera_id = "CAM-001"
    with patch.object(multi_camera_manager, "_get_secondary_source", return_value=None):
        frame = multi_camera_manager.get_camera_jpeg("CAM-999")
        assert isinstance(frame, bytes)
        assert len(frame) > 0


def test_test_connection_webcam():
    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: 640.0 if prop == 3 else 480.0 if prop == 4 else 30.0
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, fake_frame)
        mock_cap_cls.return_value = mock_cap

        res = multi_camera_manager.test_connection("0")
        assert res["ok"] is True
        assert res["connected"] is True
        assert res["resolution"] == "640x480"
        assert res["fps"] == 30.0
        assert "Webcam" in res["vendor"]
        assert res["thumbnail"].startswith("data:image/jpeg;base64,")


def test_test_connection_rtsp_success():
    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        mock_sock_cls.return_value.__enter__.return_value = mock_sock

        with patch("cv2.VideoCapture") as mock_cap_cls:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.get.side_effect = lambda prop: 1920.0 if prop == 3 else 1080.0 if prop == 4 else 25.0
            fake_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
            mock_cap.read.return_value = (True, fake_frame)
            mock_cap_cls.return_value = mock_cap

            res = multi_camera_manager.test_connection("rtsp://admin:pass@192.168.1.50:554/live")
            assert res["ok"] is True
            assert res["connected"] is True
            assert res["resolution"] == "1920x1080"
            assert res["fps"] == 25.0
            assert "latency_ms" in res
            assert res["thumbnail"].startswith("data:image/jpeg;base64,")


def test_test_connection_rtsp_socket_failed():
    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 111  # Connection refused
        mock_sock_cls.return_value.__enter__.return_value = mock_sock

        res = multi_camera_manager.test_connection("rtsp://admin:pass@192.168.1.99:554/live")
        assert res["ok"] is False
        assert res["connected"] is False
        assert "Không thể kết nối" in res["error"]


def test_get_all_cameras_status():
    fake_cams = [
        {"id": "CAM-001", "name": "Cam 1", "ip": "192.168.1.18", "rtsp": "rtsp://...", "status": "online", "fps": 25},
        {"id": "CAM-002", "name": "Cam 2", "ip": "192.168.1.19", "rtsp": "rtsp://...", "status": "offline", "fps": 30}
    ]
    multi_camera_manager.primary_camera_id = "CAM-001"
    with patch("src.web.admin.repository.get_all_cameras_db", return_value=fake_cams):
        with patch("src.web.shared.pipeline.pipeline.is_running", return_value=True):
            statuses = multi_camera_manager.get_all_cameras_status()
            assert len(statuses) == 2
            c1 = next(c for c in statuses if c["id"] == "CAM-001")
            assert c1["is_primary"] is True
            assert c1["status"] == "online"
            c2 = next(c for c in statuses if c["id"] == "CAM-002")
            assert c2["is_primary"] is False


def test_api_get_cameras_status():
    client = TestClient(app)
    token = get_test_token()
    headers = {"Authorization": f"Bearer {token}"}

    fake_statuses = [
        {"id": "CAM-001", "name": "Camera 1", "status": "online", "is_primary": True, "fps": 25, "resolution": "1920x1080"}
    ]
    with patch("src.web.admin.service.get_cameras_status", return_value=fake_statuses):
        resp = client.get("/api/cameras/status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "CAM-001"
        assert data[0]["is_primary"] is True


def test_api_post_camera_test():
    client = TestClient(app)
    token = get_test_token()
    headers = {"Authorization": f"Bearer {token}"}

    fake_res = {
        "ok": True,
        "connected": True,
        "latency_ms": 15.4,
        "resolution": "1920x1080",
        "fps": 25.0,
        "camera_id": "CAM-001",
        "name": "Cam 1",
        "thumbnail": "data:image/jpeg;base64,123",
        "message": "Kết nối thành công"
    }
    with patch("src.web.admin.service.test_camera", return_value=fake_res):
        resp = client.post("/api/cameras/CAM-001/test", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["latency_ms"] == 15.4
        assert data["resolution"] == "1920x1080"


def test_api_post_camera_test_connection_arbitrary():
    client = TestClient(app)
    token = get_test_token()
    headers = {"Authorization": f"Bearer {token}"}

    fake_res = {
        "ok": True,
        "connected": True,
        "latency_ms": 12.0,
        "resolution": "1280x720",
        "fps": 30.0,
        "thumbnail": "data:image/jpeg;base64,abc",
        "message": "Thành công"
    }
    with patch("src.web.admin.service.test_camera_connection_arbitrary", return_value=fake_res):
        resp = client.post(
            "/api/cameras/test-connection",
            headers=headers,
            json={"rtsp": "rtsp://192.168.1.88/live"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["resolution"] == "1280x720"


def test_api_post_set_primary_camera():
    client = TestClient(app)
    token = get_test_token()
    headers = {"Authorization": f"Bearer {token}"}

    fake_res = {
        "ok": True,
        "camera_id": "CAM-002",
        "name": "Camera Cầu Thang",
        "is_primary": True,
        "message": "Đã chuyển camera chính"
    }
    with patch("src.web.admin.service.set_primary_camera", return_value=fake_res):
        resp = client.post("/api/cameras/CAM-002/set-primary", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["camera_id"] == "CAM-002"


def test_api_camera_snapshot_by_id():
    client = TestClient(app)
    token = get_test_token()
    headers = {"Authorization": f"Bearer {token}"}

    fake_jpeg = b"\xff\xd8\xff\xe0fakejpegbytes"
    with patch.object(multi_camera_manager, "get_camera_jpeg", return_value=fake_jpeg):
        resp = client.get("/api/cameras/CAM-001/snapshot", headers=headers)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/jpeg"
        assert resp.content == fake_jpeg
