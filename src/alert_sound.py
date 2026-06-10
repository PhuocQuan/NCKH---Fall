from __future__ import annotations

import threading
from collections.abc import Callable

from src.fall_detector import FallState
from src.ui_overlay import FALL_ALARM_STATES

try:
    import winsound  # type: ignore
except Exception:  # pragma: no cover
    winsound = None  # type: ignore


def play_alert_sound() -> None:
    """Play a fall alert sound without blocking the video loop."""

    if winsound is None:
        return

    def _beep() -> None:
        try:
            for _ in range(3):
                winsound.Beep(880, 300)
        except Exception:
            try:
                winsound.MessageBeep(winsound.MB_ICONHAND)
            except Exception:
                return

    threading.Thread(target=_beep, daemon=True).start()


class FallAlarmTracker:
    """Trigger alert sounds when entering or sustaining fall-like states."""

    def __init__(
        self,
        beep_interval_frames: int,
        *,
        alarm_callback: Callable[[], None] | None = None,
    ) -> None:
        self.beep_interval_frames = max(1, beep_interval_frames)
        self._alarm_callback = alarm_callback or play_alert_sound
        self._frames_since_beep = self.beep_interval_frames
        self._previous_state = FallState.NORMAL

    def reset(self) -> None:
        self._frames_since_beep = self.beep_interval_frames
        self._previous_state = FallState.NORMAL

    def update(self, state: FallState) -> None:
        if state in FALL_ALARM_STATES:
            if self._previous_state not in FALL_ALARM_STATES:
                self._frames_since_beep = 0
                self._alarm_callback()
            else:
                self._frames_since_beep += 1
                if self._frames_since_beep >= self.beep_interval_frames:
                    self._frames_since_beep = 0
                    self._alarm_callback()
        else:
            self._frames_since_beep = self.beep_interval_frames

        self._previous_state = state
