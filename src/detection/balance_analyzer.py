"""
File: src/detection/balance_analyzer.py
Chức năng chính: Phân tích động học tư thế đa chiều và định lượng các chỉ số sinh cơ học
để phát hiện hành vi tiền té ngã (Pre-Fall Detection: mất thăng bằng, lảo đảo, bước hụt, chóng mặt).

File liên kết:
- Gọi bởi: src/detection/fall_detector.py (tích hợp trong mỗi chu trình cập nhật frame)
- Sử dụng cấu hình từ: src/core/config.py (DetectorConfig)
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Mapping

from src.core.config import DetectorConfig


class PreFallType(str, Enum):
    """
    Phân loại hành vi tiền té ngã:
    - NONE: Thăng bằng ổn định bình thường.
    - SWAYING: Lảo đảo / Đung đưa thân ngang liên tục (Postural Sway).
    - STUMBLE: Bước hụt / Vấp ngã (Stumble / Deceleration drop).
    - DIZZY: Chóng mặt / Choáng váng, mất thăng bằng kéo dài (Dizziness / Unsteadiness).
    """
    NONE = "none"
    SWAYING = "swaying"
    STUMBLE = "stumble"
    DIZZY = "dizzy"


@dataclass(frozen=True)
class BalanceMetrics:
    """Các chỉ số sinh học định lượng sự thăng bằng của cơ thể."""
    is_pre_fall: bool
    pre_fall_type: PreFallType
    postural_sway: float          # Postural sway score chuẩn hóa trong đoạn [0.0, 1.0]
    lateral_std: float            # Độ lệch chuẩn vị trí ngang CoM (sigma_x)
    reversals: int                # Số lần đảo hướng chuyển động ngang (zero-crossings)
    torso_instability: float      # Chỉ số mất ổn định góc nghiêng thân [0.0, 1.0]
    com_x: float                  # Trọng tâm x
    com_y: float                  # Trọng tâm y
    com_velocity_x: float         # Vận tốc ngang của CoM
    com_velocity_y: float         # Vận tốc dọc của CoM


class BalanceAnalyzer:
    """
    Thuật toán phân tích động học tư thế dựa trên cửa sổ trượt thời gian (Sliding Window).
    Tính toán Center of Mass (CoM), độ dao động ngang, tần số đảo chiều và góc thân người.
    """

    def __init__(self, config: DetectorConfig | None = None) -> None:
        self.config = config or DetectorConfig()
        self.window_frames = getattr(self.config, "pre_fall_window_frames", 15)
        self.dizzy_duration_frames = getattr(self.config, "pre_fall_dizzy_duration_frames", 25)
        self.sway_threshold = getattr(self.config, "pre_fall_sway_threshold", 0.032)
        self.min_reversals = getattr(self.config, "pre_fall_min_reversals", 3)
        self.enabled = getattr(self.config, "enable_pre_fall", True)

        max_history = max(self.window_frames, self.dizzy_duration_frames, 30)
        self._history: deque[tuple[float, float, float]] = deque(maxlen=max_history)
        self._stable_upright_count = 0
        self._previous_com_x: float | None = None
        self._previous_com_y: float | None = None

    def reset(self) -> None:
        """Đặt lại toàn bộ trạng thái bộ nhớ đệm."""
        self._history.clear()
        self._stable_upright_count = 0
        self._previous_com_x = None
        self._previous_com_y = None

    def on_tracking_lost(self) -> None:
        """Đặt lại CoM trước đó khi mất dấu landmarks để không nhảy vọt vận tốc sau gián đoạn."""
        self._previous_com_x = None
        self._previous_com_y = None

    def analyze(
        self,
        landmarks: Mapping[str, Any],
        torso_angle: float,
        angle_velocity: float = 0.0,
    ) -> BalanceMetrics:
        """
        Phân tích động học tư thế của frame hiện tại.
        
        Args:
            landmarks: Bản đồ các điểm mốc pose (chứa left_shoulder, right_shoulder, left_hip, right_hip).
            torso_angle: Góc nghiêng thân so với phương thẳng đứng (độ).
            angle_velocity: Vận tốc thay đổi góc thân (độ / frame).
            
        Returns:
            BalanceMetrics: Kết quả định lượng chỉ số thăng bằng.
        """
        if not self.enabled:
            return self._empty_metrics(torso_angle)

        left_sh = _get_pt(landmarks, "left_shoulder")
        right_sh = _get_pt(landmarks, "right_shoulder")
        left_hip = _get_pt(landmarks, "left_hip")
        right_hip = _get_pt(landmarks, "right_hip")

        if not left_sh or not right_sh or not left_hip or not right_hip:
            self._previous_com_x = None
            self._previous_com_y = None
            return self._empty_metrics(torso_angle)

        # Kiểm tra độ tin cậy của các điểm mốc
        vis_list = [getattr(p, "visibility", 1.0) for p in (left_sh, right_sh, left_hip, right_hip)]
        if min(vis_list) < 0.20:
            self._previous_com_x = None
            self._previous_com_y = None
            return self._empty_metrics(torso_angle)

        # 1. Tính toán Center of Mass (CoM) - Trọng tâm thân trên & hông
        sh_mid_x = (left_sh.x + right_sh.x) / 2.0
        sh_mid_y = (left_sh.y + right_sh.y) / 2.0
        hip_mid_x = (left_hip.x + right_hip.x) / 2.0
        hip_mid_y = (left_hip.y + right_hip.y) / 2.0

        com_x = (sh_mid_x + hip_mid_x) / 2.0
        com_y = (sh_mid_y + hip_mid_y) / 2.0

        vx = 0.0 if self._previous_com_x is None else com_x - self._previous_com_x
        vy = 0.0 if self._previous_com_y is None else com_y - self._previous_com_y
        self._previous_com_x = com_x
        self._previous_com_y = com_y

        self._history.append((com_x, com_y, torso_angle))

        upright_angle = getattr(self.config, "torso_upright_angle_deg", 32.0)
        fall_angle = getattr(self.config, "torso_fall_angle_deg", 58.0)

        # Chuẩn hóa tỷ lệ bất biến khoảng cách (Scale Invariance) cho biên độ lắc ngang
        current_torso_length = math.hypot(sh_mid_x - hip_mid_x, sh_mid_y - hip_mid_y)
        ref_torso_len = getattr(self.config, "reference_torso_length", 0.25)
        scale_factor = ref_torso_len / max(0.12, current_torso_length)

        # 2. Xử lý phục hồi thăng bằng (Recovery): Nếu người đứng/ngồi thẳng ổn định trong 5 frame
        if torso_angle <= upright_angle and abs(vx) < 0.010 and vy <= 0.008:
            self._stable_upright_count += 1
        else:
            self._stable_upright_count = 0

        if self._stable_upright_count >= 5:
            # Người đã lấy lại thăng bằng hoàn toàn, reset lịch sử trượt
            self._history.clear()
            self._history.append((com_x, com_y, torso_angle))
            return BalanceMetrics(
                is_pre_fall=False,
                pre_fall_type=PreFallType.NONE,
                postural_sway=0.0,
                lateral_std=0.0,
                reversals=0,
                torso_instability=0.0,
                com_x=com_x,
                com_y=com_y,
                com_velocity_x=vx,
                com_velocity_y=vy,
            )

        # Nếu người đã nằm ngang hoàn toàn (>= fall_angle), không còn là giai đoạn tiền té ngã
        if torso_angle >= fall_angle:
            return BalanceMetrics(
                is_pre_fall=False,
                pre_fall_type=PreFallType.NONE,
                postural_sway=0.0,
                lateral_std=0.0,
                reversals=0,
                torso_instability=1.0,
                com_x=com_x,
                com_y=com_y,
                com_velocity_x=vx,
                com_velocity_y=vy,
            )

        # 3. Phân tích cửa sổ trượt gần nhất (window_frames)
        recent_items = list(self._history)[-self.window_frames:]
        xs = [item[0] for item in recent_items]
        angles = [item[2] for item in recent_items]
        n_samples = len(xs)

        # 3.1. Độ lệch chuẩn vị trí ngang (sigma_x) & Chuẩn hóa theo tỷ lệ khoảng cách
        if n_samples >= 3:
            mean_x = sum(xs) / n_samples
            var_x = sum((x - mean_x) ** 2 for x in xs) / n_samples
            lateral_std = math.sqrt(var_x)
        else:
            lateral_std = 0.0

        norm_lateral_std = lateral_std * scale_factor

        # 3.2. Số lần đảo hướng chuyển động ngang (Velocity Zero-Crossings)
        deadband = 0.0035
        dx_list = [xs[i] - xs[i - 1] for i in range(1, n_samples)]
        signs: list[int] = []
        for dx in dx_list:
            if dx > deadband:
                signs.append(1)
            elif dx < -deadband:
                signs.append(-1)

        reversals = 0
        for i in range(1, len(signs)):
            if signs[i] != signs[i - 1]:
                reversals += 1

        # 3.3. Chỉ số mất ổn định góc nghiêng thân (Torso Tilt Instability)
        if torso_angle <= upright_angle:
            tilt_pos_score = 0.0
        else:
            tilt_pos_score = min(1.0, (torso_angle - upright_angle) / max(1.0, fall_angle - upright_angle))

        if n_samples >= 3:
            mean_angle = sum(angles) / n_samples
            angle_std = math.sqrt(sum((a - mean_angle) ** 2 for a in angles) / n_samples)
        else:
            angle_std = 0.0
        angle_fluc_score = min(1.0, angle_std / 12.0)
        torso_instability = min(1.0, max(0.0, 0.6 * tilt_pos_score + 0.4 * angle_fluc_score))

        # 3.4. Điểm số mất thăng bằng tổng hợp (Postural Sway Score in [0.0, 1.0])
        effective_sway = max(norm_lateral_std, lateral_std) if current_torso_length < 0.20 else norm_lateral_std
        sway_norm = min(1.0, effective_sway / max(1e-5, self.sway_threshold * 1.4))
        rev_norm = min(1.0, reversals / max(1, self.min_reversals + 1))
        postural_sway = min(1.0, max(0.0, 0.5 * sway_norm + 0.3 * rev_norm + 0.2 * torso_instability))

        # 4. Phân loại Tiền Té Ngã (Pre-Fall Classification)
        pre_fall_type = PreFallType.NONE

        recent_vxs = [abs(xs[i] - xs[i - 1]) for i in range(1, n_samples)]
        max_vx_recent = max(recent_vxs) if recent_vxs else 0.0

        has_sway_motion = (norm_lateral_std >= self.sway_threshold or lateral_std >= self.sway_threshold) and reversals >= self.min_reversals
        has_tilt_instability = (torso_angle >= 25.0) or (torso_instability >= 0.25) or (angle_std >= 3.5)
        has_strong_lateral_sway = max_vx_recent >= 0.012
        is_stable_upright = (torso_angle <= 22.0) and (torso_instability < 0.20) and (angle_std < 2.5) and (max_vx_recent < 0.012)

        # 4.1. Bước hụt / Vấp ngã (STUMBLE): Hạ độ cao đột ngột kết hợp giật ngang hoặc vặn góc
        is_stumble = (
            vy >= 0.016
            and (abs(vx) >= 0.012 or torso_angle >= 30.0 or abs(angle_velocity) >= 7.0 or torso_instability >= 0.35)
            and torso_angle < fall_angle
        )
        if is_stumble:
            pre_fall_type = PreFallType.STUMBLE

        # 4.2. Lảo đảo mất thăng bằng cấp tính (SWAYING): Yêu cầu có biên độ lắc ngang kèm vận tốc lớn hoặc mất ổn định thân
        elif has_sway_motion and (has_tilt_instability or has_strong_lateral_sway) and not is_stable_upright:
            pre_fall_type = PreFallType.SWAYING

        # 4.3. Chóng mặt / Choáng váng (DIZZY): Mất thăng bằng đung đưa duy trì liên tục kéo dài >= dizzy_duration_frames
        elif len(self._history) >= self.dizzy_duration_frames:
            all_items = list(self._history)
            all_xs = [it[0] for it in all_items]
            mean_all_x = sum(all_xs) / len(all_xs)
            all_std = math.sqrt(sum((x - mean_all_x) ** 2 for x in all_xs) / len(all_xs))
            norm_all_std = all_std * scale_factor

            all_dx = [all_xs[i] - all_xs[i - 1] for i in range(1, len(all_xs))]
            all_signs = [1 if d > deadband else -1 if d < -deadband else 0 for d in all_dx]
            all_rev = 0
            prev_s = 0
            for s in all_signs:
                if s != 0:
                    if prev_s != 0 and s != prev_s:
                        all_rev += 1
                    prev_s = s

            has_dizzy_sway = (norm_all_std >= self.sway_threshold * 0.65 or all_std >= self.sway_threshold * 0.65)
            if has_dizzy_sway and all_rev >= self.min_reversals and not is_stable_upright:
                pre_fall_type = PreFallType.DIZZY

        is_pre_fall = pre_fall_type != PreFallType.NONE
        if is_pre_fall:
            postural_sway = max(postural_sway, 0.65)

        return BalanceMetrics(
            is_pre_fall=is_pre_fall,
            pre_fall_type=pre_fall_type,
            postural_sway=round(postural_sway, 3),
            lateral_std=round(lateral_std, 4),
            reversals=reversals,
            torso_instability=round(torso_instability, 3),
            com_x=round(com_x, 4),
            com_y=round(com_y, 4),
            com_velocity_x=round(vx, 4),
            com_velocity_y=round(vy, 4),
        )

    def update(
        self,
        landmarks: Mapping[str, Any],
        torso_angle: float,
        angle_velocity: float = 0.0,
    ) -> BalanceMetrics:
        """Bí danh (alias) của phương thức analyze()."""
        return self.analyze(landmarks, torso_angle, angle_velocity)

    def _empty_metrics(self, torso_angle: float = 0.0) -> BalanceMetrics:
        return BalanceMetrics(
            is_pre_fall=False,
            pre_fall_type=PreFallType.NONE,
            postural_sway=0.0,
            lateral_std=0.0,
            reversals=0,
            torso_instability=0.0,
            com_x=0.5,
            com_y=0.5,
            com_velocity_x=0.0,
            com_velocity_y=0.0,
        )


def _get_pt(landmarks: Mapping[str, Any], key: str) -> Any | None:
    if isinstance(landmarks, Mapping):
        return landmarks.get(key)
    return getattr(landmarks, key, None)
