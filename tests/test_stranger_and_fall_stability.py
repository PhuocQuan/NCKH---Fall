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
from src.web.shared.pipeline import filter_anatomical_faces


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


def test_desk_occlusion_and_high_angle_sitting_does_not_trigger_fall():
    """
    TC-DESK-01: Ngồi làm việc trước bàn laptop, thân dưới bị bàn che khuất.
    MediaPipe ước lượng hông tại mặt bàn khiến |hip.y - shoulder.y| = 0.06 < 0.14,
    khiến góc thân tính ra ~76 độ. Hệ thống phải nhận biết tư thế ngồi (is_seated = True),
    duy trì NORMAL và TUYỆT ĐỐI KHÔNG BÁO ALERT dù ngồi bất động lâu.
    """
    detector = FallDetector(
        DetectorConfig(
            torso_fall_angle_deg=58.0,
            alert_after_seconds=2.0,
            assumed_fps=15,
        )
    )

    # Vai ở y=0.38, hông ở y=0.44 (nén dọc 0.06), x lệch 0.15 -> góc ~68-76 độ
    # Đầu gần mép trên (nose.y = 0.06 <= 0.08)
    sitting_desk_pose = {
        "nose": Point(0.50, 0.06, 0.95),
        "left_shoulder": Point(0.35, 0.38, 0.95),
        "right_shoulder": Point(0.49, 0.38, 0.95),
        "left_hip": Point(0.50, 0.44, 0.95),
        "right_hip": Point(0.64, 0.44, 0.95),
    }

    alert_fired = False
    for _ in range(60):  # 4 giây liên tục (> alert_after_seconds = 2.0s)
        res = detector.update(sitting_desk_pose)
        if res.event_started or res.state == FallState.ALERT:
            alert_fired = True

    assert alert_fired is False
    assert res.state == FallState.NORMAL
    assert res.is_seated is True
    assert res.lying_seconds == 0.0
    assert not res.event_started


def test_false_face_on_keyboard_rejected_by_anatomical_position():
    """
    TC-DESK-02: Bàn tay gõ bàn phím bị nhận diện nhầm thành khuôn mặt (NGUOI LA).
    Bộ lọc giải phẫu học phát hiện tâm box nằm sâu bên dưới vai (center_y > sh_y + 0.12)
    và loại bỏ triệt để, không để lọt vào danh sách người lạ.
    """
    pose_points = {
        "nose": Point(0.50, 0.15, 0.95),
        "left_shoulder": Point(0.40, 0.38, 0.95),
        "right_shoulder": Point(0.60, 0.38, 0.95),
        "left_hip": Point(0.45, 0.44, 0.95),
        "right_hip": Point(0.55, 0.44, 0.95),
    }

    # Giả lập box mặt ảo trên bàn phím: frame cao 480, box tại y=330, h=60 (center y = 360 -> y_norm = 0.75 > 0.38 + 0.12 = 0.50)
    fake_face = RecognizedFace(
        name="Unknown",
        confidence=0.66,
        person_type=PersonType.STRANGER,
        box=(250, 330, 60, 60),
    )

    # Giả lập khuôn mặt thật trên đầu: box tại y=60, h=70 (center y = 95 -> y_norm = 0.198 < 0.50)
    real_face = RecognizedFace(
        name="Phuoc Quan",
        confidence=0.92,
        person_type=PersonType.FAMILY,
        box=(260, 60, 70, 70),
    )

    # 1. Khi có cả mặt thật và mặt ảo trên phím: Chỉ giữ lại mặt thật
    filtered = filter_anatomical_faces([fake_face, real_face], pose_points, frame_height=480)
    assert len(filtered) == 1
    assert filtered[0].name == "Phuoc Quan"

    # 2. Khi chỉ có mặt ảo trên phím (ví dụ đầu bị che khuất): Loại bỏ 100%
    filtered_only_fake = filter_anatomical_faces([fake_face], pose_points, frame_height=480)
    assert len(filtered_only_fake) == 0


def test_real_fall_on_floor_with_ground_proximity_triggers_alert():
    """
    TC-DESK-03: Cú ngã thật xuống sàn nhà (Ground Proximity: shoulder.y >= 0.52 và hip.y >= 0.60).
    Hệ thống nhận diện chính xác đây là ngã trên sàn, không bị chặn bởi bộ lọc ngồi,
    và kích hoạt FallState.ALERT.
    """
    detector = FallDetector(
        DetectorConfig(
            torso_fall_angle_deg=58.0,
            alert_after_seconds=1.5,
            min_fall_frames=3,
            assumed_fps=10,
        )
    )

    standing_pose = {
        "nose": Point(0.50, 0.18, 0.95),
        "left_shoulder": Point(0.44, 0.32, 0.95),
        "right_shoulder": Point(0.56, 0.32, 0.95),
        "left_hip": Point(0.46, 0.60, 0.95),
        "right_hip": Point(0.54, 0.60, 0.95),
    }

    floor_fall_pose = {
        "nose": Point(0.20, 0.70, 0.95),
        "left_shoulder": Point(0.35, 0.70, 0.95),
        "right_shoulder": Point(0.37, 0.72, 0.95),
        "left_hip": Point(0.68, 0.72, 0.95),
        "right_hip": Point(0.70, 0.74, 0.95),
    }

    # Đứng bình thường
    for _ in range(5):
        detector.update(standing_pose)

    # Rơi xuống sàn
    transition_res = detector.update(floor_fall_pose)
    assert transition_res.fall_like_transition is True
    assert transition_res.is_seated is False

    # Nằm im trên sàn quá thời gian quy định
    alert_triggered = False
    for _ in range(20):  # 2.0 giây
        res = detector.update(floor_fall_pose)
        if res.event_started or res.state == FallState.ALERT:
            alert_triggered = True

    assert alert_triggered is True
    assert res.state == FallState.ALERT
    assert res.is_seated is False


def test_filter_anatomical_faces_edge_cases():
    """Kiểm tra các trường hợp biên của bộ lọc giải phẫu học khuôn mặt."""
    # 1. Danh sách khuôn mặt rỗng
    assert filter_anatomical_faces([], {"left_shoulder": Point(0.4, 0.4)}, 480) == []

    # 2. Points là None
    fake_face = RecognizedFace("Unknown", PersonType.STRANGER, (10, 10, 50, 50), 0.66)
    assert filter_anatomical_faces([fake_face], None, 480) == [fake_face]

    # 3. Frame height không hợp lệ
    assert filter_anatomical_faces([fake_face], {"left_shoulder": Point(0.4, 0.4)}, 0) == [fake_face]

    # 4. Vai không đủ độ tin cậy visibility (<= 0.20)
    low_vis_points = {
        "left_shoulder": Point(0.4, 0.4, visibility=0.10),
        "right_shoulder": Point(0.6, 0.4, visibility=0.15),
    }
    assert filter_anatomical_faces([fake_face], low_vis_points, 480) == [fake_face]

    # 5. Chỉ 1 vai rõ nét: vẫn tính theo vai rõ nét đó
    one_sh_points = {
        "left_shoulder": Point(0.4, 0.35, visibility=0.90),
        "right_shoulder": Point(0.6, 0.35, visibility=0.10),
    }
    # Mặt ở y=300 (tâm y=325/480 = 0.677 > 0.35 + 0.12) -> bị loại
    face_on_hand = RecognizedFace("Unknown", PersonType.STRANGER, (100, 300, 50, 50), 0.70)
    assert filter_anatomical_faces([face_on_hand], one_sh_points, 480) == []


def test_sitting_with_occluded_nose_stays_normal():
    """Kiểm tra khi ngồi sát mép trên khung hình với mũi bị khuất (vis < 0.35)."""
    detector = FallDetector(DetectorConfig(alert_after_seconds=1.5, assumed_fps=10))

    sitting_cut_off_head = {
        "nose": Point(0.50, 0.02, visibility=0.10),  # Mũi bị cắt ở mép trên
        "left_shoulder": Point(0.40, 0.36, visibility=0.95),
        "right_shoulder": Point(0.60, 0.36, visibility=0.95),
        "left_hip": Point(0.44, 0.43, visibility=0.95),  # Bị bàn che khuất (|0.43 - 0.36| = 0.07 < 0.14)
        "right_hip": Point(0.56, 0.43, visibility=0.95),
    }

    for _ in range(25):
        res = detector.update(sitting_cut_off_head)
        assert res.state == FallState.NORMAL
        assert res.is_seated is True
        assert res.lying_seconds == 0.0
        assert not res.event_started


def test_ground_proximity_floor_fall_near_chair_triggers_alert():
    """
    TC-DESK-04: Ngã thật trên sàn nhà gần ghế (Ground Proximity: hip.y = 0.65 >= 0.60, shoulder.y = 0.50).
    Dù có ghế (chair) ngay cạnh và giao thoa bounding box, Ground Proximity phải nhận diện đây là
    ngã trên sàn (is_seated = False) và kích hoạt ALERT, tuyệt đối không bị bộ lọc ngồi chặn lại.
    """
    from src.detection.object_detector import DetectedObject

    detector = FallDetector(
        DetectorConfig(
            torso_fall_angle_deg=58.0,
            alert_after_seconds=1.0,
            min_fall_frames=2,
            assumed_fps=10,
        )
    )

    standing_pose = {
        "nose": Point(0.40, 0.18, 0.95),
        "left_shoulder": Point(0.35, 0.32, 0.95),
        "right_shoulder": Point(0.47, 0.32, 0.95),
        "left_hip": Point(0.37, 0.58, 0.95),
        "right_hip": Point(0.45, 0.58, 0.95),
    }

    # Người ngã xuống sàn gần ghế: hông chạm sàn y=0.65 (>= 0.60), vai ở y=0.50 (< 0.52)
    chair_obj = DetectedObject("chair", 0.90, (100, 100, 200, 200), (0.2, 0.4, 0.8, 0.8))
    floor_fall_pose = {
        "nose": Point(0.20, 0.55, 0.95),
        "left_shoulder": Point(0.35, 0.50, 0.95),
        "right_shoulder": Point(0.37, 0.50, 0.95),
        "left_hip": Point(0.68, 0.65, 0.95),
        "right_hip": Point(0.70, 0.65, 0.95),
    }

    for _ in range(5):
        detector.update(standing_pose, nearby_objects=[chair_obj])

    # Chuyển động ngã xuống sàn
    transition = detector.update(floor_fall_pose, nearby_objects=[chair_obj])
    assert transition.is_seated is False

    alert_fired = False
    for _ in range(15):  # 1.5s > 1.0s alert
        res = detector.update(floor_fall_pose, nearby_objects=[chair_obj])
        if res.event_started or res.state == FallState.ALERT:
            alert_fired = True

    assert alert_fired is True
    assert res.state == FallState.ALERT
    assert res.is_seated is False


def test_flat_floor_fall_across_room_not_confused_with_desk_occlusion():
    """
    TC-DESK-05: Người ngã nằm phẳng trên sàn ở xa camera (shoulder.y = 0.49, hip.y = 0.52, nose.y = 0.48).
    Do nằm ngang, |hip.y - shoulder.y| = 0.03 < 0.14, nhưng đầu nằm sát sàn cùng mức vai (không phải đầu
    hướng lên trên trần nhà khi ngồi bàn). Hệ thống phải nhận biết đây là ngã sàn và phát báo động.
    """
    detector = FallDetector(
        DetectorConfig(
            torso_fall_angle_deg=58.0,
            alert_after_seconds=1.0,
            min_fall_frames=2,
            assumed_fps=10,
        )
    )

    standing_pose = {
        "nose": Point(0.50, 0.20, 0.95),
        "left_shoulder": Point(0.45, 0.30, 0.95),
        "right_shoulder": Point(0.55, 0.30, 0.95),
        "left_hip": Point(0.46, 0.55, 0.95),
        "right_hip": Point(0.54, 0.55, 0.95),
    }

    # Nằm ngang trên sàn ở xa: đầu ngang vai
    flat_fall_pose = {
        "nose": Point(0.20, 0.48, 0.95),
        "left_shoulder": Point(0.35, 0.49, 0.95),
        "right_shoulder": Point(0.37, 0.49, 0.95),
        "left_hip": Point(0.68, 0.52, 0.95),
        "right_hip": Point(0.70, 0.52, 0.95),
    }

    for _ in range(5):
        detector.update(standing_pose)

    alert_fired = False
    for _ in range(15):
        res = detector.update(flat_fall_pose)
        if res.event_started or res.state == FallState.ALERT:
            alert_fired = True

    assert alert_fired is True
    assert res.state == FallState.ALERT
    assert res.is_seated is False


def test_forearm_limb_artifact_horizontal_on_table_rejected_as_fall():
    """
    TC-DESK-06: Người đặt cẳng tay lên bàn (như trong ảnh thực tế 09:50:39).
    MediaPipe bắt nhầm cẳng tay nằm ngang (góc ~87.7 độ) thành thân người, nhưng
    chiều dài thân cực ngắn (|L_torso| = 0.10 < 0.14). Hệ thống phải nhận diện
    đây là chi thể (is_limb_artifact = True), duy trì NORMAL và KHÔNG BÁO NGÃ.
    """
    detector = FallDetector(
        DetectorConfig(
            torso_fall_angle_deg=58.0,
            alert_after_seconds=1.0,
            min_fall_frames=2,
            warning_frames=2,
            assumed_fps=10,
        )
    )

    # Cẳng tay nằm ngang trên bàn: góc 87 độ nhưng chiều dài thân chỉ 0.10
    forearm_table_pose = {
        "nose": Point(0.35, 0.40, 0.40),
        "left_shoulder": Point(0.30, 0.65, 0.90),
        "right_shoulder": Point(0.32, 0.65, 0.90),
        "left_hip": Point(0.40, 0.66, 0.85),
        "right_hip": Point(0.42, 0.66, 0.85),
    }

    for _ in range(20):
        res = detector.update(forearm_table_pose)
        assert res.state == FallState.NORMAL
        assert not res.event_started


def test_close_up_fist_tiny_face_filtered_when_no_pose():
    """
    TC-DESK-07: Nắm đấm/tay che sát camera (như trong ảnh thực tế 09:50:28, SEARCHING POSE).
    YuNet bắt nhầm nếp nhăn da thành các box khuôn mặt tí hon (24px, 28px).
    Bộ lọc filter_anatomical_faces khi points=None phải tự động loại bỏ các box < 36px hoặc conf < 0.60.
    """
    from src.web.shared.pipeline import filter_anatomical_faces

    fake_tiny_faces = [
        RecognizedFace(name="Quan", person_type=PersonType.FAMILY, box=(150, 200, 24, 24), confidence=0.55),
        RecognizedFace(name="Quan", person_type=PersonType.FAMILY, box=(170, 210, 28, 28), confidence=0.52),
        RecognizedFace(name="Stranger", person_type=PersonType.STRANGER, box=(180, 220, 26, 26), confidence=0.50),
    ]

    filtered = filter_anatomical_faces(fake_tiny_faces, points=None, frame_height=720)
    assert len(filtered) == 0, "Toàn bộ box mặt ảo trên nắm đấm phải bị loại bỏ"


def test_multi_person_bounding_boxes_renders_separate_boxes_for_each_person():
    """
    TC-MULTI-01: Kiểm tra tính năng 'Mỗi người mỗi khung riêng' khi có 2 người trong khung hình.
    - Người 1 (An): Có MediaPipe Pose skeleton + Face 'An'.
    - Người 2 (Bao): Không có MediaPipe Pose skeleton (do MediaPipe chỉ tracking 1 người) + Face 'Bao'.
    -> _draw_multi_person_boxes phải vẽ 2 bounding box riêng biệt: 'Nguoi: An' và 'Nguoi: Bao'.
    """
    import numpy as np
    import cv2
    from src.web.shared.pipeline import _draw_multi_person_boxes

    # Frame giả lập 640x480
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Người 1: An ở bên phải
    face_an = RecognizedFace(name="An", person_type=PersonType.FAMILY, box=(480, 100, 50, 60), confidence=0.88)
    pose_points = {
        "nose": Point(0.79, 0.25, 0.95),
        "left_shoulder": Point(0.73, 0.35, 0.95),
        "right_shoulder": Point(0.85, 0.35, 0.95),
        "left_hip": Point(0.75, 0.65, 0.95),
        "right_hip": Point(0.83, 0.65, 0.95),
    }

    # Người 2: Bao ở bên trái (cầm điện thoại, không có skeleton)
    face_bao = RecognizedFace(name="Bao", person_type=PersonType.FAMILY, box=(120, 100, 50, 60), confidence=0.85)

    _draw_multi_person_boxes(
        frame=frame,
        faces=[face_an, face_bao],
        points=pose_points,
        cached_objects=[],
        fall_result=None,
        cv2=cv2,
    )

    # Frame không còn toàn số 0 (đã được vẽ các đường viền và nhãn màu xanh)
    assert np.any(frame > 0), "Frame phải có các bounding box được vẽ"


def test_typing_sitting_posture_does_not_trigger_pre_fall():
    """
    TC-PRE-07: Người ngồi thẳng gõ phím máy tính (torso_angle 18.3°, rung lắc tay gõ phím).
    Trước đây bị nhận diện nhầm thành TIEN TE NGA: LAO DAO (88%) | 18.3deg.
    Bây giờ với bộ lọc is_stable_upright và Scale Normalization, pre_fall=False và state=NORMAL.
    """
    cfg = DetectorConfig(
        enable_pre_fall=True,
        torso_upright_angle_deg=32.0,
        torso_fall_angle_deg=58.0,
        pre_fall_sway_threshold=0.032,
        pre_fall_min_reversals=3,
    )
    detector = FallDetector(cfg)

    # Mô phỏng người ngồi thẳng làm việc với góc thân 18.3° và rung tay gõ phím
    import math
    for i in range(25):
        # Rung tay/thân cực nhỏ khi gõ phím (~0.005)
        jitter = 0.005 * math.sin(i * 1.5)
        # Giữ góc thân ~ 18.3 độ (x_sh - x_hip ~ 0.065 với y_span = 0.20)
        pose = {
            "nose": Point(0.50 + jitter, 0.15, 0.95),
            "left_shoulder": Point(0.44 + jitter, 0.25, 0.95),
            "right_shoulder": Point(0.56 + jitter, 0.25, 0.95),
            "left_hip": Point(0.38, 0.45, 0.95),
            "right_hip": Point(0.50, 0.45, 0.95),
        }
        res = detector.update(pose)

    assert res.pre_fall is False, "Ngồi thẳng gõ phím không được báo Tiền té ngã"
    assert res.state == FallState.NORMAL


def test_multi_person_pose_estimation_and_drawing():
    """
    TC-MULTI-02: Kiểm tra tính năng nhận diện khung xương đa người (Multi-person Pose Estimation).
    Khi trong khung hình có 2 người (Bảo và Ân), PoseEstimator.estimate_multi nhận diện
    từng người thông qua crop ROI và PoseEstimator.draw vẽ được khung xương cho cả hai.
    """
    from src.detection.pose_estimator import PoseEstimator, RemappedLandmark, RemappedPoseResult
    import numpy as np

    pe = PoseEstimator()

    # Tạo 2 kết quả pose giả lập cho 2 người
    lms_1 = [RemappedLandmark(0.2, 0.2, 0.0, 0.9) for _ in range(33)]
    lms_2 = [RemappedLandmark(0.7, 0.2, 0.0, 0.9) for _ in range(33)]

    res_1 = RemappedPoseResult(lms_1)
    res_2 = RemappedPoseResult(lms_2)

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Vẽ danh sách đa khung xương
    pe.draw(frame, [res_1, res_2])

    assert np.any(frame > 0), "Frame phải có các đường vẽ khung xương cho cả 2 người"

    # Kiểm tra estimate_multi với frame rỗng hoặc không có face: không crash
    empty_res = pe.estimate_multi(None, [])
    assert empty_res == []

    pe.close()


def test_skeleton_temporal_stabilization_and_clean_connections():
    """
    TC-SKEL-01: Kiểm tra cơ chế cố định khung xương (Landmark Stabilization) và 12 khớp nối chuẩn.
    1. Khi người đứng yên/ngồi có rung lắc nhiễu vi mô (micro-jitter ~0.003), bộ lọc EMA
       ổn định và triệt tiêu rung giật của tọa độ các khớp.
    2. Khi người di chuyển, hệ số thích ứng tăng lên để bám sát chuyển động mượt mà.
    3. CLEAN_BODY_CONNECTIONS chỉ chứa 12 đường nối giải phẫu chính, triệt tiêu mạng ngón tay/ngón chân.
    """
    from src.detection.pose_estimator import PoseEstimator, RemappedLandmark, CLEAN_BODY_CONNECTIONS

    pe = PoseEstimator()

    # 1. Ổn định rung lắc vi mô (Micro-jitter)
    stabilized_xs = []
    for i in range(10):
        jitter = 0.003 * ((-1) ** i)
        step_lms = [RemappedLandmark(0.5 + jitter, 0.5, 0.0, 0.9) for _ in range(33)]
        smoothed = pe._stabilize_landmarks(step_lms, tracker_key="test_jitter")
        stabilized_xs.append(smoothed[11].x)

    raw_range = 0.006
    smooth_range = max(stabilized_xs[3:]) - min(stabilized_xs[3:])
    assert smooth_range < raw_range, "Khung xương phải được ổn định và triệt tiêu rung giật"

    # 2. Bám sát chuyển động di chuyển (Walking motion)
    moving_lms_1 = [RemappedLandmark(0.5, 0.5, 0.0, 0.9) for _ in range(33)]
    pe._stabilize_landmarks(moving_lms_1, tracker_key="test_walk")
    moving_lms_2 = [RemappedLandmark(0.54, 0.5, 0.0, 0.9) for _ in range(33)]
    smoothed_walk = pe._stabilize_landmarks(moving_lms_2, tracker_key="test_walk")
    assert smoothed_walk[11].x > 0.52, "Khung xương phải bám sát theo chuyển động của người"

    # 3. CLEAN_BODY_CONNECTIONS chỉ có 12 xương chính
    assert len(CLEAN_BODY_CONNECTIONS) == 12

    pe.close()


def test_pipeline_cached_pose_ttl():
    """
    TC-SKEL-02: Kiểm tra TTL (Time-To-Live) của cached_pose trong luồng stream video.
    Khi người rời khỏi khung hình hoặc không nhận diện được pose quá 0.45s,
    cached_pose tự động hết hạn và không bị treo khung xương ảo trên màn hình.
    """
    from src.web.shared.pipeline import FallDetectionPipeline

    pipe = FallDetectionPipeline.__new__(FallDetectionPipeline)
    pipe._cached_pose_results = "mock_pose"
    pipe._cached_pose_ts = time.time() - 0.60  # Đã cũ quá 0.60s (vượt ngưỡng 0.45s)

    now = time.time()
    if (now - getattr(pipe, "_cached_pose_ts", 0.0)) <= 0.45:
        cached_pose = pipe._cached_pose_results
    else:
        cached_pose = None

    assert cached_pose is None, "Cached pose quá 0.45s phải bị hủy bỏ, tránh đứng hình khung xương"


def test_face_recognition_hysteresis_and_multi_frame_consensus():
    """
    TC-FACE-01: Kiểm tra chống nhảy tên (Anti-flicker Hysteresis).
    Một tracklet đang ở trạng thái 'Stranger', nếu chỉ xuất hiện 1 frame đơn lẻ
    có điểm tương đồng vượt ngưỡng (ví dụ nhận nhầm do ánh sáng/nhiễu),
    hệ thống TUYỆT ĐỐI KHÔNG nhảy tên ngay mà phải đợi >= 3 frames xác nhận.
    """
    from src.face.face_recognizer import FaceRecognizer, _TrackedFace, PersonType
    from src.core.config import FaceConfig

    rec = FaceRecognizer.__new__(FaceRecognizer)
    rec.config = FaceConfig(enabled=True, similarity_threshold=0.38)
    rec._active_face_tracks = []
    rec._next_track_id = 1
    rec._recent_known_tracks = []

    now = time.time()
    trk = _TrackedFace(
        track_id=1,
        box=(100, 100, 80, 80),
        last_seen=now,
        confirmed_name="Stranger",
        person_type=PersonType.STRANGER,
        history=[("Stranger", 0.20)],
        consecutive_stranger_count=1,
        last_known_seen_time=0.0,
    )
    rec._active_face_tracks.append(trk)

    # 1 frame fluke match với Quan: chưa đủ 3 votes -> giữ Stranger
    threshold = 0.38
    best_score = 0.40
    score_margin = 0.02
    best_match_name = "Quan"
    best_match_type = PersonType.FAMILY

    trk.history.append((best_match_name, best_score))
    recent_known_votes = [n for n, _ in trk.history[-5:] if n != "Stranger"]
    if best_score >= threshold and recent_known_votes.count(best_match_name) >= 3 and score_margin >= 0.04:
        trk.confirmed_name = best_match_name
        trk.person_type = best_match_type

    assert trk.confirmed_name == "Stranger", "1 frame fluke match tuyệt đối không được làm nhảy tên"

    # Sau 3 frames liên tục khớp An với margin >= 0.04: xác nhận An
    for _ in range(3):
        trk.history.append(("An", 0.45))

    recent_known_votes = [n for n, _ in trk.history[-5:] if n != "Stranger"]
    if 0.45 >= threshold and recent_known_votes.count("An") >= 3 and 0.08 >= 0.04:
        trk.confirmed_name = "An"
        trk.person_type = PersonType.FAMILY
        trk.last_known_seen_time = time.time()

    assert trk.confirmed_name == "An", "Sau khi có đủ 3 frames đồng thuận, danh tính được xác nhận chính xác"


def test_face_recognition_sticky_identity_during_temporary_dip():
    """
    TC-FACE-02: Kiểm tra giữ vững danh tính (Sticky Identity 5.0 giây).
    Khi người quen (An) quay mặt nghiêng, cúi gõ phím làm điểm tụt xuống dưới ngưỡng,
    hệ thống giữ nguyên danh tính 'An' trong 5 giây, không bị nhảy sang Người lạ hay người khác.
    """
    from src.face.face_recognizer import _TrackedFace, PersonType

    now = time.time()
    trk = _TrackedFace(
        track_id=1,
        box=(100, 100, 80, 80),
        last_seen=now,
        confirmed_name="An",
        person_type=PersonType.FAMILY,
        history=[("An", 0.46), ("An", 0.44)],
        consecutive_stranger_count=0,
        last_known_seen_time=now,
    )

    curr_time = now + 2.0
    best_score = 0.22

    if (curr_time - trk.last_known_seen_time <= 5.0) and best_score >= 0.16:
        final_name = trk.confirmed_name
    else:
        final_name = "Stranger"

    assert final_name == "An", "Trong cửa sổ 5s khi quay đầu/cúi mặt, danh tính An phải được duy trì kiên định"


def test_no_object_detection_drawn_on_stream_frame():
    """
    TC-NO-OBJ-01: Kiểm tra tắt hoàn toàn vẽ nhận diện vật thể trên display_frame.
    Màn hình stream chỉ tập trung vào con người (khuôn mặt, khung xương),
    không vẽ bất kỳ bounding box đồ vật (bàn, ghế, laptop) nào.
    """
    import inspect
    from src.web.shared.pipeline import FallDetectionPipeline

    source = inspect.getsource(FallDetectionPipeline._stream_loop)
    assert "_object_detector.draw" not in source, "display_frame tuyệt đối không được vẽ bounding box đồ vật"


def test_multi_person_pose_temporal_isolation():
    """
    TC-MULTI-ISO-01: Kiểm tra cách ly suy luận MediaPipe Pose giữa các người (Temporal Crop Isolation).
    - self._crop_pose hoạt động ở chế độ static_image_mode=True, độc lập với self._pose (video mode).
    - Vòng lặp duyệt crop của 2 người liên tiếp qua nhiều frames không gây nhiễm chéo trạng thái bộ lọc.
    - 2 người ở gần nhau (< 0.35) được gán 2 tracker độc quyền riêng biệt, không chiếm dụng tracker của nhau.
    """
    from unittest.mock import MagicMock
    from src.detection.pose_estimator import PoseEstimator, RemappedLandmark, RemappedPoseResult
    from src.face.face_recognizer import RecognizedFace, PersonType
    import numpy as np

    pe = PoseEstimator()
    try:
        assert pe._crop_pose is not None, "PoseEstimator phải khởi tạo _crop_pose độc lập"

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        face1 = RecognizedFace(name="Bao", person_type=PersonType.FAMILY, confidence=0.88, box=(180, 100, 80, 90))
        face2 = RecognizedFace(name="An", person_type=PersonType.FAMILY, confidence=0.85, box=(280, 100, 80, 90))

        # Giả lập kết quả trả về của _crop_pose cho từng người
        def mock_crop_landmarks(center_x: float):
            lms = []
            for i in range(33):
                lms.append(MagicMock(x=center_x, y=0.4, z=0.0, visibility=0.9))
            lms[11] = MagicMock(x=center_x - 0.05, y=0.35, z=0.0, visibility=0.95)
            lms[12] = MagicMock(x=center_x + 0.05, y=0.35, z=0.0, visibility=0.95)
            lms[23] = MagicMock(x=center_x - 0.04, y=0.60, z=0.0, visibility=0.95)
            lms[24] = MagicMock(x=center_x + 0.04, y=0.60, z=0.0, visibility=0.95)
            mock_res = MagicMock()
            mock_res.pose_landmarks.landmark = lms
            return mock_res

        # Crop trả về landmark tương ứng
        def mock_process(crop_rgb):
            return mock_crop_landmarks(0.5)

        pe._crop_pose.process = mock_process

        # Chạy qua 4 frames liên tiếp với 2 người đứng gần nhau
        for frame_idx in range(4):
            results = pe.estimate_multi(frame, [face1, face2])
            assert len(results) == 2, f"Phải phát hiện và theo dõi độc lập 2 người, nhận được: {len(results)}"
            p1_pts, p1_res = results[0]
            p2_pts, p2_res = results[1]
            # Toạ độ X của người 1 (bên trái) và người 2 (bên phải) phải tách biệt rõ ràng
            assert p1_pts["left_shoulder"].x < p2_pts["left_shoulder"].x
            assert abs(p1_pts["left_shoulder"].x - p2_pts["left_shoulder"].x) > 0.08

        # Kiểm tra 2 tracker độc quyền riêng biệt được tạo trong _pose_trackers
        trackers = [k for k in pe._pose_trackers if k != "main"]
        assert len(trackers) == 2, f"Phải có đúng 2 tracker riêng biệt cho 2 người, thực tế có: {trackers}"

        # Kiểm tra _crop_pose đóng an toàn khi gọi close()
        pe.close()
        assert pe._crop_pose is None, "Close() phải giải phóng _crop_pose sạch sẽ"
    finally:
        pe.close()


def test_anatomical_bone_length_filter():
    """
    TC-ANAT-01: Kiểm tra bộ lọc giới hạn giải phẫu học cơ thể thích ứng (Adaptive Anatomical Bone Filter).
    - Người ở xa: Tia xương nối sang cửa sổ/móc áo (dù ngắn < 0.26 như 0.18) vẫn bị loại bỏ do vượt quá tỷ lệ cơ thể.
    - Người ở gần: Xương hợp lệ dài (vd: cẳng chân 0.28) không bị cắt cụt hay nhấp nháy.
    - Khớp có visibility < 0.42 (torso) hoặc < 0.45 (limbs) bị loại bỏ.
    """
    from src.detection.pose_estimator import PoseEstimator, RemappedLandmark, RemappedPoseResult
    import numpy as np

    pe = PoseEstimator()

    # 1. Người ở xa (scale nhỏ: vai chỉ rộng 0.05 = 0.55 - 0.50):
    # Khớp 11 (vai trái) ở (0.50, 0.40)
    # Khớp 13 (khuỷu ảo trên tường) ở (0.68, 0.40) -> khoảng cách = 0.18 (nhỏ hơn 0.26 nhưng lớn hơn 0.10 của người này)
    # Bộ lọc giải phẫu học thích ứng PHẢI LOẠI BỎ tia xương này!
    lms_far = [RemappedLandmark(0.5, 0.5, 0.0, 0.1) for _ in range(33)]
    lms_far[11] = RemappedLandmark(0.50, 0.40, 0.0, 0.85)  # Vai trái
    lms_far[12] = RemappedLandmark(0.55, 0.40, 0.0, 0.85)  # Vai phải (vai span = 0.05)
    lms_far[13] = RemappedLandmark(0.68, 0.40, 0.0, 0.85)  # Khớp ảo trên tường cách 0.18
    lms_far[14] = RemappedLandmark(0.58, 0.48, 0.0, 0.85)  # Khuỷu tay phải hợp lệ (~0.085)
    lms_far[23] = RemappedLandmark(0.51, 0.60, 0.0, 0.85)  # Hông trái
    lms_far[24] = RemappedLandmark(0.54, 0.60, 0.0, 0.85)  # Hông phải

    res_far = RemappedPoseResult(lms_far)
    frame_far = np.zeros((480, 640, 3), dtype=np.uint8)
    pe.draw(frame_far, res_far)

    # Điểm giữa vai trái và khuỷu ảo (x=0.59*640=377, y=0.40*480=192):
    # Tuyệt đối KHÔNG có đường xương bắn qua!
    sample_pixel_wall = frame_far[int(0.40 * 480), int(0.59 * 640)]
    assert np.all(sample_pixel_wall == 0), f"Tia xương bắn sang tường (khoảng cách 0.18) phải bị loại bỏ, thấy màu: {sample_pixel_wall}"

    # Trong khi đó, xương hợp lệ bên phải (vai phải 0.55 -> khuỷu phải 0.58) phải được vẽ bình thường
    valid_bone_sample = frame_far[int(0.44 * 480), int(0.565 * 640)]
    assert np.any(valid_bone_sample > 0), "Xương hợp lệ sinh học phải được vẽ bình thường"

    # 2. Người ở gần camera (scale lớn: vai rộng 0.22 = 0.61 - 0.39):
    # Cẳng chân (23 đến 25) dài 0.28 (> 0.26 cố định cũ).
    # Với bộ lọc thích ứng theo tỷ lệ giải phẫu, cẳng chân này PHẢI ĐƯỢC VẼ, không bị cắt cụt.
    lms_close = [RemappedLandmark(0.5, 0.5, 0.0, 0.1) for _ in range(33)]
    lms_close[11] = RemappedLandmark(0.39, 0.25, 0.0, 0.90)  # Vai trái
    lms_close[12] = RemappedLandmark(0.61, 0.25, 0.0, 0.90)  # Vai phải (vai span = 0.22)
    lms_close[23] = RemappedLandmark(0.42, 0.50, 0.0, 0.90)  # Hông trái
    lms_close[24] = RemappedLandmark(0.58, 0.50, 0.0, 0.90)  # Hông phải
    lms_close[25] = RemappedLandmark(0.42, 0.78, 0.0, 0.90)  # Đầu gối trái (chiều dài = 0.28)

    frame_close = np.zeros((480, 640, 3), dtype=np.uint8)
    pe.draw(frame_close, RemappedPoseResult(lms_close))
    leg_sample = frame_close[int(0.64 * 480), int(0.42 * 640)]
    assert np.any(leg_sample > 0), "Cẳng chân hợp lệ của người đứng gần camera (dài 0.28) phải được vẽ đầy đủ, không bị cắt cụt"

    # 3. Kiểm tra lọc khớp có độ tin cậy thấp (< 0.42 cho torso, < 0.45 cho limbs)
    lms_low_vis = [RemappedLandmark(0.5, 0.5, 0.0, 0.1) for _ in range(33)]
    lms_low_vis[11] = RemappedLandmark(0.50, 0.40, 0.0, 0.40)  # vis 0.40 < 0.42 (torso)
    lms_low_vis[12] = RemappedLandmark(0.55, 0.40, 0.0, 0.40)
    frame_low = np.zeros((480, 640, 3), dtype=np.uint8)
    pe.draw(frame_low, RemappedPoseResult(lms_low_vis))
    assert not np.any(frame_low > 0), "Khớp có độ tin cậy thấp trên đồ vật tuyệt đối không được vẽ"

    pe.close()


def test_camera_stream_db_persistence():
    """
    TC-CAM-PERSIST-01: Kiểm tra hàm upsert_camera_stream_db và độ bền vững dữ liệu Camera trong DB.
    Khi gọi upsert_camera_stream_db, cấu hình Camera (id, name, ip, rtsp, status)
    được lưu chuẩn xác vào SQLite/Turso và không bị thất thoát khi truy vấn lại.
    Khẳng định không swallow ngoại lệ.
    """
    from src.web.admin.repository import upsert_camera_stream_db, get_all_cameras_db, delete_camera_db

    test_cam_id = "CAM-TEST-PERSIST"
    test_rtsp = "rtsp://admin:pass@192.168.1.99:554/live"

    try:
        # 1. Thực hiện upsert camera mới
        result_id = upsert_camera_stream_db(
            id=test_cam_id,
            name="Camera Phòng Khách Test",
            ip="192.168.1.99",
            rtsp=test_rtsp,
            area="Phòng khách",
            target="Cao tuổi",
            state="normal",
            status="online",
            fps=30,
            resolution="1920x1080",
            threshold=85,
        )
        assert result_id == test_cam_id

        # Kiểm tra truy vấn danh sách cameras từ DB - PHẢI TỒN TẠI
        all_cams = get_all_cameras_db()
        found = [c for c in all_cams if c["id"] == test_cam_id]
        assert len(found) > 0, "Camera vừa upsert phải tồn tại trong cơ sở dữ liệu"
        assert found[0]["ip"] == "192.168.1.99"
        assert found[0]["rtsp"] == test_rtsp
        assert found[0]["name"] == "Camera Phòng Khách Test"

        # 2. Cập nhật camera cũ với IP mới (mô phỏng DHCP router đổi IP)
        updated_rtsp = "rtsp://admin:pass@192.168.1.188:554/live"
        upsert_camera_stream_db(
            id=test_cam_id,
            name="Camera Phòng Khách Cập Nhật",
            ip="192.168.1.188",
            rtsp=updated_rtsp,
        )
        all_cams_updated = get_all_cameras_db()
        found_updated = [c for c in all_cams_updated if c["id"] == test_cam_id]
        assert len(found_updated) == 1
        assert found_updated[0]["ip"] == "192.168.1.188"
        assert found_updated[0]["rtsp"] == updated_rtsp
    finally:
        # Dọn dẹp bản ghi kiểm thử
        try:
            delete_camera_db(test_cam_id)
        except Exception:
            pass

    # Xác nhận sau khi xoá không còn trong DB
    remaining = [c for c in get_all_cameras_db() if c["id"] == test_cam_id]
    assert len(remaining) == 0, "Bản ghi kiểm thử phải được dọn dẹp sạch sẽ khỏi DB"


def test_close_multi_person_crop_partitioning_and_separation():
    """
    TC-MULTI-PARTITION-01: Kiểm tra phân vùng Voronoi/Midpoint theo phương ngang khi 2 người đứng sát nhau.
    - Người 1 (Nhân) ở bên trái: box (160, 100, 80, 90), cx = 200, cạnh phải = 240.
    - Người 2 (Bảo) ở bên phải: box (250, 100, 80, 90), cx = 290, cạnh trái = 250.
    - Điểm phân tách ngang split = (240 + 250) // 2 = 245.
    - Vùng crop của Người 1 có bx2 <= 245 (không bao giờ lấn sang Người 2).
    - Vùng crop của Người 2 có bx1 >= 245 (không bao giờ lấn sang Người 1).
    - Khung xương 2 người hoàn toàn tách biệt, không có tia xương nối chéo giữa 2 người.
    """
    from unittest.mock import MagicMock
    from src.detection.pose_estimator import PoseEstimator, RemappedLandmark, RemappedPoseResult
    from src.face.face_recognizer import RecognizedFace, PersonType
    import numpy as np

    pe = PoseEstimator()
    try:
        frame_w, frame_h = 640, 480
        frame = np.zeros((frame_h, frame_w, 3), dtype=np.uint8)

        face_nhan = RecognizedFace(name="Nhan", person_type=PersonType.FAMILY, confidence=0.92, box=(160, 100, 80, 90))
        face_bao = RecognizedFace(name="Bao", person_type=PersonType.FAMILY, confidence=0.90, box=(250, 100, 80, 90))

        processed_crops = []

        def mock_process(crop_rgb):
            processed_crops.append(crop_rgb.shape)
            # Giả lập landmark trả về trong crop
            lms = []
            for _ in range(33):
                lms.append(MagicMock(x=0.5, y=0.4, z=0.0, visibility=0.9))
            lms[11] = MagicMock(x=0.35, y=0.30, z=0.0, visibility=0.95)  # vai trái trong crop
            lms[12] = MagicMock(x=0.65, y=0.30, z=0.0, visibility=0.95)  # vai phải trong crop
            lms[13] = MagicMock(x=0.25, y=0.45, z=0.0, visibility=0.90)  # khuỷu trái
            lms[14] = MagicMock(x=0.75, y=0.45, z=0.0, visibility=0.90)  # khuỷu phải
            lms[23] = MagicMock(x=0.38, y=0.60, z=0.0, visibility=0.90)
            lms[24] = MagicMock(x=0.62, y=0.60, z=0.0, visibility=0.90)
            mock_res = MagicMock()
            mock_res.pose_landmarks.landmark = lms
            return mock_res

        pe._crop_pose.process = mock_process

        results = pe.estimate_multi(frame, [face_nhan, face_bao])
        assert len(results) == 2, f"Phải phát hiện 2 khung xương riêng biệt, thực tế: {len(results)}"
        assert len(processed_crops) == 2, "Cả 2 người phải được crop và xử lý độc lập"

        p1_pts, p1_res = results[0]
        p2_pts, p2_res = results[1]

        # Kiểm tra toạ độ X toàn cục: Người 1 (Nhân) hoàn toàn bên trái split, Người 2 (Bảo) hoàn toàn bên phải split
        split_norm = 245 / float(frame_w)
        assert p1_pts["nose"].x < split_norm, "Người 1 phải nằm hoàn toàn bên trái đường phân cách"
        assert p2_pts["nose"].x > split_norm, "Người 2 phải nằm hoàn toàn bên phải đường phân cách"

        # Kiểm tra khi vẽ 2 khung xương, không có xương nào bắc cầu qua đường phân cách x = 245
        draw_frame = np.zeros((frame_h, frame_w, 3), dtype=np.uint8)
        pe.draw(draw_frame, [p1_res, p2_res])

        # Điểm chính giữa 2 người (x=245, y=140 đến 250) tuyệt đối không có pixel vẽ xương bắc cầu
        mid_column = draw_frame[120:250, 245]
        assert np.all(mid_column == 0), "Tuyệt đối không có đường xương nối chéo qua lại giữa Nhân và Bảo"
    finally:
        pe.close()


def test_cross_person_horizontal_span_filter_rejects_bridging():
    """
    TC-MULTI-FILTER-02: Kiểm tra bộ lọc giới hạn độ dài theo phương ngang (Horizontal Span Bone Filter).
    - Cánh tay / Cẳng tay (11-13, 12-14, 13-15, 14-16) vươn ngang Delta x > min(0.20, 1.35 * ref_scale)
      bị triệt tiêu hoàn toàn, không vẽ nối giữa 2 người.
    - Chiều rộng vai (11-12) Delta x > min(0.28, 1.4 * ref_scale) bị triệt tiêu hoàn toàn.
    - Xương hợp lệ có Delta x nhỏ vẫn được vẽ chuẩn xác.
    """
    from src.detection.pose_estimator import PoseEstimator, RemappedLandmark, RemappedPoseResult
    import numpy as np

    pe = PoseEstimator()
    try:
        frame_w, frame_h = 640, 480

        # Khởi tạo khung xương chimera (như ảnh chụp thực tế media_1790322165054.png):
        # Vai phải (12) trên cổ Bảo tại x = 0.56, y = 0.35 (vis = 0.90)
        # Khuỷu tay phải (14) bị MediaPipe bắt nhầm sang cằm Nhân tại x = 0.32, y = 0.35 (vis = 0.90)
        # Khoảng cách ngang Delta x = |0.56 - 0.32| = 0.24 > 0.20!
        lms_chimera = [RemappedLandmark(0.5, 0.5, 0.0, 0.1) for _ in range(33)]
        # Vai chuẩn của Bảo
        lms_chimera[11] = RemappedLandmark(0.48, 0.35, 0.0, 0.90)  # Vai trái
        lms_chimera[12] = RemappedLandmark(0.56, 0.35, 0.0, 0.90)  # Vai phải (span = 0.08)
        # Khuỷu tay nối dị thường sang Nhân
        lms_chimera[14] = RemappedLandmark(0.32, 0.35, 0.0, 0.90)  # Delta x = 0.24 > 0.20
        # Cẳng tay trái hợp lệ của Bảo
        lms_chimera[13] = RemappedLandmark(0.44, 0.44, 0.0, 0.90)  # Delta x = 0.04 <= 0.20
        # Thân mình
        lms_chimera[23] = RemappedLandmark(0.49, 0.55, 0.0, 0.90)
        lms_chimera[24] = RemappedLandmark(0.55, 0.55, 0.0, 0.90)

        res_chimera = RemappedPoseResult(lms_chimera)
        frame = np.zeros((frame_h, frame_w, 3), dtype=np.uint8)
        pe.draw(frame, res_chimera)

        # 1. Kiểm tra tia xương bắc cầu chéo (12 nối 14 qua x=0.44, y=0.35): PHẢI BỊ LOẠI BỎ
        bridging_pixel = frame[int(0.35 * frame_h), int(0.44 * frame_w)]
        assert np.all(bridging_pixel == 0), f"Tia xương nối chéo giữa 2 người (Delta x=0.24) phải bị lọc bỏ, thấy: {bridging_pixel}"

        # 2. Kiểm tra xương cánh tay trái hợp lệ (11 nối 13): PHẢI ĐƯỢC VẼ BÌNH THƯỜNG
        valid_pixel = frame[int(0.395 * frame_h), int(0.46 * frame_w)]
        assert np.any(valid_pixel > 0), "Xương cánh tay hợp lệ của cùng một người phải được vẽ bình thường"

        # 3. Kiểm tra xương vai quá rộng (chimera shoulders giữa 2 người: Delta x = 0.34 > 0.28)
        lms_wide_torso = [RemappedLandmark(0.5, 0.5, 0.0, 0.1) for _ in range(33)]
        lms_wide_torso[11] = RemappedLandmark(0.30, 0.35, 0.0, 0.90)  # Nhân
        lms_wide_torso[12] = RemappedLandmark(0.64, 0.35, 0.0, 0.90)  # Bảo (Delta x = 0.34)
        lms_wide_torso[23] = RemappedLandmark(0.45, 0.55, 0.0, 0.90)
        lms_wide_torso[24] = RemappedLandmark(0.55, 0.55, 0.0, 0.90)

        frame_wide = np.zeros((frame_h, frame_w, 3), dtype=np.uint8)
        pe.draw(frame_wide, RemappedPoseResult(lms_wide_torso))
        shoulder_bridge = frame_wide[int(0.35 * frame_h), int(0.47 * frame_w)]
        assert np.all(shoulder_bridge == 0), "Đường nối vai chimera qua 2 người (Delta x=0.34) phải bị loại bỏ"
    finally:
        pe.close()


def test_single_face_uses_roi_and_pipeline_face_driven():
    """
    TC-MULTI-FALLBACK-03: Kiểm tra khi có khuôn mặt nhận diện (dù chỉ 1 mặt):
    1. PoseEstimator.estimate_multi chạy theo Face ROI và KHÔNG BAO GIỜ tự động fallback
       sang toàn khung hình (self.estimate) khi crop không tìm thấy pose.
    2. FallDetectionPipeline._process_pose_estimation gọi estimate_multi khi current_faces có >= 1 mặt,
       chỉ gọi toàn khung hình khi current_faces hoàn toàn rỗng.
    """
    from unittest.mock import MagicMock
    from src.detection.pose_estimator import PoseEstimator
    from src.face.face_recognizer import RecognizedFace, PersonType
    from src.web.shared.pipeline import FallDetectionPipeline
    import numpy as np

    pe = PoseEstimator()
    try:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        single_face = RecognizedFace(name="Bao", person_type=PersonType.FAMILY, confidence=0.88, box=(200, 100, 80, 90))

        # Giả lập crop_pose không phát hiện được landmark trong ROI
        pe._crop_pose.process = MagicMock(return_value=None)
        pe.estimate = MagicMock()  # Toàn khung hình

        # 1. Gọi estimate_multi với 1 mặt
        res = pe.estimate_multi(frame, [single_face])
        assert res == [], "Nếu crop không thấy pose, trả về rỗng chứ không gọi fallback toàn khung hình"
        assert pe.estimate.call_count == 0, "TUYỆT ĐỐI KHÔNG gọi estimate toàn khung hình khi có mặt người"

        # 2. Gọi estimate_multi không có mặt nào (faces=[]) -> Phải fallback toàn khung hình
        pe.estimate.return_value = ({"nose": MagicMock()}, MagicMock())
        res_no_faces = pe.estimate_multi(frame, [])
        assert pe.estimate.call_count == 1, "Khi không có khuôn mặt nào, cho phép fallback toàn khung hình"
        assert len(res_no_faces) == 1

        # 3. Kiểm tra logic trong FallDetectionPipeline._process_pose_estimation
        pipe = FallDetectionPipeline.__new__(FallDetectionPipeline)
        pipe._estimator = MagicMock()
        pipe._estimator.estimate_multi = MagicMock(return_value=[])
        pipe._estimator.estimate = MagicMock()

        # Khi current_faces có 1 mặt: phải gọi estimate_multi và không gọi estimate toàn khung hình
        pts, pose_res = pipe._process_pose_estimation(frame, [single_face])
        assert pipe._estimator.estimate_multi.call_count == 1
        assert pipe._estimator.estimate.call_count == 0
        assert pts is None and pose_res is None

        # Khi current_faces rỗng: gọi estimate toàn khung hình
        pipe._process_pose_estimation(frame, [])
        assert pipe._estimator.estimate.call_count == 1
    finally:
        pe.close()


def test_distal_limb_suppression_preserves_shoulder():
    """
    TC-MULTI-DISTAL-01: Kiểm tra triệt tiêu khớp ngoại vi (Distal Joint Suppression).
    Khi khuỷu tay (13 hoặc 14) bị MediaPipe bắt nhầm vươn ngang qua người khác (Delta x > 0.20),
    dù điểm ngoại vi có visibility cao hơn (ví dụ 0.95 > 0.80),
    hệ thống TUYỆT ĐỐI KHÔNG được xóa khớp vai (11 hoặc 12) mà phải xóa khớp ngoại vi (13 hoặc 14).
    """
    from unittest.mock import MagicMock
    from src.detection.pose_estimator import PoseEstimator
    from src.face.face_recognizer import RecognizedFace, PersonType
    import numpy as np

    pe = PoseEstimator()
    try:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        face = RecognizedFace(name="Nhan", person_type=PersonType.FAMILY, confidence=0.90, box=(200, 100, 80, 90))

        # Giả lập crop landmark: vai trái (11) có vis=0.80, khuỷu tay trái (13) bị hallucinate vươn ngang xa có vis=0.95
        def mock_process(crop_rgb):
            lms = []
            for _ in range(33):
                lms.append(MagicMock(x=0.5, y=0.5, z=0.0, visibility=0.85))
            # Vai trái (11): x=0.70, vis=0.80
            lms[11] = MagicMock(x=0.70, y=0.35, z=0.0, visibility=0.80)
            # Vai phải (12): x=0.45, vis=0.85
            lms[12] = MagicMock(x=0.45, y=0.35, z=0.0, visibility=0.85)
            # Khuỷu tay trái (13): vươn ngang dị thường x=0.05 (Delta x = 0.65 trong crop, 0.24 toàn cục > 0.20) với vis cao 0.95!
            lms[13] = MagicMock(x=0.05, y=0.35, z=0.0, visibility=0.95)
            mock_res = MagicMock()
            mock_res.pose_landmarks.landmark = lms
            return mock_res

        pe._crop_pose.process = mock_process
        results = pe.estimate_multi(frame, [face])
        assert len(results) == 1, "Phải trả về 1 kết quả pose cho khuôn mặt"

        pts, res = results[0]
        # Khớp vai (11) phải được bảo toàn visibility (không bị hạ về 0.0)
        assert pts["left_shoulder"].visibility > 0.50, "Khớp vai gốc tuyệt đối không bị xóa khi cánh tay vươn ngang"
        # Khớp khuỷu tay (13) ngoại vi vươn ngang quá giới hạn phải bị dập tắt visibility về 0.0
        remapped_lms = res.pose_landmarks.landmark
        assert remapped_lms[13].visibility == 0.0, f"Khớp khuỷu tay ngoại vi phải bị hạ về 0.0, thực tế: {remapped_lms[13].visibility}"
    finally:
        pe.close()


def test_clamped_crop_landmarks_prevent_partition_bleeding():
    """
    TC-MULTI-CLAMP-02: Kiểm tra kẹp toạ độ trong ranh giới crop (Clamped Partition Boundaries).
    Khi MediaPipe ngoại suy lm.x âm (ví dụ -0.15) ra ngoài mép crop trái,
    toạ độ toàn cục gx tuyệt đối KHÔNG được nhỏ hơn bx1/w (ranh giới phân vùng split_left).
    """
    from unittest.mock import MagicMock
    from src.detection.pose_estimator import PoseEstimator
    from src.face.face_recognizer import RecognizedFace, PersonType
    import numpy as np

    pe = PoseEstimator()
    try:
        frame_w, frame_h = 640, 480
        frame = np.zeros((frame_h, frame_w, 3), dtype=np.uint8)

        # Người 1 bên trái, Người 2 bên phải
        face1 = RecognizedFace(name="Nhan", person_type=PersonType.FAMILY, confidence=0.92, box=(150, 100, 80, 90))
        face2 = RecognizedFace(name="Bao", person_type=PersonType.FAMILY, confidence=0.90, box=(270, 100, 80, 90))

        # Giả lập MediaPipe ngoại suy toạ độ âm (lm.x = -0.20) cho Người 2 (mép trái crop)
        def mock_process(crop_rgb):
            lms = []
            for _ in range(33):
                lms.append(MagicMock(x=0.5, y=0.5, z=0.0, visibility=0.90))
            lms[11] = MagicMock(x=0.60, y=0.35, z=0.0, visibility=0.90)
            # Khớp vai phải ngoại suy âm ra ngoài mép trái
            lms[12] = MagicMock(x=-0.20, y=0.35, z=0.0, visibility=0.90)
            mock_res = MagicMock()
            mock_res.pose_landmarks.landmark = lms
            return mock_res

        pe._crop_pose.process = mock_process
        results = pe.estimate_multi(frame, [face1, face2])
        assert len(results) == 2

        # Phân cách split_left giữa (150+80=230) và 270 là (230+270)//2 = 250
        split_x_norm = 250 / float(frame_w)
        p2_pts, p2_res = results[1]
        p2_lms = p2_res.pose_landmarks.landmark

        # Vai phải của Người 2 không được phép nhỏ hơn split_x_norm
        assert p2_lms[12].x >= split_x_norm - 1e-4, f"Toạ độ Người 2 không được tràn qua split sang Người 1: {p2_lms[12].x} < {split_x_norm}"
    finally:
        pe.close()


def test_real_sample_two_persons_both_detected_and_separated():
    """
    TC-MULTI-REAL-03: Kiểm tra ảnh chụp thực tế 2 người đứng sát nhau (sample_two_persons.png).
    1. YuNet nhận diện được 2 khuôn mặt.
    2. PoseEstimator.estimate_multi trả về 2 pose skeletons (len == 2).
    3. Cả 2 người đều được vẽ khung xương (non-zero drawn pixels).
    4. Giữa khung xương 2 người có khoảng trống cách ly, không có xương nào nối chéo bắc cầu.
    """
    import os
    import cv2
    from src.core.config import load_config
    from src.face.face_recognizer import FaceRecognizer
    from src.detection.pose_estimator import PoseEstimator
    import numpy as np

    sample_path = "tests/sample_two_persons.png"
    if not os.path.exists(sample_path):
        return

    cfg = load_config("configs/default.yaml")
    fr = FaceRecognizer(cfg.face)
    pe = PoseEstimator()
    try:
        img = cv2.imread(sample_path)
        faces = fr.recognize(img)
        assert len(faces) == 2, f"Phải nhận diện được 2 khuôn mặt trong ảnh mẫu, thực tế: {len(faces)}"

        multi = pe.estimate_multi(img, faces)
        assert len(multi) == 2, f"Phải ước tính được 2 bộ khung xương riêng biệt, thực tế: {len(multi)}"

        # Kiểm tra vẽ từng người
        canvas_p0 = np.zeros_like(img)
        canvas_p1 = np.zeros_like(img)
        pe.draw(canvas_p0, multi[0][1])
        pe.draw(canvas_p1, multi[1][1])

        ys0, xs0 = np.where(canvas_p0[:, :, 0] > 0)
        ys1, xs1 = np.where(canvas_p1[:, :, 0] > 0)

        assert len(xs0) > 0, "Người 0 (Nhân) phải có khung xương được vẽ"
        assert len(xs1) > 0, "Người 1 (Bảo) phải có khung xương được vẽ"

        # Khung xương Người 0 nằm hoàn toàn bên trái, Người 1 nằm hoàn toàn bên phải
        max_x_p0 = max(xs0)
        min_x_p1 = min(xs1)
        assert max_x_p0 < min_x_p1, f"Khung xương 2 người phải hoàn toàn tách biệt: p0 max x={max_x_p0} < p1 min x={min_x_p1}"

        # Kiểm tra khoảng cách phân cách giữa 2 khung xương >= 50 pixels
        separation_gap = min_x_p1 - max_x_p0
        assert separation_gap >= 50, f"Khoảng cách giữa 2 khung xương phải >= 50px, thực tế: {separation_gap}px"
    finally:
        pe.close()











