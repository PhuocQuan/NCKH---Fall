from src.config import DetectorConfig
from src.fall_detector import FallDetector, FallState, Point


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


def falling_sequence():
    return [
        standing_pose(),
        standing_pose(),
        {
            "nose": Point(0.42, 0.42),
            "left_shoulder": Point(0.46, 0.46),
            "right_shoulder": Point(0.52, 0.49),
            "left_hip": Point(0.58, 0.64),
            "right_hip": Point(0.62, 0.66),
        },
        lying_pose(),
    ]


def test_standing_pose_is_normal():
    detector = FallDetector()

    result = detector.update(standing_pose())

    assert result.state == FallState.NORMAL
    assert result.torso_angle_deg < 30


def test_persistent_fall_like_lying_pose_becomes_fallen():
    detector = FallDetector(
        DetectorConfig(min_fall_frames=3, warning_frames=2, alert_after_seconds=10, assumed_fps=30)
    )

    states = []
    for pose in falling_sequence():
        states.append(detector.update(pose).state)
    states.extend(detector.update(lying_pose()).state for _ in range(3))

    assert states[-1] == FallState.FALLEN


def test_lying_without_fall_transition_does_not_alert():
    detector = FallDetector(DetectorConfig(min_fall_frames=5, warning_frames=2))

    result = None
    for _ in range(400):
        result = detector.update(lying_pose())

    assert result is not None
    assert result.state == FallState.LYING
    assert result.event_started is False


def test_alert_starts_after_fall_and_long_lying():
    detector = FallDetector(
        DetectorConfig(
            min_fall_frames=2,
            warning_frames=1,
            alert_after_seconds=1,
            assumed_fps=10,
            cooldown_frames=20,
        )
    )

    result = None
    event_started = False
    for pose in falling_sequence():
        result = detector.update(pose)
    for _ in range(12):
        result = detector.update(lying_pose())
        event_started = event_started or result.event_started

    assert result is not None
    assert result.state == FallState.ALERT
    assert event_started is True


def test_demo_mode_alerts_on_long_lying_without_fall_transition():
    detector = FallDetector(
        DetectorConfig(
            min_fall_frames=2,
            alert_after_seconds=1,
            assumed_fps=10,
            alert_on_long_lying_without_fall=True,
        )
    )

    result = None
    event_started = False
    for _ in range(12):
        result = detector.update(lying_pose())
        event_started = event_started or result.event_started

    assert result is not None
    assert result.state == FallState.ALERT
    assert event_started is True
