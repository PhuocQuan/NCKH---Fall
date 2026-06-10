from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from src.config import ProjectConfig

PROFILE_OPTIONS = ("default", "elderly", "child", "pregnant", "disabled")
DEFAULT_USER_SETTINGS_PATH = Path("configs/user.yaml")


@dataclass(frozen=True)
class UserSettings:
    profile: str = "default"
    alert_after_seconds: float = 10.0
    draw_landmarks: bool = True
    snapshot_on_alert: bool = True


def load_user_settings(path: str | Path = DEFAULT_USER_SETTINGS_PATH) -> UserSettings:
    import yaml

    settings_path = Path(path)
    if not settings_path.exists():
        return UserSettings()

    data = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}
    section = data if isinstance(data, dict) else {}
    profile = str(section.get("profile", "default")).strip().lower()
    if profile not in PROFILE_OPTIONS:
        profile = "default"
    return UserSettings(
        profile=profile,
        alert_after_seconds=float(section.get("alert_after_seconds", 10.0)),
        draw_landmarks=bool(section.get("draw_landmarks", True)),
        snapshot_on_alert=bool(section.get("snapshot_on_alert", True)),
    )


def save_user_settings(
    settings: UserSettings,
    path: str | Path = DEFAULT_USER_SETTINGS_PATH,
) -> Path:
    import yaml

    settings_path = Path(path)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = asdict(settings)
    settings_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return settings_path


def apply_user_settings(config: ProjectConfig, settings: UserSettings) -> ProjectConfig:
    detector = replace(
        config.detector,
        profile=settings.profile,
        alert_after_seconds=max(1.0, float(settings.alert_after_seconds)),
    )
    app = replace(config.app, draw_landmarks=settings.draw_landmarks)
    return replace(config, detector=detector, app=app)
