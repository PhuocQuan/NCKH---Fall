"""
Tests for Pre-Fall Detection: Postural sway, stumble, dizziness, balance recovery,
and accelerated fall alert linkage.
"""
import math
import pytest

from src.core.config import DetectorConfig
from src.detection.balance_analyzer import BalanceAnalyzer, BalanceMetrics, PreFallType
from src.detection.fall_detector import FallDetector, FallState, Point


def make_standing_pose(offset_x: float = 0.0, offset_y: float = 0.0, tilt_angle_deg: float = 0.0) -> dict[str, Point]:
    """Tạo tư thế đứng với độ lệch ngang, dọc và góc nghiêng tùy chỉnh."""
    torso_len = 0.28
    rad = math.radians(tilt_angle_deg)
    tilt_dx = torso_len * math.sin(rad)
    tilt_dy = torso_len * (1.0 - math.cos(rad))

    hip_x = 0.50 + offset_x
    hip_y = 0.62 + offset_y
    sh_x = 0.50 + offset_x + tilt_dx
    sh_y = 0.34 + offset_y + tilt_dy

    return {
        "nose": Point(sh_x, sh_y - 0.16, 0.95),
        "left_shoulder": Point(sh_x - 0.06, sh_y, 0.95),
        "right_shoulder": Point(sh_x + 0.06, sh_y, 0.95),
        "left_hip": Point(hip_x - 0.04, hip_y, 0.95),
        "right_hip": Point(hip_x + 0.04, hip_y, 0.95),
    }


def make_lying_pose() -> dict[str, Point]:
    """Tư thế nằm ngang trên sàn."""
    return {
        "nose": Point(0.20, 0.70, 0.95),
        "left_shoulder": Point(0.35, 0.71, 0.95),
        "right_shoulder": Point(0.37, 0.73, 0.95),
        "left_hip": Point(0.68, 0.72, 0.95),
        "right_hip": Point(0.70, 0.74, 0.95),
    }


# ==============================================================================
# TC-PRE-01: Đi đứng bình thường (Normal Stable Pose)
# ==============================================================================
def test_tc_pre_01_stable_upright_pose_no_pre_fall():
    """
    TC-PRE-01: Người đứng yên hoặc chuyển động thẳng bình thường
    -> Không có tiền té ngã (pre_fall=False, state=NORMAL, postural_sway thấp).
    """
    config = DetectorConfig(enable_pre_fall=True)
    detector = FallDetector(config)

    for _ in range(15):
        res = detector.update(make_standing_pose(offset_x=0.0))
        assert res.state == FallState.NORMAL
        assert not res.pre_fall
        assert res.pre_fall_type in {"", PreFallType.NONE.value}
        assert res.postural_sway < 0.30


# ==============================================================================
# TC-PRE-02: Lảo đảo thân người mất thăng bằng (Postural Swaying)
# ==============================================================================
def test_tc_pre_02_postural_swaying_triggers_pre_fall():
    """
    TC-PRE-02: Dao động lắc ngang hình sin sang 2 bên trục X
    -> Kích hoạt pre_fall=True, pre_fall_type=SWAYING, state=PRE_FALL.
    """
    config = DetectorConfig(
        enable_pre_fall=True,
        pre_fall_sway_threshold=0.030,
        pre_fall_min_reversals=3,
        pre_fall_window_frames=15,
    )
    detector = FallDetector(config)

    detected_sway = False
    for i in range(18):
        # Dao động chu kỳ 5 frames với biên độ 0.05 > ngưỡng 0.030
        dx = 0.05 * math.sin(i * 2.0 * math.pi / 5.0)
        res = detector.update(make_standing_pose(offset_x=dx))
        if res.pre_fall and res.pre_fall_type == PreFallType.SWAYING.value:
            detected_sway = True
            assert res.state == FallState.PRE_FALL
            assert res.postural_sway >= 0.50

    assert detected_sway, "Hệ thống phải nhận diện được hiện tượng lảo đảo (SWAYING)"


# ==============================================================================
# TC-PRE-03: Bước hụt / Vấp ngã (Stumble / Sudden Drop)
# ==============================================================================
def test_tc_pre_03_stumble_sudden_drop_triggers_pre_fall():
    """
    TC-PRE-03: Đột biến hạ thấp trọng tâm kết hợp giật ngang hoặc vẹo góc
    -> Kích hoạt pre_fall=True, pre_fall_type=STUMBLE, state=PRE_FALL.
    """
    config = DetectorConfig(enable_pre_fall=True)
    detector = FallDetector(config)

    # 1. Đứng thẳng ban đầu
    detector.update(make_standing_pose())
    detector.update(make_standing_pose())

    # 2. Khụy hông nhanh (vy=0.030 >= 0.016) và giật lệch ngang (dx=0.020 >= 0.012)
    stumble_pose = make_standing_pose(offset_x=0.020, offset_y=0.030, tilt_angle_deg=35.0)
    res = detector.update(stumble_pose)

    assert res.pre_fall is True
    assert res.pre_fall_type == PreFallType.STUMBLE.value
    assert res.state == FallState.PRE_FALL


# ==============================================================================
# TC-PRE-04: Triệu chứng chóng mặt / Đung đưa kéo dài (Dizziness Sway)
# ==============================================================================
def test_tc_pre_04_dizziness_sustained_sway():
    """
    TC-PRE-04: Đứng đung đưa thân nghiêng qua lại kéo dài >= 25 frames
    -> Kích hoạt pre_fall=True, pre_fall_type=DIZZY, state=PRE_FALL.
    """
    config = DetectorConfig(
        enable_pre_fall=True,
        pre_fall_dizzy_duration_frames=25,
        pre_fall_sway_threshold=0.032,
        pre_fall_min_reversals=3,
    )
    detector = FallDetector(config)

    res = None
    for i in range(28):
        # Đung đưa chậm chu kỳ 8 frame, biên độ 0.032
        dx = 0.032 * math.sin(i * 2.0 * math.pi / 8.0)
        res = detector.update(make_standing_pose(offset_x=dx))

    assert res is not None
    assert res.pre_fall is True
    assert res.pre_fall_type == PreFallType.DIZZY.value
    assert res.state == FallState.PRE_FALL


# ==============================================================================
# TC-PRE-05: Tự phục hồi thăng bằng (Recovery back to NORMAL)
# ==============================================================================
def test_tc_pre_05_balance_recovery_resets_to_normal():
    """
    TC-PRE-05: Sau khi lảo đảo (PRE_FALL), người đứng thẳng tĩnh trong 5 frame
    -> Hệ thống tự động phục hồi về NORMAL.
    """
    config = DetectorConfig(
        enable_pre_fall=True,
        pre_fall_sway_threshold=0.030,
        pre_fall_min_reversals=3,
    )
    detector = FallDetector(config)

    # 1. Gây lảo đảo
    for i in range(16):
        dx = 0.05 * math.sin(i * 2.0 * math.pi / 5.0)
        detector.update(make_standing_pose(offset_x=dx))

    # 2. Đứng thẳng tĩnh lại trong 6 frame
    last_res = None
    for _ in range(6):
        last_res = detector.update(make_standing_pose(offset_x=0.0))

    assert last_res is not None
    assert last_res.state == FallState.NORMAL
    assert not last_res.pre_fall
    assert last_res.pre_fall_type in {"", PreFallType.NONE.value}


# ==============================================================================
# TC-PRE-06: Tích hợp chuỗi Tiền té ngã -> Té ngã thật (Pre-fall Linkage)
# ==============================================================================
def test_tc_pre_06_pre_fall_linkage_accelerates_alert():
    """
    TC-PRE-06: Khi có PRE_FALL trước khi nằm xuống sàn, hệ thống xác nhận ngã
    nhanh hơn (thời gian alert giảm một nửa so với thông thường).
    """
    # Kịch bản 1: Có pre-fall trước khi ngã
    det_pre_fall = FallDetector(
        DetectorConfig(
            min_fall_frames=6,
            alert_after_seconds=2.0,
            assumed_fps=10.0,  # 2.0s = 20 frames bình thường, có pre-fall -> 1.0s = 10 frames
            enable_pre_fall=True,
        )
    )
    # Lảo đảo trước
    for i in range(15):
        dx = 0.05 * math.sin(i * 2.0 * math.pi / 5.0)
        det_pre_fall.update(make_standing_pose(offset_x=dx))

    # Bắt đầu nằm xuống sàn
    pre_fall_alert_frame = None
    for f in range(1, 25):
        r = det_pre_fall.update(make_lying_pose())
        if r.state == FallState.ALERT:
            pre_fall_alert_frame = f
            break

    # Kịch bản 2: Không có pre-fall (ngã bất ngờ theo quy tắc chuẩn)
    det_standard = FallDetector(
        DetectorConfig(
            min_fall_frames=6,
            alert_after_seconds=2.0,
            assumed_fps=10.0,
            enable_pre_fall=False,
        )
    )
    # Đứng yên bình thường
    for _ in range(5):
        det_standard.update(make_standing_pose())

    # Khung hình chuyển tiếp ngã theo cách thông thường
    det_standard._fall_candidate = True
    standard_alert_frame = None
    for f in range(1, 25):
        r = det_standard.update(make_lying_pose())
        if r.state == FallState.ALERT:
            standard_alert_frame = f
            break

    assert pre_fall_alert_frame is not None, "Pre-fall sequence phải kích hoạt ALERT"
    assert standard_alert_frame is not None, "Standard fall sequence phải kích hoạt ALERT"
    assert pre_fall_alert_frame < standard_alert_frame, (
        f"Pre-fall alert ({pre_fall_alert_frame} frames) phải nhanh hơn standard alert ({standard_alert_frame} frames)"
    )


# ==============================================================================
# Unit Tests & Edge Cases cho BalanceAnalyzer
# ==============================================================================
def test_balance_analyzer_missing_landmarks_graceful():
    """Kiểm tra xử lý an toàn khi thiếu landmarks hoặc visibility thấp."""
    analyzer = BalanceAnalyzer()
    res = analyzer.analyze({}, torso_angle=10.0)
    assert not res.is_pre_fall
    assert res.pre_fall_type == PreFallType.NONE

    # Visibility cực thấp (< 0.20)
    low_vis_pose = {
        "left_shoulder": Point(0.4, 0.3, visibility=0.1),
        "right_shoulder": Point(0.6, 0.3, visibility=0.1),
        "left_hip": Point(0.4, 0.6, visibility=0.1),
        "right_hip": Point(0.6, 0.6, visibility=0.1),
    }
    res_low = analyzer.analyze(low_vis_pose, torso_angle=10.0)
    assert not res_low.is_pre_fall


def test_balance_analyzer_reset():
    """Kiểm tra phương thức reset dọn sạch bộ đệm."""
    analyzer = BalanceAnalyzer()
    for i in range(15):
        dx = 0.05 * math.sin(i * 2.0 * math.pi / 5.0)
        analyzer.analyze(make_standing_pose(offset_x=dx), torso_angle=15.0)

    analyzer.reset()
    assert len(analyzer._history) == 0
    assert analyzer._stable_upright_count == 0


def test_elderly_profile_scales_pre_fall_sway_threshold():
    """Kiểm tra cấu hình profile elderly làm tăng độ nhạy (giảm ngưỡng sway)."""
    base_cfg = DetectorConfig(profile="elderly", pre_fall_sway_threshold=0.032)
    detector = FallDetector(base_cfg)
    assert detector.config.pre_fall_sway_threshold == pytest.approx(0.032 * 0.85)


def test_swaying_precedence_after_long_sequence():
    """
    Kiểm tra độ ưu tiên phân loại: Khi người đã ở trong khung hình > 25 frames
    (vượt quá dizzy_duration_frames), sau đó xuất hiện dao động lắc ngang mạnh
    (SWAYING), hệ thống phải nhận diện chính xác là SWAYING chứ không bị nhầm
    thành DIZZY.
    """
    config = DetectorConfig(
        enable_pre_fall=True,
        pre_fall_sway_threshold=0.030,
        pre_fall_min_reversals=3,
        pre_fall_dizzy_duration_frames=20,
    )
    detector = FallDetector(config)

    # 1. Đứng yên bình thường 25 frames (> dizzy_duration_frames)
    for _ in range(25):
        detector.update(make_standing_pose(offset_x=0.0))

    # 2. Bắt đầu lảo đảo mạnh cấp tính
    detected_sway = False
    for i in range(16):
        dx = 0.05 * math.sin(i * 2.0 * math.pi / 5.0)
        res = detector.update(make_standing_pose(offset_x=dx))
        if res.pre_fall and res.pre_fall_type == PreFallType.SWAYING.value:
            detected_sway = True
            break

    assert detected_sway, "Dao động lắc ngang mạnh phải được phân loại là SWAYING kể cả khi lịch sử > dizzy_duration_frames"


def test_occlusion_gap_does_not_trigger_false_stumble():
    """
    Kiểm tra xử lý gián đoạn tracking: Khi bị che khuất tạm thời (landmarks rỗng hoặc
    visibility thấp), CoM trước đó phải được reset về None để không tính vận tốc giả
    mạo (delta) qua khoảng trống, tránh báo động giả STUMBLE.
    """
    detector = FallDetector(DetectorConfig(enable_pre_fall=True))

    # Frame 1: Đứng ở vị trí bình thường
    detector.update(make_standing_pose(offset_x=0.0, offset_y=0.0))

    # Frame 2: Mất tracking hoàn toàn do vật cản
    detector.update({})

    # Frame 3: Xuất hiện lại ở vị trí hơi lệch do bước đi bình thường
    res = detector.update(make_standing_pose(offset_x=0.025, offset_y=0.025))

    assert res.pre_fall_type != PreFallType.STUMBLE.value, (
        "Không được báo STUMBLE giả mạo khi xuất hiện lại sau một frame mất tracking"
    )


def test_pre_fall_linkage_sustained_for_long_alert_duration():
    """
    Kiểm tra tính bền vững của liên kết tiền té ngã: Khi alert_after_seconds kéo dài
    (ví dụ: 4.0s = 40 frames tại 10 fps > 30 frames bộ nhớ), liên kết tiền té ngã
    phải được duy trì cho toàn bộ sự cố té ngã (không bị mất ở frame 30), giúp alert
    kích hoạt chính xác ở 2.0s thay vì 4.0s.
    """
    detector = FallDetector(
        DetectorConfig(
            min_fall_frames=6,
            alert_after_seconds=4.0,
            assumed_fps=10.0,
            enable_pre_fall=True,
        )
    )

    # 1. Lảo đảo (PRE_FALL)
    for i in range(15):
        dx = 0.05 * math.sin(i * 2.0 * math.pi / 5.0)
        detector.update(make_standing_pose(offset_x=dx))

    # 2. Ngã và nằm trên sàn
    alert_frame = None
    for f in range(1, 45):
        r = detector.update(make_lying_pose())
        if r.state == FallState.ALERT:
            alert_frame = f
            break

    # Tại 10 fps, alert_after_seconds = 4.0s (40 frames). Có pre-fall giảm 50% -> 2.0s = 20 frames
    assert alert_frame is not None, "Phải kích hoạt ALERT sau khi ngã"
    assert alert_frame == pytest.approx(20, abs=2), (
        f"Alert frame phải kích hoạt ở ~20 frames (2.0s), nhưng thực tế kích hoạt ở {alert_frame}"
    )


def test_recovered_balance_clears_pre_fall_history():
    """
    Kiểm tra phục hồi thăng bằng: Sau khi lảo đảo, nếu người đó đứng yên tĩnh và
    phục hồi thăng bằng hoàn toàn, bộ nhớ tiền té ngã phải bị xóa bỏ.
    Khi xảy ra té ngã sau khi đã phục hồi, cảnh báo không được kích hoạt theo thời gian
    rút ngắn của tiền té ngã mà phải tuân theo thời gian chuẩn.
    """
    detector = FallDetector(
        DetectorConfig(
            min_fall_frames=6,
            alert_after_seconds=2.0,
            assumed_fps=10.0,
            enable_pre_fall=True,
        )
    )

    # 1. Gây lảo đảo (PRE_FALL)
    for i in range(15):
        dx = 0.05 * math.sin(i * 2.0 * math.pi / 5.0)
        detector.update(make_standing_pose(offset_x=dx))
    assert detector._pre_fall_history_frames > 0

    # 2. Đứng yên phục hồi hoàn toàn (6 frames)
    for _ in range(6):
        detector.update(make_standing_pose(offset_x=0.0))

    # Bộ nhớ pre-fall phải được xóa hoàn toàn khi phục hồi thăng bằng
    assert detector._pre_fall_history_frames == 0
    assert not detector._fall_from_pre_fall

    # 3. Khi ngã sau khi đã phục hồi, tại frame 10 (thời điểm accelerated alert nếu có pre-fall)
    # hệ thống CHƯA được kích hoạt ALERT vì không còn liên kết tiền té ngã
    alert_at_frame_10 = False
    alert_at_frame_20 = False
    for f in range(1, 25):
        res = detector.update(make_lying_pose())
        if res.state == FallState.ALERT:
            if f <= 12:
                alert_at_frame_10 = True
            if f >= 18:
                alert_at_frame_20 = True
            break

    assert not alert_at_frame_10, "Sau khi phục hồi, không được kích hoạt alert sớm (accelerated alert)"
    assert alert_at_frame_20, "Phải kích hoạt ALERT ở chu kỳ chuẩn (~20 frames)"


def test_draw_status_in_app_and_pipeline_robustness():
    """
    Kiểm tra hàm _draw_status trong app.py và pipeline.py không bị crash với các tham số,
    và trạng thái ALERT/FALLEN không bị ghi đè bởi nhãn TIEN TE NGA.
    """
    import numpy as np
    from dataclasses import dataclass
    from src.core.app import _draw_status as app_draw_status
    from src.detection.fall_detector import DetectionResult, FallState
    from src.web.shared.pipeline import _draw_status as pipe_draw_status
    import cv2

    @dataclass
    class DummyAI:
        enabled: bool = True
        label: str = "normal"
        probability: float = 0.20

    img = np.zeros((480, 640, 3), dtype=np.uint8)

    # 1. Gọi app_draw_status với 3 tham số (tương thích ngược)
    res_normal = DetectionResult(
        state=FallState.NORMAL, torso_angle_deg=12.0, head_hip_delta=0.5,
        hip_velocity=0.0, angle_velocity_deg=0.0, abnormal_frames=0,
        lying_seconds=0.0, profile="default", fall_like_transition=False,
    )
    app_draw_status(img, res_normal, DummyAI())

    # 2. Gọi app_draw_status với 5 tham số (kèm tên người và phân loại)
    res_pre_fall = DetectionResult(
        state=FallState.PRE_FALL, torso_angle_deg=25.0, head_hip_delta=0.45,
        hip_velocity=0.01, angle_velocity_deg=3.0, abnormal_frames=0,
        lying_seconds=0.0, profile="default", fall_like_transition=False,
        pre_fall=True, pre_fall_type="swaying", postural_sway=0.72,
    )
    app_draw_status(img, res_pre_fall, DummyAI(), "OngNoi", "ATTENTION")

    # 3. Khi ở trạng thái ALERT với pre_fall=True, nhãn vẽ phải là ALERT chứ không bị đè bởi PRE_FALL
    res_alert = DetectionResult(
        state=FallState.ALERT, torso_angle_deg=75.0, head_hip_delta=0.1,
        hip_velocity=0.0, angle_velocity_deg=0.0, abnormal_frames=15,
        lying_seconds=3.0, profile="default", fall_like_transition=True,
        pre_fall=True, pre_fall_type="swaying", postural_sway=0.85,
    )
    app_draw_status(img, res_alert, DummyAI(), "BàNgoại", "FAMILY")

    # 4. Kiểm tra pipeline _draw_status
    state_colors = {
        FallState.NORMAL: (70, 200, 90),
        FallState.PRE_FALL: (0, 165, 255),
        FallState.ALERT: (0, 0, 255),
    }
    pipe_draw_status(img, res_pre_fall, DummyAI(), state_colors, cv2, pose_detected=True)
    pipe_draw_status(img, res_alert, DummyAI(), state_colors, cv2, pose_detected=True)

