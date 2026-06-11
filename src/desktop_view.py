from __future__ import annotations

from time import perf_counter
from typing import Any

import cv2
from PIL import Image, ImageTk

from src.ui_theme import (
    PROFILE_DISPLAY,
    STATUS_DISPLAY,
    profile_combo_values,
    profile_from_combo,
    profile_to_combo,
)


class UiRefreshGate:
    """Limit sidebar text updates to reduce Tkinter overhead."""

    def __init__(self, interval_ms: int = 120) -> None:
        self._interval = interval_ms / 1000.0
        self._last_refresh = 0.0
        self._last_status = ""

    def should_refresh(self, status: str, *, force: bool = False) -> bool:
        now = perf_counter()
        if force or status != self._last_status:
            self._last_status = status
            self._last_refresh = now
            return True
        if now - self._last_refresh >= self._interval:
            self._last_refresh = now
            return True
        return False


class FramePresenter:
    """Render BGR frames into a Tk label efficiently."""

    def __init__(self, min_width: int = 320, min_height: int = 240) -> None:
        self.min_width = min_width
        self.min_height = min_height
        self._photo: ImageTk.PhotoImage | None = None
        self._cached_label_size = (0, 0)

    @property
    def photo(self) -> ImageTk.PhotoImage | None:
        return self._photo

    def show_placeholder(self, label: Any, text: str) -> None:
        width = max(self.min_width, label.winfo_width())
        height = max(self.min_height, label.winfo_height())
        image = Image.new("RGB", (width, height), color=(18, 18, 18))
        self._photo = ImageTk.PhotoImage(image)
        label.configure(image=self._photo, text=text, compound="center")

    def render(self, frame_bgr: Any, label: Any) -> None:
        width = max(self.min_width, label.winfo_width())
        height = max(self.min_height, label.winfo_height())
        if (width, height) != self._cached_label_size:
            self._cached_label_size = (width, height)

        frame_h, frame_w = frame_bgr.shape[:2]
        scale = min(width / frame_w, height / frame_h)
        target_w = max(1, int(frame_w * scale))
        target_h = max(1, int(frame_h * scale))
        if target_w != frame_w or target_h != frame_h:
            display = cv2.resize(frame_bgr, (target_w, target_h), interpolation=cv2.INTER_AREA)
        else:
            display = frame_bgr

        rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        self._photo = ImageTk.PhotoImage(Image.fromarray(rgb))
        label.configure(image=self._photo, text="")
