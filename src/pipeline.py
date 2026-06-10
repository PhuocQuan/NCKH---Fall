from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from typing import Any

from src.ai_classifier import AIPrediction, FallAIClassifier
from src.config import ProjectConfig
from src.decision_fusion import fuse_detection_with_ai
from src.event_logger import EventLogger
from src.feature_extractor import LandmarkFeatureBuffer
from src.fall_detector import DetectionResult, FallDetector
from src.pose_estimator import PoseEstimator
from src.runtime_metrics import FPSCounter


@dataclass(frozen=True)
class PipelineResult:
    has_pose: bool
    fps: float
    pose_ms: float
    detection: DetectionResult | None
    ai_prediction: AIPrediction | None
    pose_results: Any
    event_logged: bool
    pose_lost_grace: bool


class FallDetectionPipeline:
    """Shared realtime processing loop for CLI and desktop apps."""

    def __init__(
        self,
        config: ProjectConfig,
        source: int | str | None = None,
    ) -> None:
        self.config = config
        self.source = source
        self.detector = FallDetector(config.detector)
        self.feature_buffer = LandmarkFeatureBuffer(
            window_size=round(config.detector.assumed_fps)
        )
        self.ai_classifier = FallAIClassifier(config.ai)
        self.estimator = PoseEstimator(config.pose)
        self.logger = EventLogger(config.app.event_log_path)
        self.logger.open_session()
        self.fps_counter = FPSCounter(window_size=round(config.detector.assumed_fps))
        self._pose_lost_frames = 0
        self._last_detection: DetectionResult | None = None
        self._last_ai_prediction: AIPrediction | None = None
        self._ever_detected_pose = False

    @property
    def waiting_first_pose(self) -> bool:
        return not self._ever_detected_pose

    def reset(self) -> None:
        self.detector.reset()
        self.feature_buffer.reset()
        self.ai_classifier.reset()
        self._pose_lost_frames = 0
        self._last_detection = None
        self._last_ai_prediction = None
        self._ever_detected_pose = False

    def close(self) -> None:
        self.logger.close_session()
        self.estimator.close()

    def process_frame(self, frame: Any) -> PipelineResult:
        fps = self.fps_counter.tick()
        pose_estimate = self.estimator.estimate(frame)
        points = pose_estimate.points
        pose_results = pose_estimate.results
        pose_ms = pose_estimate.pose_ms

        if points:
            self._pose_lost_frames = 0
            self._ever_detected_pose = True
            features = self.feature_buffer.append(points)
            ai_prediction = self.ai_classifier.predict(features)
            result = self.detector.update(points)
            result = fuse_detection_with_ai(result, ai_prediction, self.config.ai)
            event_logged = False
            if result.event_started:
                self.logger.write(result, source=self.source, fps=fps)
                event_logged = True

            self._last_detection = result
            self._last_ai_prediction = ai_prediction
            return PipelineResult(
                has_pose=True,
                fps=fps,
                pose_ms=pose_ms,
                detection=result,
                ai_prediction=ai_prediction,
                pose_results=pose_results,
                event_logged=event_logged,
                pose_lost_grace=False,
            )

        self._pose_lost_frames += 1
        max_lost = max(1, self.config.app.max_pose_lost_frames)
        if self._pose_lost_frames < max_lost and self._last_detection is not None:
            return PipelineResult(
                has_pose=False,
                fps=fps,
                pose_ms=pose_ms,
                detection=self._last_detection,
                ai_prediction=self._last_ai_prediction,
                pose_results=pose_results,
                event_logged=False,
                pose_lost_grace=True,
            )

        self.feature_buffer.reset()
        self.detector.reset()
        self.ai_classifier.reset()
        self._last_detection = None
        self._last_ai_prediction = None
        return PipelineResult(
            has_pose=False,
            fps=fps,
            pose_ms=pose_ms,
            detection=None,
            ai_prediction=_disabled_ai_prediction(self.ai_classifier.ready),
            pose_results=pose_results,
            event_logged=False,
            pose_lost_grace=False,
        )


def build_pipeline_config(
    config: ProjectConfig,
    *,
    alert_on_long_lying: bool = False,
) -> ProjectConfig:
    if alert_on_long_lying:
        detector = replace(config.detector, alert_on_long_lying_without_fall=True)
        return replace(config, detector=detector)
    return config


def _disabled_ai_prediction(enabled: bool) -> AIPrediction:
    return AIPrediction(label="unknown", probability=0.0, enabled=enabled)
