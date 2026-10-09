"""
Master Test Plan - Suite 3: Fault Tolerance, Security & Resilience
Covers:
- TC-FT-01: Camera disconnect & auto-recovery mechanism (Escaping MockVideoCapture trap)
- TC-FT-03: Offline fallback logging when database is unreachable
- TC-SEC-01: PBKDF2-SHA256 password hashing & backward compatibility verification
"""

import os
from pathlib import Path
import pytest
import numpy as np

from src.camera.video_source import VideoSource, MockVideoCapture
from src.web.shared.auth import hash_password, verify_password, login, VALID_USERS
from src.web.shared.db import log_action, OFFLINE_LOG_PATH


# ==============================================================================
# TEST CASE TC-FT-01: AUTO-RECOVERY FROM MOCKVIDEOCAPTURE TRAP
# ==============================================================================
def test_tc_ft_01_camera_auto_reconnect_from_mock():
    """
    Kịch bản: Nguồn camera ban đầu không mở được, VideoSource dùng MockVideoCapture.
    Khi nguồn camera thật trở lại hoạt động, VideoSource phải tự động thoát khỏi Mock
    và kết nối lại với camera thật mà không cần khởi động lại Server.
    """
    # Khởi tạo VideoSource với nguồn giả lập
    vs = VideoSource(source="rtsp://non-existent-camera:554/stream")
    assert isinstance(vs.capture, MockVideoCapture)

    # Đọc frame giả lập
    ok, frame = vs.read()
    assert ok is True
    assert frame is not None
    assert frame.shape[0] == 480

    # Giả lập camera vật lý đã online trở lại bằng cách mock _open_real_only
    class MockRealCapture:
        def __init__(self):
            self.opened = True
        def isOpened(self):
            return self.opened
        def read(self):
            # Frame camera thật kích thước 720p
            return True, np.ones((720, 1280, 3), dtype=np.uint8) * 200
        def release(self):
            self.opened = False
        def get(self, prop):
            return 30.0

    vs._open_real_only = lambda: MockRealCapture()
    
    # Ép thời gian reconnect qua ngưỡng 5s
    vs._last_reconnect_time = 0.0

    # Lần gọi read() tiếp theo phải phát hiện camera thật và hoán đổi đối tượng capture
    ok2, frame2 = vs.read()
    assert ok2 is True
    assert not isinstance(vs.capture, MockVideoCapture)
    assert vs.capture.isOpened()
    
    vs.release()


# ==============================================================================
# TEST CASE TC-FT-03: OFFLINE LOGGING FALLBACK
# ==============================================================================
def test_tc_ft_03_offline_logging_fallback_when_db_down(tmp_path, monkeypatch):
    """
    Kịch bản: Mạng Internet bị ngắt, không thể kết nối tới Turso Cloud DB.
    Hàm log_action phải tự động ghi vào file offline fallback mà không làm crash server.
    """
    # Trỏ file log offline sang thư mục test tạm thời
    test_offline_file = tmp_path / "system_logs_offline.csv"
    monkeypatch.setattr("src.web.shared.db.OFFLINE_LOG_PATH", test_offline_file)

    # Giả lập hàm get_db_client ném ngoại lệ mất mạng (Network Timeout)
    def broken_db_client():
        raise ConnectionError("Mạng Internet bị ngắt, không thể tới Turso!")

    monkeypatch.setattr("src.web.shared.db.get_db_client", broken_db_client)

    # Gọi log_action khi mất mạng
    log_action("FALL_ALERT", "AI_CORE", "Phát hiện té ngã tại phòng khách (Mất mạng)")

    # Khẳng định file log offline đã được tạo và chứa nội dung cảnh báo
    assert test_offline_file.exists()
    content = test_offline_file.read_text(encoding="utf-8")
    assert "FALL_ALERT" in content
    assert "Phát hiện té ngã tại phòng khách" in content


# ==============================================================================
# TEST CASE TC-SEC-01: BẢO MẬT MẬT KHẨU & TƯƠNG THÍCH NGƯỢC
# ==============================================================================
def test_tc_sec_01_password_hashing_and_backward_compatibility():
    """
    Kiểm tra:
    1. Hàm hash_password tạo ra chuỗi hash an toàn chuẩn PBKDF2-SHA256 với salt ngẫu nhiên.
    2. Hai lần hash cùng 1 mật khẩu phải ra 2 chuỗi khác nhau (do salt khác nhau).
    3. Hàm verify_password xác thực chính xác mật khẩu đúng và từ chối mật khẩu sai.
    4. Hỗ trợ tương thích ngược (backward compatibility) với mật khẩu plaintext cũ.
    """
    plain = "MySecretPass2026!"
    
    # 1. Hash mật khẩu
    h1 = hash_password(plain)
    h2 = hash_password(plain)
    
    assert h1.startswith("$pbkdf2-sha256$100000$")
    assert h1 != h2, "Hai lần hash phải ra chuỗi khác nhau do salt ngẫu nhiên"

    # 2. Xác thực với hash
    assert verify_password(plain, h1) is True
    assert verify_password("WrongPassword", h1) is False

    # 3. Tương thích ngược với plaintext cũ
    old_plaintext = "nckh2025"
    assert verify_password("nckh2025", old_plaintext) is True
    assert verify_password("wrong", old_plaintext) is False
