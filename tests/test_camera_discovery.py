"""
Unit and Integration Tests for Camera Auto-Discovery and Auto-Binding.
"""

import socket
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import time
import jwt

from src.camera.camera_discovery import (
    build_imou_rtsp,
    discover_all_cameras,
    get_local_ip,
    get_subnet_prefix,
    probe_rtsp_socket,
    scan_host,
)
from src.web.server import app
from src.web.shared.auth import JWT_SECRET_KEY, JWT_ALGORITHM


def get_test_token() -> str:
    payload = {"sub": "admin@nckh.vn", "exp": int(time.time() + 3600)}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def test_get_local_ip_and_prefix():
    ip = get_local_ip()
    assert isinstance(ip, str)
    assert len(ip.split(".")) == 4

    prefix = get_subnet_prefix("192.168.1.15")
    assert prefix == "192.168.1."

    prefix_custom = get_subnet_prefix("10.0.0.50")
    assert prefix_custom == "10.0.0."


def test_build_imou_rtsp():
    rtsp = build_imou_rtsp("192.168.1.55", "SecretCode123")
    assert rtsp == "rtsp://admin:SecretCode123@192.168.1.55:554/cam/realmonitor?channel=1&subtype=1"


def test_probe_rtsp_socket_mocked():
    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        mock_sock.recv.return_value = b"RTSP/1.0 200 OK\r\nServer: Dahua-Stream/2.0\r\n\r\n"
        mock_sock_cls.return_value = mock_sock

        is_rtsp, server_desc = probe_rtsp_socket("192.168.1.20", 554)
        assert is_rtsp is True
        assert "Dahua" in server_desc


def test_scan_host_detected():
    with patch("src.camera.camera_discovery.probe_rtsp_socket", return_value=(True, "Dahua RTSP")):
        with patch("src.camera.camera_discovery.probe_dahua_rpc", return_value=True):
            res = scan_host("192.168.1.20")
            assert res is not None
            assert res["ip"] == "192.168.1.20"
            assert "Imou / Dahua" in res["vendor"]
            assert res["port"] == 554


def test_api_cameras_discover():
    client = TestClient(app)
    token = get_test_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Mock discover_all_cameras to avoid slow physical network probe during unit test
    fake_cameras = [
        {
            "ip": "192.168.1.25",
            "port": 554,
            "vendor": "Imou / Dahua",
            "server_desc": "Dahua RTSP",
            "latency_ms": 12.0,
            "detected_via": "fast_subnet_scan",
            "suggested_imou_rtsp": "rtsp://admin:L223Xr!w@192.168.1.25:554/cam/realmonitor?channel=1&subtype=1",
            "suggested_generic_rtsp": "rtsp://192.168.1.25:554/live",
            "local_subnet": "192.168.1.0/24",
            "host_local_ip": "192.168.1.8"
        }
    ]

    with patch("src.camera.camera_discovery.discover_all_cameras", return_value=fake_cameras):
        resp = client.get("/api/cameras/discover", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert len(data["cameras"]) == 1
        assert data["cameras"][0]["ip"] == "192.168.1.25"


def test_api_cameras_auto_bind():
    client = TestClient(app)
    token = get_test_token()
    headers = {"Authorization": f"Bearer {token}"}

    with patch("src.web.admin.repository.update_camera_network_db", return_value="CAM-011"):
        with patch("src.web.shared.pipeline.pipeline.start") as mock_pipeline_start:
            resp = client.post(
                "/api/cameras/auto-bind",
                headers=headers,
                json={"camera_id": "CAM-011", "new_ip": "192.168.1.25", "safety_code": "L223Xr!w"}
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is True
            assert data["new_ip"] == "192.168.1.25"
            assert "192.168.1.25" in data["new_rtsp"]
