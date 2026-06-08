from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DetectorConfig:
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
    camera_width: int = 1280
    camera_height: int = 720
    draw_landmarks: bool = True
    event_log_path: str = "data/events.csv"


@dataclass(frozen=True)
class AIConfig:
    enabled: bool = False
    model_path: str = "models/fall_classifier.joblib"
    alert_probability: float = 0.70
    smoothing_frames: int = 5


@dataclass(frozen=True)
class ProjectConfig:
    detector: DetectorConfig = DetectorConfig()
    app: AppConfig = AppConfig()
    ai: AIConfig = AIConfig()


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    return value if isinstance(value, dict) else {}


def load_config(path: str | Path = "configs/default.yaml") -> ProjectConfig:
    import yaml

    config_path = Path(path)
    if not config_path.exists():
        return ProjectConfig()

    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    detector = DetectorConfig(**_section(data, "detector"))
    app = AppConfig(**_section(data, "app"))
    ai = AIConfig(**_section(data, "ai"))
    return ProjectConfig(detector=detector, app=app, ai=ai)
