from unittest.mock import MagicMock

from src.config import AppConfig, DetectorConfig, ProjectConfig
from src.fall_detector import FallState, Point
from src.pose_estimator import PoseEstimateResult
from src.pipeline import FallDetectionPipeline, build_pipeline_config


def standing_pose():
    return {
        "nose": Point(0.50, 0.18),
        "left_shoulder": Point(0.44, 0.34),
        "right_shoulder": Point(0.56, 0.34),
        "left_hip": Point(0.46, 0.62),
        "right_hip": Point(0.54, 0.62),
    }


def lying_pose():
    return {
        "nose": Point(0.30, 0.60),
        "left_shoulder": Point(0.43, 0.61),
        "right_shoulder": Point(0.45, 0.63),
        "left_hip": Point(0.70, 0.62),
        "right_hip": Point(0.72, 0.64),
    }


def _pipeline_with_short_grace() -> FallDetectionPipeline:
    config = ProjectConfig(
        detector=DetectorConfig(assumed_fps=30),
        app=AppConfig(max_pose_lost_frames=3),
    )
    pipeline = FallDetectionPipeline(config, source="test")
    pipeline.estimator = MagicMock()
    pipeline.estimator.estimate.return_value = PoseEstimateResult(
        points=standing_pose(),
        results=None,
        pose_ms=12.5,
    )
    pipeline.estimator.draw = MagicMock()
    pipeline.estimator.close = MagicMock()
    pipeline.logger.write = MagicMock()
    return pipeline


def test_build_pipeline_config_enables_long_lying_demo_mode():
    config = ProjectConfig()
    updated = build_pipeline_config(config, alert_on_long_lying=True)
    assert updated.detector.alert_on_long_lying_without_fall is True


def test_pose_loss_grace_keeps_last_detection():
    pipeline = _pipeline_with_short_grace()
    frame = MagicMock()

    first = pipeline.process_frame(frame)
    assert first.has_pose is True
    assert first.detection is not None
    assert first.detection.state == FallState.NORMAL

    pipeline.estimator.estimate.return_value = PoseEstimateResult(
        points=None,
        results=None,
        pose_ms=8.0,
    )
    grace = pipeline.process_frame(frame)
    assert grace.has_pose is False
    assert grace.pose_lost_grace is True
    assert grace.detection == first.detection


def test_pose_loss_beyond_grace_resets_detection():
    pipeline = _pipeline_with_short_grace()
    frame = MagicMock()

    pipeline.process_frame(frame)
    pipeline.estimator.estimate.return_value = PoseEstimateResult(
        points=None,
        results=None,
        pose_ms=8.0,
    )

    for _ in range(3):
        result = pipeline.process_frame(frame)

    assert result.has_pose is False
    assert result.pose_lost_grace is False
    assert result.detection is None

    pipeline.estimator.estimate.return_value = PoseEstimateResult(
        points=lying_pose(),
        results=None,
        pose_ms=10.0,
    )
    recovered = pipeline.process_frame(frame)
    assert recovered.has_pose is True
    assert recovered.detection is not None
    assert recovered.detection.state == FallState.LYING


def test_pipeline_logs_alert_event():
    config = ProjectConfig(
        detector=DetectorConfig(
            assumed_fps=30,
            min_fall_frames=1,
            alert_after_seconds=0.0,
            alert_on_long_lying_without_fall=True,
        )
    )
    pipeline = FallDetectionPipeline(config, source="camera-0")
    pipeline.estimator = MagicMock()
    pipeline.estimator.estimate.return_value = PoseEstimateResult(
        points=lying_pose(),
        results=None,
        pose_ms=10.0,
    )
    pipeline.estimator.draw = MagicMock()
    pipeline.estimator.close = MagicMock()
    pipeline.logger.write = MagicMock()
    frame = MagicMock()

    logged = False
    for _ in range(3):
        result = pipeline.process_frame(frame)
        logged = logged or result.event_logged

    assert logged is True
    pipeline.logger.write.assert_called()
