from __future__ import annotations

from collections import deque
from time import perf_counter


class FPSCounter:
    def __init__(self, window_size: int = 30) -> None:
        self._timestamps: deque[float] = deque(maxlen=max(2, window_size))

    def tick(self) -> float:
        self._timestamps.append(perf_counter())
        return self.fps

    @property
    def fps(self) -> float:
        if len(self._timestamps) < 2:
            return 0.0

        elapsed = self._timestamps[-1] - self._timestamps[0]
        if elapsed <= 0:
            return 0.0
        return (len(self._timestamps) - 1) / elapsed
