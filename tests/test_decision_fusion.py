from src.ai_classifier import AIPrediction
from src.config import AIConfig
from src.decision_fusion import fuse_detection_with_ai
from src.fall_detector import DetectionResult, FallState


def _result(state: FallState, abnormal_frames: int = 5) -> DetectionResult:
    return DetectionResult(
        state=state,
        torso_angle_deg=70.0,
        head_hip_delta=0.05,
        hip_velocity=0.04,
        angle_velocity_deg=20.0,
        abnormal_frames=abnormal_frames,
        lying_seconds=0.5,
        profile="default",
        fall_like_transition=True,
    )


def test_display_mode_keeps_rule_based_result():
    result = _result(FallState.POSSIBLE_FALL)
    prediction = AIPrediction(label="fall", probability=0.99, enabled=True)

    fused = fuse_detection_with_ai(result, prediction, AIConfig(decision_mode="display"))

    assert fused.state == FallState.POSSIBLE_FALL


def test_assist_mode_does_not_raise_normal_pose():
    result = _result(FallState.NORMAL)
    prediction = AIPrediction(label="fall", probability=0.99, enabled=True)

    fused = fuse_detection_with_ai(result, prediction, AIConfig(decision_mode="assist"))

    assert fused.state == FallState.NORMAL


def test_assist_mode_raises_possible_fall_when_ai_is_confident():
    result = _result(FallState.POSSIBLE_FALL)
    prediction = AIPrediction(label="fall", probability=0.99, enabled=True)

    fused = fuse_detection_with_ai(result, prediction, AIConfig(decision_mode="assist"))

    assert fused.state == FallState.FALLEN


def test_assist_mode_requires_enough_abnormal_frames():
    result = _result(FallState.POSSIBLE_FALL, abnormal_frames=1)
    prediction = AIPrediction(label="fall", probability=0.99, enabled=True)

    fused = fuse_detection_with_ai(
        result,
        prediction,
        AIConfig(decision_mode="assist", assist_min_frames=5),
    )

    assert fused.state == FallState.POSSIBLE_FALL
