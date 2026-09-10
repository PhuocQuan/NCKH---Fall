"""
File: src/core/config.py
Chức năng chính: Đọc và phân tích file cấu hình (configs/default.yaml).
Chứa các thông số cấu hình mặc định cho Camera, AI, Thuật toán phát hiện (Góc, Thời gian).

File liên kết:
- Ảnh hưởng tới: Toàn bộ hệ thống (app.py, pipeline.py, fall_detector.py đều phải gọi file này).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DetectorConfig:
    """Cấu hình các ngưỡng (threshold) cho thuật toán phát hiện té ngã (Góc nghiêng, tốc độ rơi, thời gian nằm)."""
    torso_fall_angle_deg: float = 62.0
    torso_upright_angle_deg: float = 35.0
    head_hip_height_ratio: float = 0.18
    hip_drop_velocity: float = 0.035
    angle_change_velocity_deg: float = 18.0
    min_fall_frames: int = 7
    warning_frames: int = 3
    alert_after_seconds: float = 10.0
    alert_on_long_lying_without_fall: bool = False
    assumed_fps: float = 30.0
    cooldown_frames: int = 20
    profile: str = "default"


@dataclass(frozen=True)
class AppConfig:
    """Cấu hình chung cho ứng dụng (Độ phân giải camera, hiển thị xương khớp, đường dẫn lưu file log)."""
    camera_width: int = 640
    camera_height: int = 480
    model_complexity: int = 1
    draw_landmarks: bool = True
    event_log_path: str = "data/events.csv"


@dataclass(frozen=True)
class AIConfig:
    """Cấu hình cho mô hình Học máy AI (Bật/tắt AI, đường dẫn model, ngưỡng xác suất)."""
    enabled: bool = False
    model_path: str = "models/fall_classifier.joblib"
    alert_probability: float = 0.70
    smoothing_frames: int = 5


@dataclass(frozen=True)
class FaceConfig:
    """Cấu hình nhận diện khuôn mặt (Bật/tắt, đường dẫn lưu ảnh người quen, ngưỡng sai số)."""
    enabled: bool = True
    known_faces_dir: str = "data/known_faces"
    similarity_threshold: float = 0.40
    score_threshold: float = 0.45
    process_every_n_frames: int = 2


@dataclass(frozen=True)
class ProjectConfig:
    """Class tổng hợp toàn bộ các cấu hình ở trên."""
    detector: DetectorConfig = DetectorConfig()
    app: AppConfig = AppConfig()
    ai: AIConfig = AIConfig()
    face: FaceConfig = FaceConfig()


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    return value if isinstance(value, dict) else {}


def load_config(path: str | Path = "configs/default.yaml") -> ProjectConfig:
    """Hàm đọc file yaml và ánh xạ (map) vào các Class cấu hình."""
    import yaml

    config_path = Path(path)
    if not config_path.exists():
        return ProjectConfig()

    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    detector = DetectorConfig(**_section(data, "detector"))
    app = AppConfig(**_section(data, "app"))
    ai = AIConfig(**_section(data, "ai"))
    face = FaceConfig(**_section(data, "face"))
    return ProjectConfig(detector=detector, app=app, ai=ai, face=face)

