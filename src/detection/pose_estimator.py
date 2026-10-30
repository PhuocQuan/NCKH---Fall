"""
File: src/detection/pose_estimator.py
Chức năng chính: Bao bọc (Wrapper) thư viện MediaPipe Pose.
Nhận vào một khung hình (frame), xử lý và trả về toạ độ (x, y) của các khớp xương (landmarks).

File liên kết:
- Gọi bởi: app.py, pipeline.py
"""
from __future__ import annotations

import logging
import math
import threading
import time
from typing import Any

import cv2
import src.core.protobuf_patch  # noqa: F401
import mediapipe as mp

drawing_utils = mp.solutions.drawing_utils
pose = mp.solutions.pose

from src.detection.fall_detector import Point


LANDMARK_NAMES = {
    "nose": pose.PoseLandmark.NOSE,
    "left_shoulder": pose.PoseLandmark.LEFT_SHOULDER,
    "right_shoulder": pose.PoseLandmark.RIGHT_SHOULDER,
    "left_hip": pose.PoseLandmark.LEFT_HIP,
    "right_hip": pose.PoseLandmark.RIGHT_HIP,
}

# 12 Khớp nối giải phẫu học cơ thể người chuẩn xác (loại bỏ mạng ngón tay / ngón chân gây loạn hình)
CLEAN_BODY_CONNECTIONS = [
    # Thân mình (Torso Box)
    (11, 12),  # Vai trái - Vai phải
    (11, 23),  # Vai trái - Hông trái
    (12, 24),  # Vai phải - Hông phải
    (23, 24),  # Hông trái - Hông phải
    # Cánh tay trái
    (11, 13),  # Vai trái - Khuỷu tay trái
    (13, 15),  # Khuỷu tay trái - Cổ tay trái
    # Cánh tay phải
    (12, 14),  # Vai phải - Khuỷu tay phải
    (14, 16),  # Khuỷu tay phải - Cổ tay phải
    # Chân trái
    (23, 25),  # Hông trái - Đầu gối trái
    (25, 27),  # Đầu gối trái - Cổ chân trái
    # Chân phải
    (24, 26),  # Hông phải - Đầu gối phải
    (26, 28),  # Đầu gối phải - Cổ chân phải
]


def _detect_camera_shake(points: dict[str, Point], prev_points: dict[str, Point]) -> tuple[bool, float]:
    """
    Phát hiện rung chấn vật lý của cảm biến Camera (do gió, rung giá đỡ, đóng cửa).
    Trả về (is_camera_shake, global_magnitude).
    """
    deltas = [
        (points[k].x - prev_points[k].x, points[k].y - prev_points[k].y)
        for k in points
    ]
    dxs = [d[0] for d in deltas]
    dys = [d[1] for d in deltas]

    n = len(deltas)
    mean_dx = sum(dxs) / n
    mean_dy = sum(dys) / n
    var_dx = sum((dx - mean_dx) ** 2 for dx in dxs) / n
    var_dy = sum((dy - mean_dy) ** 2 for dy in dys) / n
    motion_variance = var_dx + var_dy
    global_magnitude = math.hypot(mean_dx, mean_dy)

    is_camera_shake = (global_magnitude > 0.015) and (motion_variance < 0.00015)
    return is_camera_shake, global_magnitude


logger = logging.getLogger(__name__)


class RemappedLandmark:
    __slots__ = ("x", "y", "z", "visibility")

    def __init__(self, x: float, y: float, z: float = 0.0, visibility: float = 1.0) -> None:
        self.x = x
        self.y = y
        self.z = z
        self.visibility = visibility


class RemappedPoseLandmarks:
    __slots__ = ("landmark",)

    def __init__(self, landmark: list[RemappedLandmark]) -> None:
        self.landmark = landmark


class RemappedPoseResult:
    __slots__ = ("pose_landmarks",)

    def __init__(self, landmark: list[RemappedLandmark]) -> None:
        self.pose_landmarks = RemappedPoseLandmarks(landmark)


class PoseEstimator:
    """Class bọc (Wrapper) thư viện MediaPipe Pose với cơ chế tự phục hồi CalculatorGraph và đồng bộ đa luồng."""
    def __init__(
        self,
        static_image_mode: bool = False,
        model_complexity: int = 0,
        min_detection_confidence: float = 0.50,
        min_tracking_confidence: float = 0.50,
    ) -> None:
        self._mp_pose = pose
        self._drawing = drawing_utils
        self._static_image_mode = static_image_mode
        self._model_complexity = model_complexity
        self._min_detection_confidence = min_detection_confidence
        self._min_tracking_confidence = min_tracking_confidence
        self._lock = threading.Lock()
        self._pose: Any | None = None
        self._crop_pose: Any | None = None
        self._prev_points: dict[str, Point] | None = None
        self._static_object_counter = 0
        self._pose_trackers: dict[str, dict[str, Any]] = {}
        self._next_tracker_id: int = 1
        self._init_pose()

    @staticmethod
    def _compute_torso_center(landmarks: list[Any]) -> tuple[float, float]:
        """Tính tâm thân người dựa trên vai và hông (hoặc mũi nếu thân dưới bị che)."""
        indices = [11, 12, 23, 24]
        valid_pts = []
        for idx in indices:
            if idx < len(landmarks):
                lm = landmarks[idx]
                if getattr(lm, "visibility", 0.0) >= 0.15:
                    valid_pts.append((lm.x, lm.y))
        if valid_pts:
            return (sum(p[0] for p in valid_pts) / len(valid_pts), sum(p[1] for p in valid_pts) / len(valid_pts))
        if len(landmarks) > 0:
            return (getattr(landmarks[0], "x", 0.5), getattr(landmarks[0], "y", 0.5))
        return (0.5, 0.5)

    def _purge_old_trackers(self, max_age_seconds: float = 1.5) -> None:
        """Xoá bộ nhớ đệm của các đối tượng đã rời khỏi camera."""
        now = time.time()
        to_del = [
            k for k, v in self._pose_trackers.items()
            if k != "main" and (now - v.get("last_seen", 0.0)) > max_age_seconds
        ]
        for k in to_del:
            del self._pose_trackers[k]

    def _stabilize_landmarks(
        self,
        raw_landmarks: list[Any],
        tracker_key: str = "main",
        is_camera_shake: bool = False,
    ) -> list[RemappedLandmark]:
        """
        Ổn định toạ độ khung xương theo thời gian (Temporal Landmark Stabilization).
        Áp dụng Adaptive Exponential Moving Average (EMA) và kẹp nhiễu ngoại lai (Outlier Clamping).
        - Đứng yên / ngồi / nằm: alpha = 0.32 -> khóa cứng vị trí, triệt tiêu 100% rung lắc micro-jitter.
        - Đi lại / cử động bình thường: alpha = 0.65 -> bám sát theo chuyển động mượt mà, không bị lag.
        - Té ngã / chuyển động nhanh: alpha = 0.88 -> phản ứng tức thì với các biến động cơ thể.
        """
        if not raw_landmarks:
            return []

        now = time.time()
        center = self._compute_torso_center(raw_landmarks)

        if tracker_key not in self._pose_trackers or len(self._pose_trackers[tracker_key]["landmarks"]) != len(raw_landmarks):
            initial_lms = [
                RemappedLandmark(
                    x=float(getattr(lm, "x", 0.0)),
                    y=float(getattr(lm, "y", 0.0)),
                    z=float(getattr(lm, "z", 0.0)),
                    visibility=float(getattr(lm, "visibility", 1.0)),
                )
                for lm in raw_landmarks
            ]
            self._pose_trackers[tracker_key] = {
                "landmarks": initial_lms,
                "center": center,
                "last_seen": now,
            }
            return initial_lms

        prev_lms = self._pose_trackers[tracker_key]["landmarks"]

        # 1. Tính tốc độ dịch chuyển phần thân chính (Torso Speed S)
        torso_indices = [11, 12, 23, 24]
        displacements = []
        for idx in torso_indices:
            if idx < len(raw_landmarks) and idx < len(prev_lms):
                r_vis = float(getattr(raw_landmarks[idx], "visibility", 1.0))
                p_vis = float(getattr(prev_lms[idx], "visibility", 1.0))
                if r_vis >= 0.18 and p_vis >= 0.18:
                    d = math.hypot(raw_landmarks[idx].x - prev_lms[idx].x, raw_landmarks[idx].y - prev_lms[idx].y)
                    displacements.append(d)

        if displacements:
            torso_speed = sum(displacements) / len(displacements)
        else:
            if len(raw_landmarks) > 12 and len(prev_lms) > 12:
                torso_speed = (
                    math.hypot(raw_landmarks[11].x - prev_lms[11].x, raw_landmarks[11].y - prev_lms[11].y) +
                    math.hypot(raw_landmarks[12].x - prev_lms[12].x, raw_landmarks[12].y - prev_lms[12].y)
                ) / 2.0
            else:
                torso_speed = 0.02

        # 2. Hệ số làm mượt thích ứng (Adaptive Alpha)
        if is_camera_shake:
            alpha = 0.20
        elif torso_speed < 0.006:
            alpha = 0.32  # Khóa cứng khung xương, triệt tiêu rung giật khi ngồi/nằm/đứng yên
        elif torso_speed < 0.035:
            alpha = 0.65  # Bám sát mượt mà khi người đi lại bình thường
        else:
            alpha = 0.88  # Phản ứng tức thì khi té ngã hoặc đổi hướng nhanh

        # 3. Lọc nhiễu vọt biên (Outlier Clamping) và EMA Smoothing
        smoothed_landmarks: list[RemappedLandmark] = []
        for i in range(len(raw_landmarks)):
            lm = raw_landmarks[i]
            prev = prev_lms[i]

            curr_x = float(getattr(lm, "x", 0.0))
            curr_y = float(getattr(lm, "y", 0.0))
            curr_z = float(getattr(lm, "z", 0.0))
            curr_vis = float(getattr(lm, "visibility", 1.0))

            dx = curr_x - prev.x
            dy = curr_y - prev.y
            jump = math.hypot(dx, dy)

            # Khớp xương giật dị thường trong khi thân mình ổn định -> kẹp biên độ và dập tắt độ tin cậy ảo
            if torso_speed < 0.015 and jump > 0.16:
                clamp_scale = 0.16 / jump
                curr_x = prev.x + dx * clamp_scale
                curr_y = prev.y + dy * clamp_scale
                curr_vis = min(curr_vis, 0.30)

            smooth_x = prev.x * (1.0 - alpha) + curr_x * alpha
            smooth_y = prev.y * (1.0 - alpha) + curr_y * alpha
            smooth_z = prev.z * (1.0 - alpha) + curr_z * alpha
            smooth_vis = prev.visibility * 0.25 + curr_vis * 0.75

            smoothed_landmarks.append(
                RemappedLandmark(x=smooth_x, y=smooth_y, z=smooth_z, visibility=smooth_vis)
            )

        self._pose_trackers[tracker_key] = {
            "landmarks": smoothed_landmarks,
            "center": self._compute_torso_center(smoothed_landmarks),
            "last_seen": now,
        }
        return smoothed_landmarks

    def _init_pose(self) -> None:
        """Khởi tạo một instance MediaPipe Pose mới với CalculatorGraph sạch."""
        try:
            if self._pose is not None:
                self._pose.close()
        except Exception:
            pass
        try:
            if self._crop_pose is not None:
                self._crop_pose.close()
        except Exception:
            pass
        self._pose = self._mp_pose.Pose(
            static_image_mode=self._static_image_mode,
            model_complexity=self._model_complexity,
            smooth_landmarks=True,
            enable_segmentation=False,
            min_detection_confidence=self._min_detection_confidence,
            min_tracking_confidence=self._min_tracking_confidence,
        )
        self._crop_pose = self._mp_pose.Pose(
            static_image_mode=True,
            model_complexity=max(1, self._model_complexity),
            smooth_landmarks=False,
            enable_segmentation=False,
            min_detection_confidence=min(0.40, self._min_detection_confidence),
            min_tracking_confidence=min(0.40, self._min_tracking_confidence),
        )

    def close(self) -> None:
        """Đóng an toàn phiên làm việc của MediaPipe."""
        with self._lock:
            try:
                if self._pose is not None:
                    self._pose.close()
            except Exception:
                pass
            try:
                if self._crop_pose is not None:
                    self._crop_pose.close()
            except Exception:
                pass
            self._pose = None
            self._crop_pose = None

    def estimate(self, frame_bgr: Any) -> tuple[dict[str, Point] | None, Any]:
        if frame_bgr is None or getattr(frame_bgr, "size", 0) == 0:
            return None, None

        with self._lock:
            if self._pose is None:
                self._init_pose()

            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            try:
                results = self._pose.process(frame_rgb)
            except Exception as graph_err:
                print(f"[Pose Estimator] CalculatorGraph gặp sự cố ({graph_err}). Đang tự động khôi phục MediaPipe Pose...")
                self._init_pose()
                self._prev_points = None
                self._pose_trackers.pop("main", None)
                self._static_object_counter = 0
                return None, None

            if not results or not results.pose_landmarks:
                self._prev_points = None
                self._pose_trackers.pop("main", None)
                self._static_object_counter = 0
                return None, results

        landmarks = results.pose_landmarks.landmark
        
        nose = landmarks[pose.PoseLandmark.NOSE.value]
        left_eye = landmarks[pose.PoseLandmark.LEFT_EYE.value]
        right_eye = landmarks[pose.PoseLandmark.RIGHT_EYE.value]
        left_ear = landmarks[pose.PoseLandmark.LEFT_EAR.value]
        right_ear = landmarks[pose.PoseLandmark.RIGHT_EAR.value]

        points = {
            name: Point(
                x=landmarks[index.value].x,
                y=landmarks[index.value].y,
                visibility=landmarks[index.value].visibility,
            )
            for name, index in LANDMARK_NAMES.items()
        }

        # 1. Kiểm tra độ tin cậy trung bình của các điểm mốc cơ thể (Xác minh người thật)
        key_visibilities = [
            points["nose"].visibility,
            points["left_shoulder"].visibility,
            points["right_shoulder"].visibility,
            points["left_hip"].visibility,
            points["right_hip"].visibility,
        ]
        avg_key_vis = sum(key_visibilities) / len(key_visibilities)

        # Ngưỡng trung bình 0.16 giúp nhận diện tốt người ngã/nằm sàn mà vẫn lọc được đồ vật vô tri
        if avg_key_vis < 0.16:
            self._prev_points = None
            self._pose_trackers.pop("main", None)
            return None, results

        # 2. Vai và đầu: Ít nhất 1 bên vai có thể nhận diện được
        sh_max_vis = max(points["left_shoulder"].visibility, points["right_shoulder"].visibility)
        sh_avg_vis = (points["left_shoulder"].visibility + points["right_shoulder"].visibility) / 2.0
        face_vis = [left_eye.visibility, right_eye.visibility, left_ear.visibility, right_ear.visibility]
        head_vis = max(points["nose"].visibility, max(face_vis))

        if sh_max_vis < 0.15 or (head_vis < 0.10 and avg_key_vis < 0.20):
            self._prev_points = None
            self._pose_trackers.pop("main", None)
            return None, results

        # Khoảng cách 2 vai theo đường chéo Euclidean - hỗ trợ khi nằm nghiêng (2 vai xếp dọc)
        shoulder_dist = math.hypot(
            points["left_shoulder"].x - points["right_shoulder"].x,
            points["left_shoulder"].y - points["right_shoulder"].y,
        )
        if shoulder_dist < 0.030:
            self._prev_points = None
            self._pose_trackers.pop("main", None)
            return None, results

        # 3. Lọc đồ vật đứng yên tuyệt đối (Static Object Filter)
        # Đồ vật bất động (ghế, bàn, áo treo) có tọa độ không thay đổi dù chỉ 1 pixel qua nhiều frame
        if self._prev_points is not None:
            max_movement = max(
                abs(points[k].x - self._prev_points[k].x) + abs(points[k].y - self._prev_points[k].y)
                for k in points
            )
            if max_movement < 0.0005 and avg_key_vis < 0.60:
                self._static_object_counter += 1
                if self._static_object_counter > 60:  # Quá 2 giây tĩnh tuyệt đối với độ tin cậy thấp -> Đồ vật
                    return None, results
            else:
                self._static_object_counter = max(0, self._static_object_counter - 1)

        # 4. Lọc rung lắc cảm biến Camera & Temporal Landmark Stabilization thích ứng
        is_camera_shake = False
        if self._prev_points is not None:
            is_camera_shake, _ = _detect_camera_shake(points, self._prev_points)

        # Kế thừa dữ liệu mượt mà từ tracker multi-person gần nhất nếu "main" bị ngắt quãng
        now_ts = time.time()
        main_tracker = self._pose_trackers.get("main")
        if (main_tracker is None or (now_ts - main_tracker.get("last_seen", 0.0) > 0.8)) and len(self._pose_trackers) > 0:
            est_cx, est_cy = self._compute_torso_center(landmarks)
            best_recent = None
            best_dist = 0.30
            for k, tr in self._pose_trackers.items():
                if k == "main":
                    continue
                if now_ts - tr.get("last_seen", 0.0) <= 1.0:
                    d = math.hypot(est_cx - tr["center"][0], est_cy - tr["center"][1])
                    if d < best_dist:
                        best_dist = d
                        best_recent = tr
            if best_recent:
                self._pose_trackers["main"] = {
                    "landmarks": best_recent["landmarks"],
                    "center": best_recent["center"],
                    "last_seen": now_ts,
                }

        smoothed_lms = self._stabilize_landmarks(landmarks, tracker_key="main", is_camera_shake=is_camera_shake)
        smoothed_res = RemappedPoseResult(smoothed_lms)

        points = {
            name: Point(
                x=smoothed_lms[index.value].x,
                y=smoothed_lms[index.value].y,
                visibility=smoothed_lms[index.value].visibility,
            )
            for name, index in LANDMARK_NAMES.items()
        }

        self._prev_points = points
        return points, smoothed_res

    def estimate_multi(self, frame_bgr: Any, faces: list[Any] | None = None) -> list[tuple[dict[str, Point], Any]]:
        """
        Nhận diện khung xương cho nhiều người cùng lúc (Multi-Person Pose Estimation).
        Dựa vào vị trí khuôn mặt (YuNet), tạo vùng bao cơ thể (Body ROI) cho từng người,
        chạy MediaPipe Pose trên từng vùng và ánh xạ toạ độ về toàn khung hình.
        Áp dụng tracker độc lập theo vị trí không gian để ổn định chuyển động mượt mà cho từng người.
        Trả về danh sách [(points_person_1, pose_result_1), (points_person_2, pose_result_2), ...]
        """
        if frame_bgr is None or getattr(frame_bgr, "size", 0) == 0:
            return []

        if not faces:
            pts, res = self.estimate(frame_bgr)
            if pts and res:
                return [(pts, res)]
            return []

        self._purge_old_trackers(1.5)

        h, w = frame_bgr.shape[:2]
        multi_results: list[tuple[dict[str, Point], Any]] = []
        assigned_trackers: set[str] = set()

        with self._lock:
            if self._pose is None or self._crop_pose is None:
                self._init_pose()

            # Lọc bỏ các box khuôn mặt trùng lặp hoặc quá sát nhau của cùng 1 người
            unique_faces = []
            for face in faces:
                box = getattr(face, "box", None)
                if not box or len(box) < 4:
                    continue
                fx, fy, fw, fh = box[:4]
                if fw <= 5 or fh <= 5:
                    continue
                fcx, fcy = fx + fw / 2.0, fy + fh / 2.0
                is_dup = False
                for uf in unique_faces:
                    ubox = getattr(uf, "box", None)
                    ufcx, ufcy = ubox[0] + ubox[2] / 2.0, ubox[1] + ubox[3] / 2.0
                    if math.hypot(fcx - ufcx, fcy - ufcy) < max(fw, ubox[2]) * 0.70:
                        is_dup = True
                        break
                if not is_dup:
                    unique_faces.append(face)

            # Chuẩn bị danh sách các khuôn mặt hợp lệ và sắp xếp theo trục hoành (cx)
            face_items = []
            for face in unique_faces:
                box = getattr(face, "box", None)
                if not box or len(box) < 4:
                    continue
                fx, fy, fw, fh = box[:4]
                if fw <= 5 or fh <= 5:
                    continue
                cx = fx + fw // 2
                face_items.append((cx, fx, fy, fw, fh, face))

            face_items.sort(key=lambda item: item[0])
            num_faces = len(face_items)

            for i, (cx, fx, fy, fw, fh, face) in enumerate(face_items):
                bx1 = max(0, int(cx - 1.5 * fw))
                bx2 = min(w, int(cx + 1.5 * fw))
                by1 = max(0, int(fy - 0.3 * fh))
                by2 = min(h, int(fy + 5.0 * fh))

                # Phân vùng ngang Voronoi / Midpoint giữa các người gần nhau
                if i > 0:
                    prev_cx, prev_fx, _, prev_fw, _, _ = face_items[i - 1]
                    split_left = int((prev_fx + prev_fw + fx) // 2)
                    if split_left >= cx:
                        split_left = int((prev_cx + cx) // 2)
                    bx1 = max(bx1, split_left)

                if i + 1 < num_faces:
                    next_cx, next_fx, _, next_fw, _, _ = face_items[i + 1]
                    split_right = int((fx + fw + next_fx) // 2)
                    if split_right <= cx:
                        split_right = int((cx + next_cx) // 2)
                    bx2 = min(bx2, split_right)

                rw = bx2 - bx1
                rh = by2 - by1
                if rw < 35 or rh < 35:
                    continue

                crop_bgr = frame_bgr[by1:by2, bx1:bx2]
                crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
                try:
                    res_crop = self._crop_pose.process(crop_rgb)
                except Exception as e:
                    logger.debug("Crop pose error: %s", e)
                    continue

                if not res_crop or not res_crop.pose_landmarks:
                    continue

                crop_landmarks = res_crop.pose_landmarks.landmark
                remapped_lms: list[RemappedLandmark] = []
                for lm in crop_landmarks:
                    # Kẹp toạ độ trong phạm vi vùng crop để tránh việc ngoại suy (extrapolation)
                    # của MediaPipe làm toạ độ xương tràn qua đường ranh giới partition sang người khác
                    clamped_lm_x = max(0.0, min(1.0, lm.x))
                    clamped_lm_y = max(0.0, min(1.0, lm.y))
                    gx = (bx1 + clamped_lm_x * rw) / float(w)
                    gy = (by1 + clamped_lm_y * rh) / float(h)
                    # Nếu landmark bị MediaPipe ngoại suy quá xa khỏi vùng crop (>35%), hạ độ tin cậy để tránh vẽ khớp ma
                    lm_vis = float(getattr(lm, "visibility", 0.0))
                    if lm.x < -0.35 or lm.x > 1.35 or lm.y < -0.35 or lm.y > 1.35:
                        lm_vis = min(lm_vis, 0.15)
                    remapped_lms.append(
                        RemappedLandmark(
                            x=gx,
                            y=gy,
                            z=getattr(lm, "z", 0.0),
                            visibility=lm_vis,
                        )
                    )

                # Kiểm tra độ tin cậy vai tối thiểu
                left_sh = remapped_lms[pose.PoseLandmark.LEFT_SHOULDER.value]
                right_sh = remapped_lms[pose.PoseLandmark.RIGHT_SHOULDER.value]
                sh_max_vis = max(left_sh.visibility, right_sh.visibility)
                if sh_max_vis < 0.20:
                    continue

                # Bộ lọc Giới hạn Giải phẫu học (Anatomical Bone & Sanity Filter) thích ứng theo kích thước mặt
                fw_norm = fw / float(w)
                sh_dist = math.hypot(left_sh.x - right_sh.x, left_sh.y - right_sh.y)
                max_sh_dist = max(0.12, min(0.38, 2.8 * fw_norm))
                sh_dx = abs(left_sh.x - right_sh.x)
                if sh_dist > max_sh_dist or sh_dx > min(0.28, 2.8 * fw_norm):
                    fcx_norm = (fx + fw / 2.0) / float(w)
                    if abs(left_sh.x - fcx_norm) > abs(right_sh.x - fcx_norm):
                        left_sh.visibility = 0.0
                    else:
                        right_sh.visibility = 0.0

                max_torso_len = max(0.14, min(0.48, 3.8 * fw_norm))
                max_limb_len = max(0.10, min(0.40, 2.8 * fw_norm))
                fcx_norm = (fx + fw / 2.0) / float(w)

                for a_idx, b_idx in CLEAN_BODY_CONNECTIONS:
                    if a_idx < len(remapped_lms) and b_idx < len(remapped_lms):
                        p1 = remapped_lms[a_idx]
                        p2 = remapped_lms[b_idx]
                        b_dist = math.hypot(p1.x - p2.x, p1.y - p2.y)
                        b_dx = abs(p1.x - p2.x)
                        is_torso_bone = (a_idx in (11, 12) and b_idx in (23, 24))
                        is_arm_limb = (a_idx, b_idx) in {(11, 13), (13, 11), (12, 14), (14, 12), (13, 15), (15, 13), (14, 16), (16, 14)}
                        max_allowed = max_torso_len if is_torso_bone else max_limb_len
                        if b_dist > max_allowed or (is_arm_limb and b_dx > min(0.20, 2.8 * fw_norm)):
                            # Triệt tiêu khớp ngoại vi (distal joint) hoặc khớp xa khuôn mặt nhất.
                            # Tuyệt đối không xóa vai (shoulder anchor) khi cánh tay vươn ngang dị thường.
                            if (a_idx, b_idx) in {(11, 13), (12, 14), (13, 15), (14, 16), (23, 25), (24, 26), (25, 27), (26, 28)}:
                                p2.visibility = 0.0
                            elif (a_idx, b_idx) in {(11, 23), (12, 24)}:
                                p2.visibility = 0.0
                            else:
                                if abs(p1.x - fcx_norm) > abs(p2.x - fcx_norm):
                                    p1.visibility = 0.0
                                else:
                                    p2.visibility = 0.0

                # Ghép nối với tracker độc quyền theo vị trí không gian để ổn định chuyển động độc lập từng người
                torso_cx, torso_cy = self._compute_torso_center(remapped_lms)
                matched_key = None
                best_dist = 0.35
                for t_key, t_val in self._pose_trackers.items():
                    if t_key == "main" or t_key in assigned_trackers:
                        continue
                    tcx, tcy = t_val["center"]
                    dist = math.hypot(torso_cx - tcx, torso_cy - tcy)
                    if dist < best_dist:
                        best_dist = dist
                        matched_key = t_key

                # Kế thừa dữ liệu mượt mà từ tracker "main" khi chuyển từ chế độ 1 người sang nhiều người
                if matched_key is None and "main" in self._pose_trackers and "main" not in assigned_trackers:
                    mcx, mcy = self._pose_trackers["main"]["center"]
                    if math.hypot(torso_cx - mcx, torso_cy - mcy) < 0.25:
                        matched_key = f"person_{self._next_tracker_id}"
                        self._next_tracker_id += 1
                        self._pose_trackers[matched_key] = {
                            "landmarks": self._pose_trackers["main"]["landmarks"],
                            "center": (torso_cx, torso_cy),
                            "last_seen": time.time(),
                        }

                if matched_key is None:
                    matched_key = f"person_{self._next_tracker_id}"
                    self._next_tracker_id += 1

                assigned_trackers.add(matched_key)

                smoothed_lms = self._stabilize_landmarks(remapped_lms, tracker_key=matched_key, is_camera_shake=False)
                remapped_res = RemappedPoseResult(smoothed_lms)
                pts = {
                    name: Point(
                        x=smoothed_lms[index.value].x,
                        y=smoothed_lms[index.value].y,
                        visibility=smoothed_lms[index.value].visibility,
                    )
                    for name, index in LANDMARK_NAMES.items()
                }
                multi_results.append((pts, remapped_res))

        return multi_results

    def draw(self, frame_bgr: Any, results: Any, include_face: bool = False) -> None:
        """
        Vẽ khung xương chuẩn xác, mượt mà và trực quan:
        - 12 đường nối giải phẫu học cơ thể người chính (Torso, 2 tay, 2 chân).
        - Triệt tiêu hoàn toàn mạng ngón tay / ngón chân gây rối hình ảnh.
        - Khử răng cưa LINE_AA, viền trắng ngoài 3px và lõi xanh ngọc lục bảo 2px.
        - Khớp tròn kép nổi bật, chỉ vẽ khi độ tin cậy visibility >= 0.32.
        """
        if not results:
            return
        if isinstance(results, (list, tuple)):
            for res in results:
                self.draw(frame_bgr, res, include_face=include_face)
            return

        h, w = frame_bgr.shape[:2]
        pose_lms = getattr(results, "pose_landmarks", None)
        if not pose_lms:
            return
        landmarks = getattr(pose_lms, "landmark", None)
        if not landmarks:
            return

        body_conns = CLEAN_BODY_CONNECTIONS if not include_face else (
            CLEAN_BODY_CONNECTIONS + [
                (0, 1), (1, 2), (2, 3), (3, 7),
                (0, 4), (4, 5), (5, 6), (6, 8),
                (9, 10), (11, 12),
            ]
        )
        drawn_points = set()

        torso_pairs = {(11, 12), (12, 11), (11, 23), (23, 11), (12, 24), (24, 12), (23, 24), (24, 23)}
        face_pairs = {
            (0, 1), (1, 0), (1, 2), (2, 1), (2, 3), (3, 2), (3, 7), (7, 3),
            (0, 4), (4, 0), (4, 5), (5, 4), (5, 6), (6, 5), (6, 8), (8, 6),
            (9, 10), (10, 9)
        }

        # Ước tính quy mô tỷ lệ giải phẫu học cơ thể người (Adaptive Anatomical Scale)
        ref_scale = 0.15
        sh_found = False
        if len(landmarks) > 12:
            l_sh = landmarks[11]
            r_sh = landmarks[12]
            if getattr(l_sh, "visibility", 0.0) >= 0.25 and getattr(r_sh, "visibility", 0.0) >= 0.25:
                sh_dist = math.hypot(l_sh.x - r_sh.x, l_sh.y - r_sh.y)
                sh_dx = abs(l_sh.x - r_sh.x)
                if 0.03 <= sh_dist <= 0.45 and sh_dx <= 0.28:
                    ref_scale = sh_dist
                    sh_found = True
        if not sh_found and len(landmarks) > 24:
            l_hip = landmarks[23]
            r_hip = landmarks[24]
            if getattr(l_hip, "visibility", 0.0) >= 0.25 and getattr(r_hip, "visibility", 0.0) >= 0.25:
                hip_dist = math.hypot(l_hip.x - r_hip.x, l_hip.y - r_hip.y)
                hip_dx = abs(l_hip.x - r_hip.x)
                if 0.03 <= hip_dist <= 0.40 and hip_dx <= 0.28:
                    ref_scale = hip_dist * 1.2

        for a, b in body_conns:
            if a >= len(landmarks) or b >= len(landmarks):
                continue
            lm1 = landmarks[a]
            lm2 = landmarks[b]
            vis1 = getattr(lm1, "visibility", 0.0)
            vis2 = getattr(lm2, "visibility", 0.0)

            is_torso = (a, b) in torso_pairs
            is_face = (a, b) in face_pairs
            min_vis = 0.42 if is_torso else 0.45

            if vis1 < min_vis or vis2 < min_vis:
                continue

            # Kiểm tra giới hạn giải phẫu học cơ thể thích ứng (Adaptive Anatomical Bone Constraints)
            # Triệt tiêu các tia xương nối dị thường bắn sang nền (cửa sổ, móc áo)
            bone_dist = math.hypot(lm1.x - lm2.x, lm1.y - lm2.y)
            if is_face:
                max_bone_len = max(0.04, min(0.18, ref_scale * 0.7))
            elif (a, b) in {(11, 23), (23, 11), (12, 24), (24, 12)}:
                max_bone_len = max(0.14, min(0.48, ref_scale * 2.1))  # Chiều dọc thân mình
            elif (a, b) in {(11, 12), (12, 11), (23, 24), (24, 23)}:
                max_bone_len = max(0.08, min(0.38, ref_scale * 1.4))  # Chiều ngang vai / hông
            else:
                max_bone_len = max(0.10, min(0.42, ref_scale * 1.65))  # Tứ chi & cẳng chân
            if bone_dist > max_bone_len:
                continue

            # Chống nối chéo khung xương giữa 2 người (Inter-Person Cross-Connection Prevention)
            # Giới hạn độ dài theo phương ngang (Horizontal Delta dx):
            # Cánh tay và cẳng tay không được vươn ngang vượt quá min(0.20, 1.35 * ref_scale)
            dx = abs(lm1.x - lm2.x)
            if (a, b) in {(11, 13), (13, 11), (12, 14), (14, 12), (13, 15), (15, 13), (14, 16), (16, 14)}:
                if dx > min(0.20, 1.35 * ref_scale):
                    continue
            # Chiều ngang vai (11, 12) và hông (23, 24) không được vượt quá min(0.28, 1.4 * ref_scale)
            if (a, b) in {(11, 12), (12, 11), (23, 24), (24, 23)}:
                if dx > min(0.28, 1.4 * ref_scale):
                    continue

            x1 = int(max(0.0, min(1.0, lm1.x)) * w)
            y1 = int(max(0.0, min(1.0, lm1.y)) * h)
            x2 = int(max(0.0, min(1.0, lm2.x)) * w)
            y2 = int(max(0.0, min(1.0, lm2.y)) * h)

            # Vẽ xương: Viền trắng ngoài (3px) + Lõi xanh lá ngọc lục bảo (2px) khử răng cưa
            cv2.line(frame_bgr, (x1, y1), (x2, y2), (255, 255, 255), 3, cv2.LINE_AA)
            cv2.line(frame_bgr, (x1, y1), (x2, y2), (0, 220, 110), 2, cv2.LINE_AA)

            # Vẽ khớp tròn kép
            if a not in drawn_points:
                cv2.circle(frame_bgr, (x1, y1), 5, (255, 255, 255), -1, cv2.LINE_AA)
                cv2.circle(frame_bgr, (x1, y1), 3, (0, 200, 90), -1, cv2.LINE_AA)
                drawn_points.add(a)
            if b not in drawn_points:
                cv2.circle(frame_bgr, (x2, y2), 5, (255, 255, 255), -1, cv2.LINE_AA)
                cv2.circle(frame_bgr, (x2, y2), 3, (0, 200, 90), -1, cv2.LINE_AA)
                drawn_points.add(b)
