from __future__ import annotations

from typing import Any

import cv2
import mediapipe as mp

drawing_utils = mp.solutions.drawing_utils
pose = mp.solutions.pose

from src.fall_detector import Point


LANDMARK_NAMES = {
    "nose": pose.PoseLandmark.NOSE,
    "left_shoulder": pose.PoseLandmark.LEFT_SHOULDER,
    "right_shoulder": pose.PoseLandmark.RIGHT_SHOULDER,
    "left_hip": pose.PoseLandmark.LEFT_HIP,
    "right_hip": pose.PoseLandmark.RIGHT_HIP,
}


class PoseEstimator:
    def __init__(
        self,
        static_image_mode: bool = False,
        model_complexity: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        self._mp_pose = pose
        self._drawing = drawing_utils
        self._pose = self._mp_pose.Pose(
            static_image_mode=static_image_mode,
            model_complexity=model_complexity,
            enable_segmentation=False,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def close(self) -> None:
        self._pose.close()

    def estimate(self, frame_bgr: Any) -> tuple[dict[str, Point] | None, Any]:
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = self._pose.process(frame_rgb)
        if not results.pose_landmarks:
            return None, results

        landmarks = results.pose_landmarks.landmark
        points = {
            name: Point(
                x=landmarks[index.value].x,
                y=landmarks[index.value].y,
                visibility=landmarks[index.value].visibility,
            )
            for name, index in LANDMARK_NAMES.items()
        }
        if any(point.visibility < 0.45 for point in points.values()):
            return None, results
        return points, results

    def draw(self, frame_bgr: Any, results: Any) -> None:
        if results.pose_landmarks:
            self._drawing.draw_landmarks(
                frame_bgr,
                results.pose_landmarks,
                self._mp_pose.POSE_CONNECTIONS,
            )
