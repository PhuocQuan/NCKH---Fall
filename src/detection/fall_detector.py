"""
File: src/detection/fall_detector.py
Chức năng chính: Chứa thuật toán cốt lõi để phát hiện người té ngã (Rule-based Fall Detection).
Thuật toán tính toán dựa trên các điểm ảnh (landmarks) do MediaPipe trả về.

File liên kết:
- Gọi bởi: src/core/app.py và src/web/shared/pipeline.py (để xử lý mỗi frame)
- Sử dụng cấu hình từ: src/core/config.py
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import atan2, degrees
from typing import Mapping

from src.core.config import DetectorConfig


class FallState(str, Enum):
    """
    Các trạng thái có thể có của một người trong khung hình:
    - NORMAL: Bình thường (đứng, ngồi).
    - LYING: Đang nằm (nhưng không phải do té ngã).
    - WARNING: Cảnh báo nhẹ (góc nghiêng nguy hiểm nhưng chưa hẳn ngã).
    - POSSIBLE_FALL: Có khả năng ngã (đang nằm và trước đó có chuyển động mạnh).
    - FALLEN: Đã ngã (nằm đủ lâu).
    - ALERT: Báo động đỏ (nằm quá lâu sau khi ngã, cần cứu hộ).
    """
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
    """Kết quả phát hiện trả về sau mỗi frame."""
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
    """
    Thuật toán phát hiện té ngã dựa trên luật (Rule-based).
    Dựa vào các toạ độ chuẩn hoá (normalized pose landmarks) từ MediaPipe.

    Coordinate convention follows image coordinates: x grows right, y grows down.
    """

    def __init__(self, config: DetectorConfig | None = None) -> None:
        self.config = _profiled_config(config or DetectorConfig())
        self._previous_hip_y: float | None = None
        self._previous_torso_angle: float | None = None
        self._abnormal_frames = 0
        self._lying_frames = 0
        self._recent_upright_frames = 0
        self._non_lying_consecutive_frames = 0
        self._fall_candidate = False
        self._alert_active = False
        self._cooldown = 0

    def reset(self) -> None:
        """Đặt lại toàn bộ trạng thái về ban đầu (dùng khi đổi video hoặc ấn phím R)."""
        self._previous_hip_y = None
        self._previous_torso_angle = None
        self._abnormal_frames = 0
        self._lying_frames = 0
        self._recent_upright_frames = 0
        self._non_lying_consecutive_frames = 0
        self._fall_candidate = False
        self._alert_active = False
        self._cooldown = 0

    def update(self, landmarks: Mapping[str, Point]) -> DetectionResult:
        """
        Cập nhật thuật toán với các điểm mốc (landmarks) của frame hiện tại.
        
        Logic từng bước:
        1. Tính điểm giữa của vai (shoulder) và hông (hip).
        2. Tính góc thân người (torso_angle) so với trục dọc (Y). Góc càng lớn tức là càng nằm ngang.
        3. Tính chênh lệch độ cao giữa đầu (mũi/vai) và hông (head_hip_delta). 
           Nếu đầu ngang hoặc thấp hơn hông -> đang nằm.
        4. Tính vận tốc rơi (hip_velocity) và tốc độ thay đổi góc (angle_velocity).
        5. Kết hợp các yếu tố trên để xác định người đó đang NẰM (lying) hay đang ĐỨNG (upright).
        6. Nếu đang nằm VÀ trước đó có rơi nhanh -> Đánh dấu là Ứng viên Té ngã (fall_candidate).
        7. Đếm số frame nằm liên tục. Nếu vượt ngưỡng cảnh báo (alert_after_seconds) -> kích hoạt ALERT.
        8. Trả về kết quả (DetectionResult).
        """
        shoulder = _midpoint(landmarks["left_shoulder"], landmarks["right_shoulder"])
        hip = _midpoint(landmarks["left_hip"], landmarks["right_hip"])
        nose = landmarks["nose"]

        torso_angle = _angle_from_vertical(shoulder, hip)
        if nose.visibility >= 0.35:
            head_hip_delta = hip.y - nose.y
        else:
            # Fallback to shoulder when nose is occluded, scaling up by 1.5 to match nose-hip ratio
            head_hip_delta = (hip.y - shoulder.y) * 1.5
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
        
        # Nhận diện nằm: thân nghiêng ngang (>= 50°) và đầu không quá cao so với hông
        max_lying_head_delta = max(0.38, self.config.head_hip_height_ratio * 1.5)
        lying = (torso_is_horizontal and head_hip_delta <= max_lying_head_delta) or (
            torso_angle >= 50.0 and head_hip_delta <= max_lying_head_delta
        )

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
            self._non_lying_consecutive_frames = 0
            self._lying_frames += 1
        else:
            self._non_lying_consecutive_frames += 1
            if torso_is_upright or self._non_lying_consecutive_frames >= 5:
                # Đứng dậy hoặc hết nằm sau nhiều frames liên tục -> Reset trạng thái
                self._lying_frames = 0
                self._fall_candidate = False
                self._alert_active = False
                self._abnormal_frames = 0
            else:
                # Khung hình giật hoặc che khuất tạm thời trên sàn -> Giảm dần thay vì xóa về 0 ngay lập tức
                self._lying_frames = max(0, self._lying_frames - 1)
                self._abnormal_frames = max(0, self._abnormal_frames - 1)

        abnormal = (self._lying_frames > 0) and (
            self._fall_candidate or self.config.alert_on_long_lying_without_fall
        )

        if abnormal and lying:
            self._abnormal_frames += 1

        event_started = False
        lying_seconds = self._lying_frames / max(self.config.assumed_fps, 1.0)
        
        if torso_is_upright or (not lying and self._non_lying_consecutive_frames >= 5):
            state = FallState.NORMAL
            self._abnormal_frames = 0
        elif (
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
            state = FallState.POSSIBLE_FALL if lying else FallState.WARNING
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
    """Tính toạ độ trung điểm giữa hai điểm (ví dụ: giữa vai trái và vai phải)."""
    return Point(
        x=(a.x + b.x) / 2.0,
        y=(a.y + b.y) / 2.0,
        visibility=(a.visibility + b.visibility) / 2.0,
    )


def _angle_from_vertical(shoulder: Point, hip: Point) -> float:
    """
    Tính góc của thân người so với phương thẳng đứng (trục Y).
    - 0 độ: Đứng thẳng hoàn toàn.
    - 90 độ: Nằm ngang hoàn toàn.
    """
    dx = shoulder.x - hip.x
    dy = shoulder.y - hip.y
    return abs(degrees(atan2(abs(dx), abs(dy))))


def _profiled_config(config: DetectorConfig) -> DetectorConfig:
    """
    Điều chỉnh độ nhạy (sensitivity) của thuật toán tuỳ theo hồ sơ (profile) người dùng.
    Ví dụ: Người già (elderly) thì thuật toán nhạy hơn (giảm ngưỡng vận tốc và góc).
    """
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
