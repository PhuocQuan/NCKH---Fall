from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import atan2, degrees, hypot
from typing import Iterable, Mapping

import numpy as np

from src.fall_detector import Point


FEATURE_NAMES = [
    "torso_angle_mean",
    "torso_angle_max",
    "torso_angle_delta",
    "hip_y_mean",
    "hip_y_delta",
    "hip_y_velocity_max",
    "head_hip_delta_mean",
    "head_hip_delta_min",
    "shoulder_hip_distance_mean",
    "visibility_mean",
]


@dataclass(frozen=True)
class PoseFeatures:
    values: np.ndarray
    names: list[str]


class LandmarkFeatureBuffer:
    def __init__(self, window_size: int = 30) -> None:
        self.window_size = window_size
        self._frames: deque[Mapping[str, Point]] = deque(maxlen=window_size)

    def reset(self) -> None:
        self._frames.clear()

    def append(self, landmarks: Mapping[str, Point]) -> PoseFeatures:
        self._frames.append(landmarks)
        return extract_sequence_features(self._frames)


def extract_sequence_features(frames: Iterable[Mapping[str, Point]]) -> PoseFeatures:
    frame_list = list(frames)
    if not frame_list:
        return PoseFeatures(values=np.zeros(len(FEATURE_NAMES), dtype=float), names=FEATURE_NAMES.copy())

    torso_angles = []
    hip_y = []
    head_hip_delta = []
    shoulder_hip_distance = []
    visibility = []

    for landmarks in frame_list:
        shoulder = _midpoint(landmarks["left_shoulder"], landmarks["right_shoulder"])
        hip = _midpoint(landmarks["left_hip"], landmarks["right_hip"])
        nose = landmarks["nose"]
        torso_angles.append(_angle_from_vertical(shoulder, hip))
        hip_y.append(hip.y)
        head_hip_delta.append(hip.y - nose.y)
        shoulder_hip_distance.append(hypot(shoulder.x - hip.x, shoulder.y - hip.y))
        visibility.extend(point.visibility for point in landmarks.values())

    hip_velocity = np.diff(hip_y) if len(hip_y) > 1 else np.array([0.0])
    values = np.array(
        [
            float(np.mean(torso_angles)),
            float(np.max(torso_angles)),
            float(torso_angles[-1] - torso_angles[0]),
            float(np.mean(hip_y)),
            float(hip_y[-1] - hip_y[0]),
            float(np.max(hip_velocity)),
            float(np.mean(head_hip_delta)),
            float(np.min(head_hip_delta)),
            float(np.mean(shoulder_hip_distance)),
            float(np.mean(visibility)),
        ],
        dtype=float,
    )
    return PoseFeatures(values=values, names=FEATURE_NAMES.copy())


def _midpoint(a: Point, b: Point) -> Point:
    return Point(
        x=(a.x + b.x) / 2.0,
        y=(a.y + b.y) / 2.0,
        visibility=(a.visibility + b.visibility) / 2.0,
    )


def _angle_from_vertical(shoulder: Point, hip: Point) -> float:
    dx = shoulder.x - hip.x
    dy = shoulder.y - hip.y
    return abs(degrees(atan2(abs(dx), abs(dy))))

