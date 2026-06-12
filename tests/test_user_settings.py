from src.config import ProjectConfig
from src.user_settings import (
    UserSettings,
    apply_user_settings,
    load_user_settings,
    save_user_settings,
)


def test_save_and_load_user_settings(tmp_path):
    path = tmp_path / "user.yaml"
    settings = UserSettings(
        profile="elderly",
        alert_after_seconds=8.0,
        draw_landmarks=False,
        snapshot_on_alert=True,
    )

    save_user_settings(settings, path)
    loaded = load_user_settings(path)

    assert loaded == settings


def test_apply_user_settings_updates_detector_and_app():
    config = ProjectConfig()
    settings = UserSettings(profile="child", alert_after_seconds=12.0, draw_landmarks=False)

    updated = apply_user_settings(config, settings)

    assert updated.detector.profile == "child"
    assert updated.detector.alert_after_seconds == 12.0
    assert updated.app.draw_landmarks is False


def test_load_user_settings_falls_back_for_invalid_profile(tmp_path):
    path = tmp_path / "user.yaml"
    path.write_text("profile: unknown\n", encoding="utf-8")

    loaded = load_user_settings(path)

    assert loaded.profile == "default"
