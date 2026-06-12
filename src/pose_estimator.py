from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import cv2
import mediapipe as mp

drawing_utils = mp.solutions.drawing_utils
pose = mp.solutions.pose

from src.config import PoseConfig
from src.fall_detector import Point


LANDMARK_NAMES = {
    "nose": pose.PoseLandmark.NOSE,
    "left_shoulder": pose.PoseLandmark.LEFT_SHOULDER,
    "right_shoulder": pose.PoseLandmark.RIGHT_SHOULDER,
    "left_hip": pose.PoseLandmark.LEFT_HIP,
    "right_hip": pose.PoseLandmark.RIGHT_HIP,
}


@dataclass(frozen=True)
class PoseEstimateResult:
    points: dict[str, Point] | None
    results: Any
    pose_ms: float


class PoseEstimator:
    def __init__(self, config: PoseConfig | None = None) -> None:
        self.config = config or PoseConfig()
        self._mp_pose = pose
        self._drawing = drawing_utils
        self._pose = self._mp_pose.Pose(
            static_image_mode=False,
            model_complexity=max(0, min(2, self.config.model_complexity)),
            enable_segmentation=False,
            min_detection_confidence=self.config.min_detection_confidence,
            min_tracking_confidence=self.config.min_tracking_confidence,
        )

    def close(self) -> None:
        self._pose.close()

    def estimate(self, frame_bgr: Any) -> PoseEstimateResult:
        started = perf_counter()
        inference_frame = prepare_pose_frame(
            frame_bgr,
            self.config.input_width,
            self.config.input_height,
        )
        frame_rgb = cv2.cvtColor(inference_frame, cv2.COLOR_BGR2RGB)
        results = self._pose.process(frame_rgb)
        pose_ms = (perf_counter() - started) * 1000.0

        if not results.pose_landmarks:
            return PoseEstimateResult(points=None, results=results, pose_ms=pose_ms)

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
            return PoseEstimateResult(points=None, results=results, pose_ms=pose_ms)
        return PoseEstimateResult(points=points, results=results, pose_ms=pose_ms)

    def draw(self, frame_bgr: Any, results: Any) -> None:
        if results.pose_landmarks:
            self._drawing.draw_landmarks(
                frame_bgr,
                results.pose_landmarks,
                self._mp_pose.POSE_CONNECTIONS,
            )


def prepare_pose_frame(frame_bgr: Any, input_width: int, input_height: int) -> Any:
    """Downscale large frames before pose inference to improve FPS."""

    if input_width <= 0 or input_height <= 0:
        return frame_bgr

    height, width = frame_bgr.shape[:2]
    if width <= input_width and height <= input_height:
        return frame_bgr

    return cv2.resize(
        frame_bgr,
        (input_width, input_height),
        interpolation=cv2.INTER_AREA,
    )
