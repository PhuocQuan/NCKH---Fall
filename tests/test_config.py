from src.config import AIConfig, load_config


def test_ai_config_defaults_keep_display_mode():
    config = AIConfig()

    assert config.decision_mode == "display"
    assert config.assist_min_frames == 5


def test_load_config_reads_ai_decision_mode(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """
ai:
  enabled: true
  decision_mode: assist
  assist_min_frames: 3
""",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.ai.enabled is True
    assert config.ai.decision_mode == "assist"
    assert config.ai.assist_min_frames == 3


def test_load_config_reads_pose_section(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """
pose:
  input_width: 480
  input_height: 270
  model_complexity: 1
""",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.pose.input_width == 480
    assert config.pose.input_height == 270
    assert config.pose.model_complexity == 1
