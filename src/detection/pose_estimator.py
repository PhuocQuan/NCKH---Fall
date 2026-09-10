"""
File: src/detection/pose_estimator.py
Chức năng chính: Bao bọc (Wrapper) thư viện MediaPipe Pose.
Nhận vào một khung hình (frame), xử lý và trả về toạ độ (x, y) của các khớp xương (landmarks).

File liên kết:
- Gọi bởi: app.py, pipeline.py
"""
from __future__ import annotations

import math
from typing import Any

import cv2
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


class PoseEstimator:
    """Class bọc (Wrapper) thư viện MediaPipe Pose."""
    def __init__(
        self,
        static_image_mode: bool = False,
        model_complexity: int = 0,
        min_detection_confidence: float = 0.50,
        min_tracking_confidence: float = 0.50,
    ) -> None:
        self._mp_pose = pose
        self._drawing = drawing_utils
        self._pose = self._mp_pose.Pose(
            static_image_mode=static_image_mode,
            model_complexity=model_complexity,
            smooth_landmarks=True,
            enable_segmentation=False,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._prev_points: dict[str, Point] | None = None
        self._static_object_counter = 0

    def close(self) -> None:
        self._pose.close()

    def estimate(self, frame_bgr: Any) -> tuple[dict[str, Point] | None, Any]:
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = self._pose.process(frame_rgb)
        if not results.pose_landmarks:
            self._prev_points = None
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

        # Ngưỡng trung bình 0.22 giúp nhận diện tốt người ngã/nằm sàn mà vẫn lọc được đồ vật vô tri
        if avg_key_vis < 0.22:
            self._prev_points = None
            return None, results

        # 2. Vai và đầu: Ít nhất 1 bên vai và 1 điểm trên khuôn mặt nhận diện được
        sh_max_vis = max(points["left_shoulder"].visibility, points["right_shoulder"].visibility)
        sh_avg_vis = (points["left_shoulder"].visibility + points["right_shoulder"].visibility) / 2.0
        face_vis = [left_eye.visibility, right_eye.visibility, left_ear.visibility, right_ear.visibility]
        head_vis = max(points["nose"].visibility, max(face_vis))

        if sh_max_vis < 0.25 or sh_avg_vis < 0.18 or head_vis < 0.18:
            self._prev_points = None
            return None, results

        # Khoảng cách 2 vai theo đường chéo Euclidean - hỗ trợ khi nằm nghiêng (2 vai xếp dọc)
        shoulder_dist = math.hypot(
            points["left_shoulder"].x - points["right_shoulder"].x,
            points["left_shoulder"].y - points["right_shoulder"].y,
        )
        if shoulder_dist < 0.030:
            self._prev_points = None
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

        # Temporal EMA smoothing cho người di chuyển
        if self._prev_points is not None:
            smoothed_points = {}
            alpha = 0.65  # 65% frame hiện tại, 35% frame trước
            for key, pt in points.items():
                prev = self._prev_points[key]
                smoothed_points[key] = Point(
                    x=prev.x * (1 - alpha) + pt.x * alpha,
                    y=prev.y * (1 - alpha) + pt.y * alpha,
                    visibility=pt.visibility,
                )
            points = smoothed_points

        self._prev_points = points
        return points, results

    def draw(self, frame_bgr: Any, results: Any) -> None:
        if results and results.pose_landmarks:
            self._drawing.draw_landmarks(
                frame_bgr,
                results.pose_landmarks,
                self._mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=self._drawing.DrawingSpec(color=(0, 220, 110), thickness=2, circle_radius=3),
                connection_drawing_spec=self._drawing.DrawingSpec(color=(245, 245, 245), thickness=2),
            )
