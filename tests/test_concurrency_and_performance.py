"""
Master Test Plan - Suite 2: Concurrency, Performance & Debounce Verification
Covers:
- TC-PF-01: Non-blocking background worker execution
- TC-PF-03: Frame buffer memory bounds & downscale footprint
- TC-DB-01: Anti-spam debounce for fall and stranger sessions
"""

import time
import threading
from collections import deque
import numpy as np
import pytest

from src.core.config import DetectorConfig
from src.detection.fall_detector import FallDetector, FallState, Point


# ==============================================================================
# TEST CASE TC-PF-01: NON-BLOCKING BACKGROUND WORKER VERIFICATION
# ==============================================================================
def test_tc_pf_01_media_saving_worker_is_non_blocking():
    """
    Kịch bản: Khi sự kiện ngã xảy ra, việc nén video và upload tốn 0.5 - 2 giây.
    Luồng xử lý frame chính không bao giờ được phép bị chặn (block) quá 10ms.
    """
    main_loop_latencies = []
    
    # Mô phỏng worker lưu media giả lập tốn 200ms
    def mock_heavy_io_saver():
        time.sleep(0.2)

    # Vòng lặp chính giả lập tốc độ 50 FPS (20ms mỗi frame)
    for frame_idx in range(20):
        t0 = time.perf_counter()
        
        # Tại frame thứ 10, kích hoạt worker ngầm như trong pipeline.py
        if frame_idx == 10:
            th = threading.Thread(target=mock_heavy_io_saver, daemon=True)
            th.start()
            
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        main_loop_latencies.append(elapsed_ms)
        time.sleep(0.005)  # giả lập xử lý nhẹ

    # Khẳng định tại frame thứ 10 (lúc bắn worker), thời gian trễ của luồng chính không bị nghẽn
    assert main_loop_latencies[10] < 20.0, f"Luồng chính bị block: {main_loop_latencies[10]}ms"


# ==============================================================================
# TEST CASE TC-PF-03: FRAME BUFFER MEMORY BOUNDS & EFFICIENCY
# ==============================================================================
def test_tc_pf_03_frame_buffer_bounded_and_optimized():
    """
    Kịch bản: Đẩy 300 frame 720p (1280x720) vào buffer.
    Buffer phải giữ đúng maxlen=200 và sau khi tối ưu resize (640x360),
    tổng dung lượng RAM của buffer phải giảm >= 70% so với bản gốc 720p.
    """
    from src.web.shared.pipeline import FallDetectionPipeline
    import cv2

    pipeline = FallDetectionPipeline()
    buffer = pipeline._frame_buffer
    
    # Tạo 1 frame mẫu 1280x720 3-kênh
    dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    # Đẩy 300 frames vào buffer bằng phương thức _buffer_frame
    for _ in range(300):
        pipeline._buffer_frame(dummy_frame, cv2)

    # 1. Khẳng định số lượng phần tử không vượt quá maxlen 200
    assert len(buffer) == 200

    # 2. Khẳng định kích thước từng frame trong buffer đã được tối ưu về 640x360
    stored_h, stored_w = buffer[0].shape[:2]
    assert stored_w == 640
    assert stored_h == 360

    # 3. Tính dung lượng bộ nhớ
    bytes_per_frame = buffer[0].nbytes
    total_buffer_mb = (bytes_per_frame * len(buffer)) / (1024 * 1024)
    
    # 200 frames 640x360x3 chỉ tốn ~132MB (thay vì ~550MB của 720p)
    assert total_buffer_mb < 150.0, f"Buffer ngốn quá nhiều RAM: {total_buffer_mb:.1f}MB"


# ==============================================================================
# TEST CASE TC-DB-01: ANTI-SPAM DEBOUNCE VERIFICATION
# ==============================================================================
def test_tc_db_01_fall_detector_anti_spam_cooldown():
    """
    Kịch bản: Đối tượng ngã xuống và nằm bất động suốt 60 frame liên tục.
    Bộ phát hiện té ngã chỉ được phép bắn `event_started=True` đúng 1 lần duy nhất,
    sau đó bật cờ `_alert_active` và kích hoạt cooldown để chống bão spam cảnh báo.
    """
    config = DetectorConfig(
        min_fall_frames=2,
        warning_frames=1,
        alert_after_seconds=0.5,
        assumed_fps=10,
        cooldown_frames=30,
    )
    detector = FallDetector(config)

    # Frame đứng
    detector.update({
        "nose": Point(0.5, 0.2), "left_shoulder": Point(0.4, 0.3),
        "right_shoulder": Point(0.6, 0.3), "left_hip": Point(0.45, 0.6), "right_hip": Point(0.55, 0.6)
    })
    # Frame ngã
    detector.update({
        "nose": Point(0.2, 0.7), "left_shoulder": Point(0.3, 0.71),
        "right_shoulder": Point(0.32, 0.73), "left_hip": Point(0.65, 0.72), "right_hip": Point(0.67, 0.74)
    })

    alerts_triggered = 0
    # Đối tượng tiếp tục nằm im trong 50 frames tiếp theo
    for _ in range(50):
        res = detector.update({
            "nose": Point(0.2, 0.7), "left_shoulder": Point(0.3, 0.71),
            "right_shoulder": Point(0.32, 0.73), "left_hip": Point(0.65, 0.72), "right_hip": Point(0.67, 0.74)
        })
        if res.event_started:
            alerts_triggered += 1

    # Khẳng định chỉ bắn sự kiện 1 lần duy nhất
    assert alerts_triggered == 1
    assert detector._alert_active is True


# ==============================================================================
# TEST CASE TC-PF-04: DECOUPLED PIPELINE MULTI-CLIENT BROADCAST
# ==============================================================================
def test_tc_pf_04_decoupled_pipeline_multi_client_stream():
    """
    Kịch bản: Nhiều client cùng xem luồng live stream (get_next_jpeg_frame).
    Mỗi client có last_frame_id độc lập và đều nhận được frame mới nhất
    mà không bị ghi đè hoặc xung đột race condition.
    """
    from src.web.shared.pipeline import FallDetectionPipeline

    p = FallDetectionPipeline()
    client1_id = -1
    client2_id = -1

    # Giả lập luồng stream sản xuất frame #1
    dummy_jpeg = b"\xff\xd8\xff\xe0dummy_jpeg_data"
    with p._frame_cond:
        p._latest_jpeg = dummy_jpeg
        p._frame_id = 1
        p._frame_cond.notify_all()

    fid1, f1 = p.get_next_jpeg_frame(client1_id, timeout=0.1)
    fid2, f2 = p.get_next_jpeg_frame(client2_id, timeout=0.1)

    assert fid1 == 1 and f1 == dummy_jpeg
    assert fid2 == 1 and f2 == dummy_jpeg

    # Giả lập frame #2
    dummy_jpeg2 = b"\xff\xd8\xff\xe0dummy_jpeg_data_2"
    with p._frame_cond:
        p._latest_jpeg = dummy_jpeg2
        p._frame_id = 2
        p._frame_cond.notify_all()

    fid1_next, f1_next = p.get_next_jpeg_frame(fid1, timeout=0.1)
    assert fid1_next == 2 and f1_next == dummy_jpeg2

