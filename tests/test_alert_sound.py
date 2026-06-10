from unittest.mock import MagicMock

from src.alert_sound import FallAlarmTracker
from src.fall_detector import FallState


def test_alarm_tracker_triggers_on_state_entry():
    callback = MagicMock()
    tracker = FallAlarmTracker(beep_interval_frames=60, alarm_callback=callback)

    tracker.update(FallState.NORMAL)
    callback.assert_not_called()

    tracker.update(FallState.POSSIBLE_FALL)
    callback.assert_called_once()


def test_alarm_tracker_resets_after_normal_state():
    callback = MagicMock()
    tracker = FallAlarmTracker(beep_interval_frames=2, alarm_callback=callback)

    tracker.update(FallState.FALLEN)
    callback.reset_mock()
    tracker.update(FallState.NORMAL)
    tracker.update(FallState.FALLEN)
    callback.assert_called_once()
