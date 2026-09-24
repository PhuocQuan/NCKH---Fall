"""
Unit tests for Stranger Detection and Fall Detection stability fixes:
- Sitting at desk / leaning forward must not trigger fall alerts.
- Low visibility hips (close-up camera) must not hallucinate falls.
- Real falls with dynamic transitions still trigger alerts reliably.
- Known face tracking with spatial centroid distance resists momentary head turns.
- Pipeline suppresses stranger alerts when face is near recent known family track.
"""

import time
import pytest
from src.core.config import DetectorConfig, FaceConfig
from src.detection.fall_detector import FallDetector, FallState, Point
from src.face.face_recognizer import FaceRecognizer, PersonType, RecognizedFace, _compute_box_center_dist


def test_sitting_at_desk_no_false_fall():
    """Người ngồi làm việc ở bàn, thân nghiêng nhẹ (40-52 độ) -> Không bao giờ báo ngã."""
    detector = FallDetector(
        DetectorConfig(
            torso_fall_angle_deg=58.0,
            alert_after_seconds=2.5,
            alert_on_long_lying_without_fall=False,
            assumed_fps=15,
        )
    )

    # Thân hơi nghiêng về phía bàn làm việc (vai x=0.48, y=0.40; hông x=0.52, y=0.68)
    sitting_pose = {
        "nose": Point(0.46, 0.28, 0.95),
        "left_shoulder": Point(0.42, 0.40, 0.95),
        "right_shoulder": Point(0.54, 0.40, 0.95),
        "left_hip": Point(0.46, 0.68, 0.95),
        "right_hip": Point(0.58, 0.68, 0.95),
    }

    for _ in range(60):  # 4 giây liên tục
        res = detector.update(sitting_pose)
        assert res.state == FallState.NORMAL
        assert res.abnormal_frames == 0
        assert not res.event_started


def test_low_visibility_hips_no_phantom_fall():
    """Camera góc hẹp chỉ thấy từ ngực/đầu trở lên, hông bị khuất ngoài khung hình (vis < 0.25)."""
    detector = FallDetector(DetectorConfig())

    close_up_pose = {
        "nose": Point(0.50, 0.20, 0.95),
        "left_shoulder": Point(0.40, 0.45, 0.90),
        "right_shoulder": Point(0.60, 0.45, 0.90),
        "left_hip": Point(0.45, 1.50, 0.05),   # Ngoài màn hình, vis cực thấp
        "right_hip": Point(0.55, 1.50, 0.08),  # Ngoài màn hình, vis cực thấp
    }

    for _ in range(30):
        res = detector.update(close_up_pose)
        assert res.state == FallState.NORMAL
        assert res.lying_seconds == 0.0
        assert not res.event_started


def test_real_fall_still_triggers_alert():
    """Cú ngã thật với chuyển động rơi nhanh và nằm bất động >= 2.5s -> Phải kích hoạt ALERT."""
    detector = FallDetector(
        DetectorConfig(
            torso_fall_angle_deg=58.0,
            alert_after_seconds=2.0,
            min_fall_frames=4,
            assumed_fps=10,
        )
    )

    standing_pose = {
        "nose": Point(0.50, 0.18, 0.95),
        "left_shoulder": Point(0.44, 0.34, 0.95),
        "right_shoulder": Point(0.56, 0.34, 0.95),
        "left_hip": Point(0.46, 0.62, 0.95),
        "right_hip": Point(0.54, 0.62, 0.95),
    }

    lying_pose = {
        "nose": Point(0.20, 0.70, 0.95),
        "left_shoulder": Point(0.35, 0.71, 0.95),
        "right_shoulder": Point(0.37, 0.73, 0.95),
        "left_hip": Point(0.68, 0.72, 0.95),
        "right_hip": Point(0.70, 0.74, 0.95),
    }

    # 1. Đứng
    for _ in range(5):
        detector.update(standing_pose)

    # 2. Rơi đột ngột sang nằm
    fall_res = detector.update(lying_pose)
    assert fall_res.fall_like_transition is True

    # 3. Nằm im trên sàn trong 2.5 giây (25 frames @ 10fps)
    alert_triggered = False
    for _ in range(25):
        res = detector.update(lying_pose)
        if res.event_started:
            alert_triggered = True

    assert alert_triggered is True
    assert res.state == FallState.ALERT


def test_compute_box_center_dist():
    """Kiểm tra tính khoảng cách tâm giữa 2 bounding box."""
    b1 = (100, 100, 50, 50)  # center = (125, 125)
    b2 = (110, 100, 50, 50)  # center = (135, 125)
    dist = _compute_box_center_dist(b1, b2)
    assert dist == pytest.approx(10.0, rel=1e-2)


def test_is_near_recent_known_face(tmp_path):
    """Kiểm tra cơ chế phát hiện khuôn mặt ở gần vị trí người quen vừa xuất hiện."""
    config = FaceConfig(enabled=True, known_faces_dir=str(tmp_path))
    recognizer = FaceRecognizer(config)

    now = time.time()
    # Giả lập đã nhận diện người quen 'Quan' tại vị trí (200, 150, 80, 80) cách đây 1.0 giây
    recognizer._recent_known_tracks.append((now - 1.0, "Quan", PersonType.FAMILY, (200, 150, 80, 80)))

    # 1. Box mới xê dịch nhẹ (215, 155, 75, 75) - cùng người đang nghiêng đầu
    box_shifted = (215, 155, 75, 75)
    assert recognizer.is_near_recent_known_face(box_shifted, max_seconds=4.0) is True

    # 2. Box ở vị trí hoàn toàn khác ở góc màn hình (600, 400, 80, 80) - đối tượng lạ mới
    box_far_away = (600, 400, 80, 80)
    assert recognizer.is_near_recent_known_face(box_far_away, max_seconds=4.0) is False
