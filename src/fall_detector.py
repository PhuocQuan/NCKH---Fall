from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import atan2, degrees
from typing import Mapping

from src.config import DetectorConfig


class FallState(str, Enum):
    NORMAL = "normal"
    LYING = "lying"
    WARNING = "warning"
    POSSIBLE_FALL = "possible_fall"
    FALLEN = "fallen"
    ALERT = "alert"


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    visibility: float = 1.0


@dataclass(frozen=True)
class DetectionResult:
    state: FallState
    torso_angle_deg: float
    head_hip_delta: float
    hip_velocity: float
    angle_velocity_deg: float
    abnormal_frames: int
    lying_seconds: float
    profile: str
    fall_like_transition: bool
    event_started: bool = False


class FallDetector:
    """Rule-based fall detector over normalized pose landmarks.

    Coordinate convention follows image coordinates: x grows right, y grows down.
    """

    def __init__(self, config: DetectorConfig | None = None) -> None:
        self.config = _profiled_config(config or DetectorConfig())
        self._previous_hip_y: float | None = None
        self._previous_torso_angle: float | None = None
        self._abnormal_frames = 0
        self._lying_frames = 0
        self._recent_upright_frames = 0
        self._fall_candidate = False
        self._alert_active = False
        self._cooldown = 0

    def reset(self) -> None:
        self._previous_hip_y = None
        self._previous_torso_angle = None
        self._abnormal_frames = 0
        self._lying_frames = 0
        self._recent_upright_frames = 0
        self._fall_candidate = False
        self._alert_active = False
        self._cooldown = 0

    def update(self, landmarks: Mapping[str, Point]) -> DetectionResult:
        shoulder = _midpoint(landmarks["left_shoulder"], landmarks["right_shoulder"])
        hip = _midpoint(landmarks["left_hip"], landmarks["right_hip"])
        nose = landmarks["nose"]

        torso_angle = _angle_from_vertical(shoulder, hip)
        head_hip_delta = hip.y - nose.y
        hip_velocity = 0.0 if self._previous_hip_y is None else hip.y - self._previous_hip_y
        angle_velocity = (
            0.0
            if self._previous_torso_angle is None
            else torso_angle - self._previous_torso_angle
        )
        self._previous_hip_y = hip.y
        self._previous_torso_angle = torso_angle

        torso_is_horizontal = torso_angle >= self.config.torso_fall_angle_deg
        torso_is_upright = torso_angle <= self.config.torso_upright_angle_deg
        head_is_low = head_hip_delta <= self.config.head_hip_height_ratio
        hip_dropped_fast = hip_velocity >= self.config.hip_drop_velocity
        body_rotated_fast = angle_velocity >= self.config.angle_change_velocity_deg
        lying = torso_is_horizontal and head_is_low

        if torso_is_upright:
            self._recent_upright_frames = min(self._recent_upright_frames + 1, 30)
        else:
            self._recent_upright_frames = max(0, self._recent_upright_frames - 1)

        fall_like_transition = torso_is_horizontal and (
            hip_dropped_fast or body_rotated_fast or self._recent_upright_frames >= 2
        )
        if fall_like_transition:
            self._fall_candidate = True

        if lying:
            self._lying_frames += 1
        else:
            self._lying_frames = 0
            self._fall_candidate = False
            self._alert_active = False

        abnormal = lying and (
            self._fall_candidate or self.config.alert_on_long_lying_without_fall
        )

        if abnormal:
            self._abnormal_frames += 1
        else:
            self._abnormal_frames = max(0, self._abnormal_frames - 1)

        event_started = False
        lying_seconds = self._lying_frames / max(self.config.assumed_fps, 1.0)
        if (
            self._abnormal_frames >= self.config.min_fall_frames
            and lying_seconds >= self.config.alert_after_seconds
        ):
            state = FallState.ALERT
            if not self._alert_active and self._cooldown == 0:
                event_started = True
                self._alert_active = True
                self._cooldown = self.config.cooldown_frames
        elif self._abnormal_frames >= self.config.min_fall_frames:
            state = FallState.FALLEN
        elif self._abnormal_frames >= self.config.warning_frames:
            state = FallState.POSSIBLE_FALL
        elif self._abnormal_frames > 0:
            state = FallState.WARNING
        elif lying:
            state = FallState.LYING
        else:
            state = FallState.NORMAL

        if self._cooldown > 0:
            self._cooldown -= 1

        return DetectionResult(
            state=state,
            torso_angle_deg=torso_angle,
            head_hip_delta=head_hip_delta,
            hip_velocity=hip_velocity,
            angle_velocity_deg=angle_velocity,
            abnormal_frames=self._abnormal_frames,
            lying_seconds=lying_seconds,
            profile=self.config.profile,
            fall_like_transition=fall_like_transition,
            event_started=event_started,
        )


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


def _profiled_config(config: DetectorConfig) -> DetectorConfig:
    profile = config.profile.lower().strip()
    if profile not in {"elderly", "child", "pregnant", "disabled"}:
        return config

    sensitivity = {
        "elderly": 0.85,
        "child": 0.90,
        "pregnant": 0.85,
        "disabled": 0.80,
    }[profile]
    return DetectorConfig(
        torso_fall_angle_deg=config.torso_fall_angle_deg * sensitivity,
        torso_upright_angle_deg=config.torso_upright_angle_deg,
        head_hip_height_ratio=config.head_hip_height_ratio,
        hip_drop_velocity=config.hip_drop_velocity * sensitivity,
        angle_change_velocity_deg=config.angle_change_velocity_deg * sensitivity,
        min_fall_frames=max(2, round(config.min_fall_frames * sensitivity)),
        warning_frames=max(1, round(config.warning_frames * sensitivity)),
        alert_after_seconds=config.alert_after_seconds,
        alert_on_long_lying_without_fall=config.alert_on_long_lying_without_fall,
        assumed_fps=config.assumed_fps,
        cooldown_frames=config.cooldown_frames,
        profile=profile,
    )
