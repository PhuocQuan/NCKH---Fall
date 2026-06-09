import csv

from src.event_logger import EventLogger
from src.fall_detector import DetectionResult, FallState


def _alert_result() -> DetectionResult:
    return DetectionResult(
        state=FallState.ALERT,
        torso_angle_deg=80.0,
        head_hip_delta=0.01,
        hip_velocity=0.05,
        angle_velocity_deg=25.0,
        abnormal_frames=10,
        lying_seconds=10.0,
        profile="default",
        fall_like_transition=True,
        event_started=True,
    )


def test_event_logger_writes_source_and_fps(tmp_path):
    path = tmp_path / "events.csv"
    logger = EventLogger(path)

    logger.write(_alert_result(), source="camera-0", fps=24.5)

    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert rows[0]["source"] == "camera-0"
    assert rows[0]["fps"] == "24.50"
    assert rows[0]["state"] == "alert"


def test_event_logger_preserves_existing_header(tmp_path):
    path = tmp_path / "events.csv"
    path.write_text("timestamp,state\n", encoding="utf-8")
    logger = EventLogger(path)

    logger.write(_alert_result(), source="camera-0", fps=24.5)

    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert rows[0]["state"] == "alert"
    assert "source" not in rows[0]
