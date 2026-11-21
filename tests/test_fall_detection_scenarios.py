"""
Master Test Plan - Suite 1: AI & Fall Detection Scenarios
Covers:
- TC-AI-01: Smoothly lying down to sleep vs Real fall
- TC-AI-02: Sudden fall event triggering and state progression
- TC-AI-03: Bending down to pick up objects & recovery
- TC-AI-04: Sitting upright on the floor
- TC-AI-07: Demographic sensitivity profiles (Elderly, Child, Pregnant, Disabled)
"""

import pytest
from src.core.config import DetectorConfig
from src.detection.fall_detector import FallDetector, FallState, Point


def make_pose(nose_y=0.18, sh_y=0.34, hip_y=0.62, nose_x=0.50, sh_dx=0.06, hip_dx=0.04):
    """Tạo toạ độ pose linh hoạt dựa trên toạ độ y và x."""
    return {
        "nose": Point(nose_x, nose_y, 0.95),
        "left_shoulder": Point(0.50 - sh_dx, sh_y, 0.95),
        "right_shoulder": Point(0.50 + sh_dx, sh_y, 0.95),
        "left_hip": Point(0.50 - hip_dx, hip_y, 0.95),
        "right_hip": Point(0.50 + hip_dx, hip_y, 0.95),
    }


def standing_pose():
    # Thân thẳng đứng, góc ~0 độ
    return {
        "nose": Point(0.50, 0.18, 0.95),
        "left_shoulder": Point(0.44, 0.34, 0.95),
        "right_shoulder": Point(0.56, 0.34, 0.95),
        "left_hip": Point(0.46, 0.62, 0.95),
        "right_hip": Point(0.54, 0.62, 0.95),
    }


def lying_pose():
    # Thân nằm ngang trên sàn, góc ~85-90 độ, đầu và hông ngang nhau
    return {
        "nose": Point(0.20, 0.70, 0.95),
        "left_shoulder": Point(0.35, 0.71, 0.95),
        "right_shoulder": Point(0.37, 0.73, 0.95),
        "left_hip": Point(0.68, 0.72, 0.95),
        "right_hip": Point(0.70, 0.74, 0.95),
    }


def sitting_on_floor_pose():
    # Ngồi bệt dưới sàn: Hông ở vị trí thấp (y=0.75), nhưng lưng đứng thẳng (y vai=0.50, y đầu=0.35)
    return {
        "nose": Point(0.50, 0.35, 0.95),
        "left_shoulder": Point(0.44, 0.50, 0.95),
        "right_shoulder": Point(0.56, 0.50, 0.95),
        "left_hip": Point(0.46, 0.75, 0.95),
        "right_hip": Point(0.54, 0.75, 0.95),
    }


def bending_pose():
    # Cúi nhặt đồ: Lưng nghiêng nhiều (>50 độ) nhưng chân và hông vẫn ở độ cao đứng (y hip ~ 0.55), đầu chúc xuống
    return {
        "nose": Point(0.32, 0.65, 0.95),
        "left_shoulder": Point(0.40, 0.58, 0.95),
        "right_shoulder": Point(0.42, 0.60, 0.95),
        "left_hip": Point(0.52, 0.55, 0.95),
        "right_hip": Point(0.54, 0.55, 0.95),
    }


# ==============================================================================
# TEST CASE TC-AI-01: NẰM NGỦ CHỦ ĐỘNG (KHÔNG PHẢI TÉ NGÃ)
# ==============================================================================
def test_tc_ai_01_lying_down_smoothly_does_not_trigger_alert():
    """
    Kịch bản: Người từ từ nằm xuống giường/sàn mà không có chuyển động rơi đột ngột.
    Hệ thống phải nhận diện là LYING, tuyệt đối không kích hoạt event_started=True.
    """
    config = DetectorConfig(
        min_fall_frames=4,
        warning_frames=2,
        alert_after_seconds=3.0,
        alert_on_long_lying_without_fall=False,  # Chuẩn NCKH: không cảnh báo nằm ngủ
        assumed_fps=10,
    )
    detector = FallDetector(config)

    # 1. Bắt đầu từ tư thế nằm thẳng hoặc chuyển tiếp cực kỳ êm (không có hip drop hay angle drop)
    # Giả lập người đã nằm sẵn hoặc chuyển động rất chậm
    for _ in range(5):
        res = detector.update(lying_pose())
        assert res.state in {FallState.LYING, FallState.NORMAL}
        assert not res.event_started

    # 2. Người tiếp tục nằm im trong 50 frames (> 5 giây, vượt quá alert_after_seconds)
    for _ in range(50):
        res = detector.update(lying_pose())
        assert res.state == FallState.LYING
        assert not res.event_started  # KHÔNG BAO GIỜ kích hoạt alert


# ==============================================================================
# TEST CASE TC-AI-02: CÚ TÉ NGÃ THẬT ĐỘT NGỘT
# ==============================================================================
def test_tc_ai_02_sudden_fall_triggers_alert_properly():
    """
    Kịch bản: Đang đứng thẳng -> ngã đập xuống sàn (vận tốc rơi cao + xoay góc nhanh) -> nằm bất động.
    Hệ thống phải qua các bước: NORMAL -> POSSIBLE_FALL / FALLEN -> ALERT và kích hoạt đúng 1 lần event_started.
    """
    config = DetectorConfig(
        min_fall_frames=3,
        warning_frames=2,
        alert_after_seconds=1.0,
        assumed_fps=10,
        cooldown_frames=20,
    )
    detector = FallDetector(config)

    # 1. Đứng thẳng trong 5 frames
    for _ in range(5):
        res = detector.update(standing_pose())
        assert res.state == FallState.NORMAL

    # 2. Frame té ngã đột ngột: từ đứng thẳng sụp xuống nằm ngang
    # Hip rơi từ 0.62 xuống 0.73 (delta = 0.11 > 0.025)
    fall_res = detector.update(lying_pose())
    assert fall_res.fall_like_transition is True

    # 3. Tiếp tục nằm trên sàn: state chuyển sang FALLEN sau khi đủ min_fall_frames
    for _ in range(config.min_fall_frames):
        res = detector.update(lying_pose())

    assert res.state in {FallState.FALLEN, FallState.ALERT}

    # 4. Nằm tiếp đủ thời gian alert_after_seconds (10 frames @ 10fps = 1.0s)
    event_started_count = 0
    for _ in range(15):
        res = detector.update(lying_pose())
        if res.event_started:
            event_started_count += 1
            assert res.state == FallState.ALERT

    # Khẳng định chỉ kích hoạt alert đúng 1 lần (không spam chuông/event)
    assert event_started_count == 1
    assert res.state == FallState.ALERT


# ==============================================================================
# TEST CASE TC-AI-03: CÚI NHẶT ĐỒ RỒI ĐỨNG DẬY
# ==============================================================================
def test_tc_ai_03_bending_and_recovering_resets_to_normal():
    """
    Kịch bản: Người cúi người nhặt đồ trong 1-2 giây rồi đứng thẳng dậy.
    Hệ thống không được kết luận té ngã, và khi đứng thẳng phải quay về NORMAL ngay lập tức.
    """
    detector = FallDetector(DetectorConfig(assumed_fps=10))

    # Đứng thẳng
    detector.update(standing_pose())
    detector.update(standing_pose())

    # Cúi gập người trong 3 frames
    for _ in range(3):
        detector.update(bending_pose())

    # Đứng thẳng dậy ngay lập tức
    for _ in range(3):
        res = detector.update(standing_pose())
        assert res.state == FallState.NORMAL
        assert res.abnormal_frames == 0
        assert not res.event_started


# ==============================================================================
# TEST CASE TC-AI-04: NGỒI BỆT TRÊN SÀN
# ==============================================================================
def test_tc_ai_04_sitting_on_floor_stays_normal():
    """
    Kịch bản: Người ngồi bệt xuống sàn, lưng tựa thẳng.
    Vì lưng vẫn hướng thẳng đứng (torso_angle < 32 deg), trạng thái duy trì NORMAL.
    """
    detector = FallDetector()

    for _ in range(10):
        res = detector.update(sitting_on_floor_pose())
        assert res.state == FallState.NORMAL
        assert res.torso_angle_deg < 32.0


# ==============================================================================
# TEST CASE TC-AI-07: KIỂM TRA ĐỘ NHẠY THEO HỒ SƠ ĐỐI TƯỢNG (PROFILES)
# ==============================================================================
def test_tc_ai_07_profile_sensitivity_adjustments():
    """
    Kiểm tra thuật toán tự động nhân hệ số nhạy cảm cho các nhóm đối tượng:
    - elderly: 0.85
    - child: 0.90
    - pregnant: 0.85
    - disabled: 0.80
    """
    from dataclasses import replace
    base_config = DetectorConfig(
        torso_fall_angle_deg=52.0,
        hip_drop_velocity=0.025,
        angle_change_velocity_deg=14.0,
    )

    # Test Profile Người cao tuổi (Elderly)
    elderly_detector = FallDetector(replace(base_config, profile="elderly"))
    assert elderly_detector.config.torso_fall_angle_deg == pytest.approx(52.0 * 0.85, rel=1e-2)
    assert elderly_detector.config.hip_drop_velocity == pytest.approx(0.025 * 0.85, rel=1e-2)

    # Test Profile Trẻ em (Child)
    child_detector = FallDetector(replace(base_config, profile="child"))
    assert child_detector.config.torso_fall_angle_deg == pytest.approx(52.0 * 0.90, rel=1e-2)

    # Test Profile Người khuyết tật (Disabled - Nhạy nhất)
    disabled_detector = FallDetector(replace(base_config, profile="disabled"))
    assert disabled_detector.config.torso_fall_angle_deg == pytest.approx(52.0 * 0.80, rel=1e-2)
