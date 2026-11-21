"""
File: tests/test_sensor_processing_and_object_detection.py
Chức năng: Kiểm thử tự động toàn diện các tính năng mới:
1. Xử lý cảm biến thị giác: Chuẩn hóa vận tốc bất biến khoảng cách (Scale Invariance),
   bù trừ góc nghiêng camera (Camera Pitch Compensation), và lọc rung lắc cảm biến.
2. Nhận diện vật thể & bối cảnh không gian (Object Detection & Spatial Context Fusion):
   Phân biệt nằm trên giường/ghế sofa với ngã sàn, triệt tiêu báo động giả.
"""
from pathlib import Path

import numpy as np
import pytest

from src.core.config import DetectorConfig, ObjectDetectionConfig
from src.detection.fall_detector import DetectionResult, FallDetector, FallState, Point, _angle_from_vertical
from src.detection.object_detector import (
    SAFE_CONTEXT_CLASSES,
    YOLOV8N_ONNX_MIRRORS,
    DetectedObject,
    ObjectDetector,
    compute_box_overlap,
    is_safe_context,
)
from src.detection.pose_estimator import PoseEstimator
from src.web.shared.pipeline import PipelineStatus


def _create_pose(shoulder_y: float, hip_y: float, dx: float = 0.0) -> dict[str, Point]:
    """Tạo landmarks giả lập cho phần thân trên cơ thể."""
    return {
        "nose": Point(x=0.5, y=max(0.0, shoulder_y - 0.12), visibility=0.9),
        "left_shoulder": Point(x=0.5 - dx - 0.05, y=shoulder_y, visibility=0.9),
        "right_shoulder": Point(x=0.5 - dx + 0.05, y=shoulder_y, visibility=0.9),
        "left_hip": Point(x=0.5 - 0.05, y=hip_y, visibility=0.9),
        "right_hip": Point(x=0.5 + 0.05, y=hip_y, visibility=0.9),
    }


# ==============================================================================
# 1. KIỂM THỬ XỬ LÝ CẢM BIẾN THỊ GIÁC (CAMERA SENSOR PROCESSING)
# ==============================================================================

def test_tc_sen_01_scale_invariance_far_vs_near():
    """
    TC-SEN-01: Kiểm tra tính bất biến tỷ lệ (Scale Invariance) theo khoảng cách người tới camera.
    - Người ở xa (thân người nhỏ L=0.10): Cú rơi với delta pixel nhỏ (0.012) vẫn được nhân hệ số scale
      (0.25 / 0.10 = 2.5) thành vận tốc chuẩn 0.030 >= 0.025, phát hiện chính xác cú ngã.
    - Người ở gần (thân người lớn L=0.50): Động tác ngồi xuống nhẹ (delta 0.030) được giảm hệ số scale
      (0.25 / 0.50 = 0.5) thành vận tốc chuẩn 0.015 < 0.025, ngăn ngừa báo động sai.
    """
    cfg = DetectorConfig(enable_scale_normalization=True, reference_torso_length=0.25)
    detector = FallDetector(cfg)

    # 1. Người ở xa: torso_length ~ 0.10 (từ y=0.30 đến y=0.40)
    p_far_1 = _create_pose(shoulder_y=0.30, hip_y=0.40)
    res_1 = detector.update(p_far_1)
    assert res_1.hip_velocity == 0.0

    # Frame 2: Hông rơi xuống 0.012 (nếu không scale thì < 0.025)
    p_far_2 = _create_pose(shoulder_y=0.31, hip_y=0.412)
    res_2 = detector.update(p_far_2)

    # Vận tốc chuẩn hóa phải được khuếch đại: ~ 0.012 * (0.25 / 0.10) = 0.030
    assert res_2.hip_velocity > 0.024
    assert res_2.hip_velocity > 0.012

    # 2. Người ở gần: torso_length ~ 0.50 (từ y=0.20 đến y=0.70)
    detector_near = FallDetector(cfg)
    p_near_1 = _create_pose(shoulder_y=0.20, hip_y=0.70)
    detector_near.update(p_near_1)

    # Cử động cúi/ngồi có raw delta = 0.030
    p_near_2 = _create_pose(shoulder_y=0.23, hip_y=0.730)
    res_near_2 = detector_near.update(p_near_2)

    # Vận tốc chuẩn hóa được co nhỏ: 0.030 * (0.25 / 0.50) = 0.015 < 0.025
    assert res_near_2.hip_velocity < 0.025
    assert res_near_2.hip_velocity < 0.030


def test_tc_sen_02_camera_pitch_compensation():
    """
    TC-SEN-02: Kiểm tra bù trừ góc nghiêng khi camera gắn trên cao chúc xuống.
    - Khi camera nghiêng 25 độ, người đứng thẳng có góc chiếu quang học raw ~ 20 độ.
    - Với bù trừ camera_pitch_angle_deg=25.0, góc nghiêng thực tế được hiệu chỉnh về sát 0 độ.
    """
    shoulder = Point(x=0.5, y=0.2)
    hip = Point(x=0.5, y=0.6)

    # Thân đứng thẳng hoàn toàn theo trục thẳng đứng
    raw_angle = _angle_from_vertical(shoulder, hip, camera_pitch_angle_deg=0.0)
    assert raw_angle == 0.0

    # Góc hơi xiên do góc nhìn camera chúc xuống (dx=0.10, dy=0.30 -> raw angle ~ 18.4 độ)
    shoulder_skewed = Point(x=0.4, y=0.2)
    hip_skewed = Point(x=0.5, y=0.5)

    angle_uncompensated = _angle_from_vertical(shoulder_skewed, hip_skewed, camera_pitch_angle_deg=0.0)
    angle_compensated = _angle_from_vertical(shoulder_skewed, hip_skewed, camera_pitch_angle_deg=25.0)

    # Góc bù trừ phải nhỏ hơn góc thô (giảm thiểu biến dạng góc nhìn)
    assert angle_compensated < angle_uncompensated
    assert angle_compensated >= 0.0


def test_tc_sen_03_camera_shake_rejection():
    """
    TC-SEN-03: Kiểm tra bộ lọc rung lắc cảm biến Camera trong PoseEstimator.
    - Khi có rung lắc cảm biến (tất cả các khớp cùng dịch chuyển đồng thời),
      PoseEstimator phát hiện camera shake và áp dụng alpha thấp để triệt tiêu rung giật.
    """
    estimator = PoseEstimator()

    # Khởi tạo frame đầu với điểm giả lập
    p1 = _create_pose(shoulder_y=0.4, hip_y=0.6)
    estimator._prev_points = p1

    # Tạo rung chấn giả lập: tất cả các điểm cùng bị giật x += 0.025, y += 0.020 (vector đồng dạng)
    shaken_points = {
        k: Point(x=pt.x + 0.025, y=pt.y + 0.020, visibility=pt.visibility)
        for k, pt in p1.items()
    }

    # Tính toán vector như trong pose_estimator
    deltas = [(shaken_points[k].x - p1[k].x, shaken_points[k].y - p1[k].y) for k in shaken_points]
    dxs = [d[0] for d in deltas]
    dys = [d[1] for d in deltas]
    mean_dx = sum(dxs) / len(dxs)
    mean_dy = sum(dys) / len(dys)
    var_dx = sum((dx - mean_dx) ** 2 for dx in dxs) / len(dxs)
    var_dy = sum((dy - mean_dy) ** 2 for dy in dys) / len(dys)
    motion_var = var_dx + var_dy
    global_mag = (mean_dx ** 2 + mean_dy ** 2) ** 0.5

    # Kiểm tra đặc trưng nhận diện rung camera: biên độ lớn nhưng độ biến thiên nội bộ cực nhỏ
    assert global_mag > 0.015
    assert motion_var < 0.00015

    from src.detection.pose_estimator import _detect_camera_shake
    is_shake, mag = _detect_camera_shake(shaken_points, p1)
    assert is_shake is True
    assert mag > 0.015


# ==============================================================================
# 2. KIỂM THỬ NHẬN DIỆN VẬT THỂ & NGỮ CẢNH KHÔNG GIAN (OBJECT DETECTION)
# ==============================================================================

def test_tc_obj_01_object_detector_helpers():
    """TC-OBJ-01: Kiểm tra các hàm tính toán không gian và định danh vật thể."""
    obj_bed = DetectedObject(
        label="bed",
        confidence=0.88,
        box=(100, 200, 300, 150),
        normalized_box=(0.1, 0.3, 0.6, 0.7),
    )
    assert obj_bed.display_name == "Giuong"

    obj_chair = DetectedObject(
        label="chair",
        confidence=0.92,
        box=(50, 100, 100, 120),
        normalized_box=(0.05, 0.1, 0.2, 0.3),
    )
    assert obj_chair.display_name == "Ghe"

    # Kiểm tra tính tỉ lệ giao nhau (Box Overlap)
    person_box_on_bed = (0.15, 0.35, 0.55, 0.65)  # Nằm hoàn toàn trên giường
    overlap_full = compute_box_overlap(person_box_on_bed, obj_bed.normalized_box)
    assert overlap_full == 1.0

    # Nằm lệch một nửa ra ngoài
    person_box_half = (0.5, 0.35, 0.7, 0.65)
    overlap_half = compute_box_overlap(person_box_half, obj_bed.normalized_box)
    assert 0.4 <= overlap_half <= 0.6

    # Nằm xa hoàn toàn không chạm giường
    person_box_floor = (0.7, 0.8, 0.9, 0.95)
    overlap_none = compute_box_overlap(person_box_floor, obj_bed.normalized_box)
    assert overlap_none == 0.0


def test_tc_obj_02_safe_resting_on_bed_suppresses_fall_alert():
    """
    TC-OBJ-02: Kịch bản người nằm ngang trên Giường (Bed) hoặc Sofa.
    - Tư thế nằm ngang (torso angle >= 65 độ).
    - Nhưng vị trí người trùng với Bounding Box của Giường (overlap >= 35%).
    - Kết quả: Hệ thống nhận diện SAFE_RESTING (Nghỉ ngơi an toàn), duy trì trạng thái LYING
      và TUYỆT ĐỐI KHÔNG BẬT CÒI / KHÔNG GỬI ALERT dù nằm quá thời gian alert_after_seconds.
    """
    cfg = DetectorConfig(
        torso_fall_angle_deg=58.0,
        alert_after_seconds=0.2,  # Rất ngắn để kiểm tra xem có bị báo sai không
        assumed_fps=10.0,
    )
    detector = FallDetector(cfg)

    # Giường nằm ở toạ độ chuẩn hóa [0.2, 0.2, 0.9, 0.8]
    bed_obj = DetectedObject(
        label="bed",
        confidence=0.95,
        box=(200, 200, 700, 600),
        normalized_box=(0.2, 0.2, 0.9, 0.8),
    )

    # Tư thế nằm ngang trên giường (y vai = 0.50, y hông = 0.52, x lệch ngang)
    lying_on_bed_pose = {
        "nose": Point(x=0.25, y=0.50, visibility=0.9),
        "left_shoulder": Point(x=0.35, y=0.48, visibility=0.9),
        "right_shoulder": Point(x=0.35, y=0.52, visibility=0.9),
        "left_hip": Point(x=0.65, y=0.50, visibility=0.9),
        "right_hip": Point(x=0.65, y=0.52, visibility=0.9),
    }

    # Chạy 15 frames liên tiếp (quá 1.5 giây, vượt xa alert_after_seconds = 0.2s)
    for _ in range(15):
        result = detector.update(lying_on_bed_pose, nearby_objects=[bed_obj])

    # Khẳng định: Hệ thống nhận biết safe_resting và không kích hoạt báo động
    assert result.safe_resting is True
    assert result.resting_object == "bed"
    assert result.state == FallState.LYING
    assert result.event_started is False
    assert detector._alert_active is False


def test_tc_obj_03_fall_on_floor_away_from_bed_triggers_alert():
    """
    TC-OBJ-03: Kịch bản người ngã thật ra sàn nhà trống (ngoài phạm vi của Giường).
    - Cú rơi nhanh và nằm im trên sàn nhà.
    - Kết quả: Hệ thống nhận diện safe_resting = False và kích hoạt cảnh báo té ngã đúng chuẩn.
    """
    cfg = DetectorConfig(
        torso_fall_angle_deg=58.0,
        hip_drop_velocity=0.020,
        alert_after_seconds=0.2,
        assumed_fps=10.0,
    )
    detector = FallDetector(cfg)

    # Giường ở góc trên bên trái
    bed_obj = DetectedObject(
        label="bed",
        confidence=0.95,
        box=(10, 10, 200, 200),
        normalized_box=(0.01, 0.01, 0.30, 0.30),
    )

    # Người đứng thẳng ở giữa sàn (x=0.7, y=0.3 -> 0.6)
    standing_pose = {
        "nose": Point(x=0.7, y=0.20, visibility=0.9),
        "left_shoulder": Point(x=0.65, y=0.30, visibility=0.9),
        "right_shoulder": Point(x=0.75, y=0.30, visibility=0.9),
        "left_hip": Point(x=0.65, y=0.60, visibility=0.9),
        "right_hip": Point(x=0.75, y=0.60, visibility=0.9),
    }
    detector.update(standing_pose, nearby_objects=[bed_obj])

    # Cú ngã đột ngột xuống sàn nhà (x=0.75, y=0.75)
    fall_pose = {
        "nose": Point(x=0.60, y=0.78, visibility=0.9),
        "left_shoulder": Point(x=0.68, y=0.76, visibility=0.9),
        "right_shoulder": Point(x=0.68, y=0.80, visibility=0.9),
        "left_hip": Point(x=0.88, y=0.77, visibility=0.9),
        "right_hip": Point(x=0.88, y=0.81, visibility=0.9),
    }

    alert_triggered = False
    for _ in range(10):
        res = detector.update(fall_pose, nearby_objects=[bed_obj])
        if res.event_started or res.state == FallState.ALERT:
            alert_triggered = True

    assert res.safe_resting is False
    assert alert_triggered is True


def test_tc_obj_04_detector_mock_and_draw():
    """TC-OBJ-04: Kiểm tra khả năng chạy mô phỏng và vẽ khung bounding box của ObjectDetector."""
    det = ObjectDetector(ObjectDetectionConfig(enabled=True))
    assert det.is_ready() or not Path("models/yolov8n.onnx").exists()

    # Đặt simulated objects
    mock_obj = DetectedObject(
        label="chair",
        confidence=0.91,
        box=(50, 50, 120, 150),
        normalized_box=(0.1, 0.1, 0.3, 0.4),
    )
    det.set_simulated_objects([mock_obj])
    assert det.is_ready() is True

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    detected = det.detect(frame)
    assert len(detected) == 1
    assert detected[0].label == "chair"

    # Thử vẽ lên frame
    det.draw(frame, detected)
    # Khung hình không còn đen tuyền vì đã được vẽ khung và nhãn
    assert np.sum(frame) > 0


def test_tc_obj_05_pipeline_status_serialization():
    """TC-OBJ-05: Kiểm tra PipelineStatus lưu trữ và serialize đúng trường detected_objects và safe_resting."""
    status = PipelineStatus(
        running=True,
        state="lying",
        detected_objects=["Giuong (95%)", "Ghe (88%)"],
        safe_resting=True,
        resting_object="bed",
    )
    d = status.to_dict()
    assert d["safe_resting"] is True
    assert d["resting_object"] == "bed"
    assert len(d["detected_objects"]) == 2
    assert "Giuong (95%)" in d["detected_objects"]


def test_tc_obj_06_safe_context_classes_and_helpers():
    """TC-OBJ-06: Kiểm tra mở rộng danh sách vật thể an toàn và mirror HuggingFace."""
    expected_classes = {"chair", "couch", "bed", "dining table", "laptop"}
    assert expected_classes.issubset(SAFE_CONTEXT_CLASSES)
    assert is_safe_context("chair") is True
    assert is_safe_context("couch") is True
    assert is_safe_context("bed") is True
    assert is_safe_context("dining table") is True
    assert is_safe_context("laptop") is True
    assert is_safe_context("knife") is False

    # Kiểm tra URL mirror là HuggingFace
    assert len(YOLOV8N_ONNX_MIRRORS) >= 2
    for url in YOLOV8N_ONNX_MIRRORS:
        assert "huggingface.co" in url
        assert url.endswith(".onnx")

    # Kiểm tra tên tiếng Việt của các vật thể mới
    obj_table = DetectedObject("dining table", 0.9, (10, 10, 100, 100), (0.1, 0.1, 0.5, 0.5))
    obj_laptop = DetectedObject("laptop", 0.9, (10, 10, 50, 50), (0.2, 0.2, 0.4, 0.4))
    assert obj_table.display_name == "Ban"
    assert obj_laptop.display_name == "Laptop"


def test_tc_obj_07_seated_with_desk_or_laptop_suppresses_fall():
    """TC-OBJ-07: Người ngồi làm việc trước bàn hoặc có laptop không bị báo ngã."""
    detector = FallDetector(
        DetectorConfig(
            torso_fall_angle_deg=58.0,
            alert_after_seconds=0.2,
            assumed_fps=10.0,
        )
    )

    # Bàn làm việc ở góc trước người
    table_obj = DetectedObject(
        label="dining table",
        confidence=0.92,
        box=(100, 200, 500, 400),
        normalized_box=(0.15, 0.35, 0.85, 0.85),
    )
    laptop_obj = DetectedObject(
        label="laptop",
        confidence=0.88,
        box=(200, 220, 200, 150),
        normalized_box=(0.30, 0.38, 0.60, 0.65),
    )

    # Tư thế ngồi làm việc trước bàn: vai y=0.38, hông y=0.44 (che khuất), nghiêng nhẹ
    seated_desk_pose = {
        "nose": Point(x=0.50, y=0.06, visibility=0.9),
        "left_shoulder": Point(x=0.38, y=0.38, visibility=0.9),
        "right_shoulder": Point(x=0.58, y=0.38, visibility=0.9),
        "left_hip": Point(x=0.45, y=0.44, visibility=0.9),
        "right_hip": Point(x=0.65, y=0.44, visibility=0.9),
    }

    alert_occurred = False
    for _ in range(20):  # 2.0s liên tục (> 0.2s alert timeout)
        res = detector.update(seated_desk_pose, nearby_objects=[table_obj, laptop_obj])
        if res.event_started or res.state == FallState.ALERT:
            alert_occurred = True

    assert alert_occurred is False
    assert res.state == FallState.NORMAL
    assert res.is_seated is True
    assert res.lying_seconds == 0.0


def test_tc_obj_08_download_error_handling_and_cleanup(tmp_path, monkeypatch):
    """TC-OBJ-08: Kiểm tra khi tải thất bại thì dọn dẹp file tạm và chuyển sang chế độ an toàn."""
    import urllib.error
    import urllib.request

    dummy_model = tmp_path / "models" / "yolov8n.onnx"
    dummy_model.parent.mkdir(parents=True, exist_ok=True)

    def fake_urlopen(req, timeout=3.0):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    ObjectDetector._download_failed = False

    cfg = ObjectDetectionConfig(enabled=True, model_path=str(dummy_model))
    det = ObjectDetector(cfg)

    assert det.is_ready() is False
    assert ObjectDetector._download_failed is True
    # Không để lại file rác .tmp trong thư mục models
    assert len(list(dummy_model.parent.glob("*.tmp"))) == 0
    assert not dummy_model.exists()
