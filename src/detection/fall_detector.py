"""
File: src/detection/fall_detector.py
Chức năng chính: Chứa thuật toán cốt lõi để phát hiện người té ngã (Rule-based Fall Detection).
Thuật toán tính toán dựa trên các điểm ảnh (landmarks) do MediaPipe trả về.

File liên kết:
- Gọi bởi: src/core/app.py và src/web/shared/pipeline.py (để xử lý mỗi frame)
- Sử dụng cấu hình từ: src/core/config.py
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import atan2, cos, degrees, hypot, radians
from typing import Any, Mapping

from src.core.config import DetectorConfig
from src.detection.balance_analyzer import BalanceAnalyzer, BalanceMetrics, PreFallType


class FallState(str, Enum):
    """
    Các trạng thái có thể có của một người trong khung hình:
    - NORMAL: Bình thường (đứng, ngồi).
    - PRE_FALL: Tiền té ngã (lảo đảo, bước hụt, chóng mặt, mất thăng bằng).
    - LYING: Đang nằm (nhưng không phải do té ngã).
    - WARNING: Cảnh báo nhẹ (góc nghiêng nguy hiểm nhưng chưa hẳn ngã).
    - POSSIBLE_FALL: Có khả năng ngã (đang nằm và trước đó có chuyển động mạnh).
    - FALLEN: Đã ngã (nằm đủ lâu).
    - ALERT: Báo động đỏ (nằm quá lâu sau khi ngã, cần cứu hộ).
    """
    NORMAL = "normal"
    PRE_FALL = "pre_fall"
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
    safe_resting: bool = False
    resting_object: str = ""
    pre_fall: bool = False
    pre_fall_type: str = ""
    postural_sway: float = 0.0
    is_seated: bool = False


class FallDetector:
    """
    Thuật toán phát hiện té ngã dựa trên luật (Rule-based).
    Dựa vào các toạ độ chuẩn hoá (normalized pose landmarks) từ MediaPipe.

    Coordinate convention follows image coordinates: x grows right, y grows down.
    """

    def __init__(self, config: DetectorConfig | None = None) -> None:
        self.config = _profiled_config(config or DetectorConfig())
        self.balance_analyzer = BalanceAnalyzer(self.config)
        self._previous_hip_y: float | None = None
        self._previous_torso_angle: float | None = None
        self._abnormal_frames = 0
        self._lying_frames = 0
        self._recent_upright_frames = 0
        self._non_lying_consecutive_frames = 0
        self._fall_candidate = False
        self._alert_active = False
        self._cooldown = 0
        self._pre_fall_history_frames = 0
        self._fall_from_pre_fall = False

    def reset(self) -> None:
        """Đặt lại toàn bộ trạng thái về ban đầu (dùng khi đổi video hoặc ấn phím R)."""
        self.balance_analyzer.reset()
        self._previous_hip_y = None
        self._previous_torso_angle = None
        self._abnormal_frames = 0
        self._lying_frames = 0
        self._recent_upright_frames = 0
        self._non_lying_consecutive_frames = 0
        self._fall_candidate = False
        self._alert_active = False
        self._cooldown = 0
        self._pre_fall_history_frames = 0
        self._fall_from_pre_fall = False

    def _calculate_scale_normalized_velocity(self, raw_velocity: float, torso_length: float) -> float:
        """Chuẩn hóa vận tốc hông rơi bất biến theo khoảng cách người tới camera."""
        if not getattr(self.config, "enable_scale_normalization", True) or self._previous_hip_y is None:
            return raw_velocity
        ref_torso = getattr(self.config, "reference_torso_length", 0.25)
        effective_torso = max(0.06, torso_length)
        scale_factor = max(0.5, min(3.0, ref_torso / effective_torso))
        return raw_velocity * scale_factor

    def _evaluate_safe_resting(
        self,
        landmarks: Mapping[str, Point],
        nearby_objects: list[Any] | None,
        is_lying: bool,
    ) -> tuple[bool, str]:
        """Kiểm tra xem người có đang nằm an toàn trên giường/sofa hay không."""
        if not nearby_objects or not is_lying:
            return False, ""

        xs = [p.x for p in landmarks.values() if getattr(p, "visibility", 0) > 0.20]
        ys = [p.y for p in landmarks.values() if getattr(p, "visibility", 0) > 0.20]
        if not xs or not ys:
            return False, ""

        person_norm_box = (min(xs), min(ys), max(xs), max(ys))
        from src.detection.object_detector import compute_box_overlap

        bed_threshold = getattr(self.config, "bed_overlap_threshold", 0.35)
        for obj in nearby_objects:
            lbl = getattr(obj, "label", "").lower()
            norm_box = getattr(obj, "normalized_box", None)
            if norm_box and lbl in {"bed", "couch", "sofa"}:
                if compute_box_overlap(person_norm_box, norm_box) >= bed_threshold:
                    return True, lbl

        return False, ""

    def _evaluate_seated(
        self,
        landmarks: Mapping[str, Point],
        shoulder: Point,
        hip: Point,
        nose: Point,
        nearby_objects: list[Any] | None,
        torso_angle: float = 0.0,
    ) -> tuple[bool, str]:
        """
        Kiểm tra xem người có đang ở tư thế ngồi (làm việc trước bàn, ngồi ghế, dùng laptop) hay không.
        
        Quy tắc lọc độ sát mặt sàn & che khuất bàn làm việc (Ground Proximity & Seated Desk Occlusion):
        1. Cú ngã thật trên sàn luôn xảy ra ở nửa dưới khung hình (shoulder.y >= 0.52 hoặc hip.y >= 0.60).
        2. Nếu vai ở nửa trên khung hình (shoulder.y < 0.52) VÀ khoảng cách dọc thân bị nén bởi mặt bàn
           (abs(hip.y - shoulder.y) < 0.16) VÀ đầu hướng lên trên: nhận diện người đang ngồi làm việc trước bàn bị che khuất thân dưới.
        3. Nếu vai ở nửa trên khung hình (shoulder.y < 0.52) VÀ hông chưa sát sàn (hip.y < 0.60)
           VÀ người có giao thoa với ghế (chair), bàn (dining table), hoặc laptop: nhận diện là tư thế ngồi làm việc an toàn.
        """
        # Cú ngã thật trên sàn luôn có hông hoặc vai sụp xuống sát sàn khi thân người nằm ngang/nghiêng ngã
        is_floor_collapsed = (torso_angle >= 50.0) or (nose.y >= shoulder.y - 0.05)
        if is_floor_collapsed and (hip.y >= 0.60 or (shoulder.y >= 0.52 and hip.y >= 0.52)):
            return False, ""

        # 1. Che khuất do bàn làm việc (Desk occlusion)
        # Người ngồi làm việc trước bàn: khoảng cách dọc hông-vai bị nén bởi mặt bàn
        # (abs(hip.y - shoulder.y) < 0.16) và đầu hướng lên trên.
        is_desk_compressed = abs(hip.y - shoulder.y) < 0.16
        head_is_upright = (
            nose.y <= 0.08
            or (getattr(nose, "visibility", 1.0) < 0.35 and shoulder.y < 0.50)
            or (nose.y < shoulder.y and (shoulder.y - nose.y) >= 0.08)
        )
        if is_desk_compressed and head_is_upright:
            return True, "desk_occlusion"

        # 2. Giao thoa với vật thể ngồi / làm việc (chair, dining table, laptop)
        if nearby_objects and shoulder.y < 0.52 and hip.y < 0.60:
            xs = [p.x for p in landmarks.values() if getattr(p, "visibility", 0) > 0.20]
            ys = [p.y for p in landmarks.values() if getattr(p, "visibility", 0) > 0.20]
            if xs and ys:
                person_norm_box = (min(xs), min(ys), max(xs), max(ys))
                from src.detection.object_detector import compute_box_overlap
                for obj in nearby_objects:
                    lbl = getattr(obj, "label", "").lower().strip()
                    norm_box = getattr(obj, "normalized_box", None)
                    if norm_box and lbl in {"chair", "dining table", "laptop", "couch", "bench"}:
                        overlap_p = compute_box_overlap(person_norm_box, norm_box)
                        overlap_o = compute_box_overlap(norm_box, person_norm_box)
                        if max(overlap_p, overlap_o) >= 0.10:
                            return True, lbl

        return False, ""

    def update(
        self,
        landmarks: Mapping[str, Point],
        nearby_objects: list[Any] | None = None,
    ) -> DetectionResult:
        """
        Cập nhật thuật toán với các điểm mốc (landmarks) của frame hiện tại và vật thể xung quanh.
        """
        left_hip = landmarks.get("left_hip")
        right_hip = landmarks.get("right_hip")
        left_shoulder = landmarks.get("left_shoulder")
        right_shoulder = landmarks.get("right_shoulder")
        nose = landmarks.get("nose")

        if not left_hip or not right_hip or not left_shoulder or not right_shoulder or not nose:
            self._previous_hip_y = None
            self._previous_torso_angle = None
            self.balance_analyzer.on_tracking_lost()
            return DetectionResult(
                state=FallState.NORMAL,
                torso_angle_deg=0.0,
                head_hip_delta=1.0,
                hip_velocity=0.0,
                angle_velocity_deg=0.0,
                abnormal_frames=0,
                lying_seconds=0.0,
                profile=self.config.profile,
                fall_like_transition=False,
                event_started=False,
                safe_resting=False,
                resting_object="",
                pre_fall=False,
                pre_fall_type="",
                postural_sway=0.0,
            )

        hip_vis = max(getattr(left_hip, "visibility", 1.0), getattr(right_hip, "visibility", 1.0))
        shoulder_vis = max(getattr(left_shoulder, "visibility", 1.0), getattr(right_shoulder, "visibility", 1.0))

        # QUAN TRỌNG: Khi camera chỉ thấy phần trên cơ thể (ngồi bàn, webcam góc hẹp, chỉ thấy đầu/ngực),
        # MediaPipe ước lượng toạ độ hông ảo ngoài màn hình với visibility cực thấp (< 0.25).
        # Cần ít nhất một bên hông và vai hiển thị rõ để thẩm định tư thế té ngã.
        if hip_vis < 0.25 or shoulder_vis < 0.25:
            self._lying_frames = 0
            self._abnormal_frames = 0
            self._fall_candidate = False
            self._alert_active = False
            self._previous_hip_y = None
            self._previous_torso_angle = None
            self.balance_analyzer.on_tracking_lost()
            return DetectionResult(
                state=FallState.NORMAL,
                torso_angle_deg=0.0,
                head_hip_delta=1.0,
                hip_velocity=0.0,
                angle_velocity_deg=0.0,
                abnormal_frames=0,
                lying_seconds=0.0,
                profile=self.config.profile,
                fall_like_transition=False,
                event_started=False,
                safe_resting=False,
                resting_object="",
                pre_fall=False,
                pre_fall_type="",
                postural_sway=0.0,
            )

        shoulder = _midpoint(left_shoulder, right_shoulder)
        hip = _midpoint(left_hip, right_hip)

        # 1. Kích thước thân người tham chiếu (Torso length)
        current_torso_length = hypot(shoulder.x - hip.x, shoulder.y - hip.y)

        # 2. Góc thân người có bù trừ góc đặt camera chúc xuống
        pitch_deg = getattr(self.config, "camera_pitch_angle_deg", 0.0)
        torso_angle = _angle_from_vertical(shoulder, hip, pitch_deg)

        if nose.visibility >= 0.35:
            head_hip_delta = hip.y - nose.y
        else:
            # Fallback to shoulder when nose is occluded, scaling up by 1.5 to match nose-hip ratio
            head_hip_delta = (hip.y - shoulder.y) * 1.5

        # 3. Chuẩn hóa vận tốc rơi bất biến theo khoảng cách người tới camera (Scale Invariance)
        raw_hip_velocity = 0.0 if self._previous_hip_y is None else hip.y - self._previous_hip_y
        hip_velocity = self._calculate_scale_normalized_velocity(raw_hip_velocity, current_torso_length)

        angle_velocity = (
            0.0
            if self._previous_torso_angle is None
            else torso_angle - self._previous_torso_angle
        )
        self._previous_hip_y = hip.y
        self._previous_torso_angle = torso_angle

        # 4. Phân tích động học tư thế & tiền té ngã (Pre-fall Analysis)
        balance_metrics = self.balance_analyzer.analyze(landmarks, torso_angle, angle_velocity)
        if balance_metrics.is_pre_fall:
            self._pre_fall_history_frames = 30
        elif self.balance_analyzer._stable_upright_count >= 5:
            # Người đã phục hồi thăng bằng hoàn toàn -> Reset bộ nhớ tiền té ngã
            self._pre_fall_history_frames = 0
        elif self._pre_fall_history_frames > 0:
            self._pre_fall_history_frames -= 1

        torso_is_horizontal = torso_angle >= self.config.torso_fall_angle_deg
        torso_is_upright = torso_angle <= self.config.torso_upright_angle_deg

        # Bộ lọc phần đầu ở sát mép trên khung hình:
        # Khi người ngồi làm việc trước camera, đầu có thể sát mép trên (nose.y <= 0.08 hoặc nose.visibility < 0.35
        # với shoulder.y < 0.50), đầu thực tế đang hướng lên trần nhà chứ không phải ngã đập đầu xuống sàn.
        head_near_top = (nose.y <= 0.08 or (getattr(nose, "visibility", 1.0) < 0.35 and shoulder.y < 0.50))
        head_is_low = (not head_near_top) and (head_hip_delta <= self.config.head_hip_height_ratio)
        hip_dropped_fast = hip_velocity >= self.config.hip_drop_velocity
        body_rotated_fast = angle_velocity >= self.config.angle_change_velocity_deg
        
        # Nhận diện nằm: thân nghiêng ngang (>= torso_fall_angle_deg) và đầu không quá cao so với hông (và không ở sát mép trên)
        max_lying_head_delta = max(0.38, self.config.head_hip_height_ratio * 1.5)
        lying = (not head_near_top) and torso_is_horizontal and (head_hip_delta <= max_lying_head_delta)

        # Lọc chi thể giả lập (Limb artifact on desk / forearm / hand):
        # Người ngã thật trên sàn luôn có thân người đầy đủ (current_torso_length >= 0.14).
        # Nếu chiều dài thân < 0.14 mà góc thân ngang (>= 58 độ) thì đây là cánh tay/bàn tay đặt trên bàn
        is_limb_artifact = (current_torso_length < 0.14) and torso_is_horizontal
        if is_limb_artifact:
            lying = False
            self._fall_candidate = False

        # 5. Tích hợp bối cảnh không gian với vật thể & Bộ lọc ngồi làm việc (Spatial Context & Seated Desk Fusion)
        safe_resting, resting_object = self._evaluate_safe_resting(landmarks, nearby_objects, lying)
        is_seated, seated_object = self._evaluate_seated(landmarks, shoulder, hip, nose, nearby_objects, torso_angle)

        if safe_resting:
            # Người nằm an toàn trên giường / sofa -> Triệt tiêu nguy cơ cảnh báo té ngã
            is_seated = False
            self._fall_candidate = False
            self._fall_from_pre_fall = False
            self._pre_fall_history_frames = 0
            self._abnormal_frames = 0
            self._alert_active = False

        if is_seated:
            # Người ngồi làm việc trước bàn hoặc ngồi trên ghế/laptop -> Không phải nằm ngã
            lying = False
            self._fall_candidate = False
            self._fall_from_pre_fall = False
            self._pre_fall_history_frames = 0
            self._abnormal_frames = 0
            self._lying_frames = 0
            self._alert_active = False

        if torso_is_upright or is_seated:
            self._recent_upright_frames = min(self._recent_upright_frames + 1, 30)
        else:
            self._recent_upright_frames = max(0, self._recent_upright_frames - 1)

        fall_like_transition = (not safe_resting) and (not is_seated) and (not is_limb_artifact) and torso_is_horizontal and (
            hip_dropped_fast
            or body_rotated_fast
            or (self._recent_upright_frames >= 4 and torso_angle >= 62.0)
            or (self._pre_fall_history_frames > 0)
        )
        if fall_like_transition:
            self._fall_candidate = True
            if self._pre_fall_history_frames > 0:
                self._fall_from_pre_fall = True

        if is_seated:
            self._non_lying_consecutive_frames += 1
            self._lying_frames = 0
            self._abnormal_frames = 0
            self._fall_candidate = False
            self._alert_active = False
        elif lying and not safe_resting:
            self._non_lying_consecutive_frames = 0
            self._lying_frames += 1
        elif safe_resting:
            self._non_lying_consecutive_frames = 0
            self._lying_frames = 0
        else:
            self._non_lying_consecutive_frames += 1
            if torso_is_upright or self._non_lying_consecutive_frames >= 5:
                # Đứng dậy hoặc hết nằm sau nhiều frames liên tục -> Reset trạng thái
                self._lying_frames = 0
                self._fall_candidate = False
                self._fall_from_pre_fall = False
                self._alert_active = False
                self._abnormal_frames = 0
            else:
                # Khung hình giật hoặc che khuất tạm thời trên sàn -> Giảm dần thay vì xóa về 0 ngay lập tức
                self._lying_frames = max(0, self._lying_frames - 1)
                self._abnormal_frames = max(0, self._abnormal_frames - 1)

        abnormal = (not safe_resting) and (not is_seated) and (self._lying_frames > 0) and (
            self._fall_candidate or self.config.alert_on_long_lying_without_fall
        )

        if abnormal and lying:
            self._abnormal_frames += 1

        event_started = False
        lying_seconds = self._lying_frames / max(self.config.assumed_fps, 1.0)
        
        has_pre_fall_linkage = self._pre_fall_history_frames > 0 or self._fall_from_pre_fall
        effective_min_fall_frames = (
            max(2, self.config.min_fall_frames // 2)
            if has_pre_fall_linkage
            else self.config.min_fall_frames
        )
        effective_alert_seconds = (
            self.config.alert_after_seconds * 0.5
            if has_pre_fall_linkage
            else self.config.alert_after_seconds
        )

        if safe_resting:
            state = FallState.LYING
            self._abnormal_frames = 0
        elif is_seated:
            state = FallState.NORMAL
            self._abnormal_frames = 0
        elif lying:
            if (
                self._abnormal_frames >= effective_min_fall_frames
                and lying_seconds >= effective_alert_seconds
            ):
                state = FallState.ALERT
                if not self._alert_active and self._cooldown == 0:
                    event_started = True
                    self._alert_active = True
                    self._cooldown = self.config.cooldown_frames
            elif self._abnormal_frames >= effective_min_fall_frames:
                state = FallState.FALLEN
            elif self._abnormal_frames >= self.config.warning_frames:
                state = FallState.POSSIBLE_FALL
            else:
                state = FallState.LYING
        else:
            # Người không nằm: kiểm tra tiền té ngã hoặc bình thường
            if balance_metrics.is_pre_fall:
                state = FallState.PRE_FALL
                self._abnormal_frames = 0
            elif torso_is_upright or self._non_lying_consecutive_frames >= 5:
                state = FallState.NORMAL
                self._abnormal_frames = 0
            elif self._abnormal_frames >= self.config.warning_frames:
                state = FallState.WARNING
            else:
                state = FallState.NORMAL

        if self._cooldown > 0:
            self._cooldown -= 1

        final_resting_object = resting_object if safe_resting else (seated_object if is_seated else "")

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
            safe_resting=safe_resting,
            resting_object=final_resting_object,
            pre_fall=False if (is_seated or safe_resting) else balance_metrics.is_pre_fall,
            pre_fall_type="" if (is_seated or safe_resting) else balance_metrics.pre_fall_type.value,
            postural_sway=0.0 if (is_seated or safe_resting) else balance_metrics.postural_sway,
            is_seated=is_seated,
        )


def _midpoint(a: Point, b: Point) -> Point:
    """Tính toạ độ trung điểm giữa hai điểm (ví dụ: giữa vai trái và vai phải)."""
    return Point(
        x=(a.x + b.x) / 2.0,
        y=(a.y + b.y) / 2.0,
        visibility=(a.visibility + b.visibility) / 2.0,
    )


def _angle_from_vertical(shoulder: Point, hip: Point, camera_pitch_angle_deg: float = 0.0) -> float:
    """
    Tính góc của thân người so với phương thẳng đứng (trục Y/trọng lực).
    - 0 độ: Đứng thẳng hoàn toàn.
    - 90 độ: Nằm ngang hoàn toàn.
    - camera_pitch_angle_deg: Bù trừ góc nghiêng do camera gắn chúc xuống.
    """
    dx = shoulder.x - hip.x
    dy = shoulder.y - hip.y
    raw_angle = abs(degrees(atan2(abs(dx), abs(dy))))
    if camera_pitch_angle_deg > 0.0:
        pitch_rad = radians(camera_pitch_angle_deg)
        tilt_factor = cos(atan2(abs(dx), max(1e-4, abs(dy))))
        compensated = max(0.0, raw_angle - degrees(pitch_rad) * 0.5 * tilt_factor)
        return float(compensated)
    return raw_angle


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
    return replace(
        config,
        torso_fall_angle_deg=config.torso_fall_angle_deg * sensitivity,
        hip_drop_velocity=config.hip_drop_velocity * sensitivity,
        angle_change_velocity_deg=config.angle_change_velocity_deg * sensitivity,
        min_fall_frames=max(2, round(config.min_fall_frames * sensitivity)),
        warning_frames=max(1, round(config.warning_frames * sensitivity)),
        pre_fall_sway_threshold=config.pre_fall_sway_threshold * sensitivity,
        profile=profile,
    )
