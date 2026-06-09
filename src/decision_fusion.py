from __future__ import annotations

from dataclasses import replace

from src.ai_classifier import AIPrediction
from src.config import AIConfig
from src.fall_detector import DetectionResult, FallState


def fuse_detection_with_ai(
    result: DetectionResult,
    ai_prediction: AIPrediction,
    config: AIConfig,
) -> DetectionResult:
    """Optionally let the AI classifier assist rule-based states.

    The fusion is intentionally conservative: AI cannot turn a normal pose into a
    fall by itself. It can only accelerate a warning once the rule detector already
    sees lying or fall-like evidence.
    """

    if config.decision_mode.lower() != "assist":
        return result
    if not ai_prediction.enabled or ai_prediction.probability < config.alert_probability:
        return result
    if result.abnormal_frames < max(1, config.assist_min_frames):
        return result
    if result.state not in {FallState.LYING, FallState.POSSIBLE_FALL, FallState.FALLEN}:
        return result

    if result.state == FallState.LYING:
        return replace(result, state=FallState.POSSIBLE_FALL)
    if result.state == FallState.POSSIBLE_FALL:
        return replace(result, state=FallState.FALLEN)
    return result
