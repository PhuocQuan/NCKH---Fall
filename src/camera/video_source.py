from __future__ import annotations

from dataclasses import dataclass
from time import sleep
import time
import numpy as np

import cv2


@dataclass(frozen=True)
class SourceInfo:
    source: int | str
    width: int
    height: int
    fps: float


class VideoSource:
    """OpenCV video source wrapper for webcam, video files, HTTP, and RTSP URLs."""

    def __init__(
        self,
        source: int | str = 0,
        width: int | None = None,
        height: int | None = None,
        reconnect_attempts: int = 3,
        reconnect_delay_sec: float = 0.5,
    ) -> None:
        self.source = _normalize_source(source)
        self.width = width
        self.height = height
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay_sec = reconnect_delay_sec
        self.capture = self._open()

    def _open(self) -> cv2.VideoCapture | MockVideoCapture:
        import sys
        capture = None
        if sys.platform.startswith("win") and isinstance(self.source, int):
            capture = cv2.VideoCapture(self.source, cv2.CAP_DSHOW)
            
        if capture is None or not capture.isOpened():
            capture = cv2.VideoCapture(self.source)

        if capture is not None and capture.isOpened():
            if self.width:
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            if self.height:
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            return capture

        # Fallback to mock video capture if physical camera cannot be opened
        print(f"[VideoSource] Warning: Khong mo duoc camera {self.source}. Dang dung simulator.")
        return MockVideoCapture(self.source, self.width or 640, self.height or 480)

    def read(self):
        ok, frame = self.capture.read()
        if ok:
            return True, frame

        for _ in range(self.reconnect_attempts):
            self.capture.release()
            sleep(self.reconnect_delay_sec)
            self.capture = self._open()
            ok, frame = self.capture.read()
            if ok:
                return True, frame

        return False, None

    def info(self) -> SourceInfo:
        return SourceInfo(
            source=self.source,
            width=int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            height=int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            fps=float(self.capture.get(cv2.CAP_PROP_FPS)),
        )

    def release(self) -> None:
        self.capture.release()


def _normalize_source(source: int | str) -> int | str:
    if isinstance(source, int):
        return source
    text = str(source).strip()
    if text.isdigit():
        return int(text)
    return text


def probe_camera(index: int, width: int = 640, height: int = 480) -> SourceInfo | None:
    import sys
    capture = None
    if sys.platform.startswith("win"):
        capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if capture is None or not capture.isOpened():
        capture = cv2.VideoCapture(index)

    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    ok, frame = capture.read()
    if not capture.isOpened() or not ok or frame is None:
        if capture:
            capture.release()
        return None

    info = SourceInfo(
        source=index,
        width=int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
        height=int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        fps=float(capture.get(cv2.CAP_PROP_FPS)),
    )
    capture.release()
    return info


class MockVideoCapture:
    def __init__(self, source: int | str, width: int = 640, height: int = 480):
        self.source = source
        self.width = width
        self.height = height
        self._frame_count = 0

    def isOpened(self) -> bool:
        return True

    def read(self) -> tuple[bool, np.ndarray]:
        import numpy as np
        import cv2
        import time

        # Create a dark blue/black frame
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        frame[:, :] = (25, 15, 10) # dark background
        
        # Draw nice dynamic design elements to show it is active!
        # Draw grid background
        for x in range(0, self.width, 40):
            cv2.line(frame, (x, 0), (x, self.height), (35, 25, 20), 1)
        for y in range(0, self.height, 40):
            cv2.line(frame, (0, y), (self.width, y), (35, 25, 20), 1)

        # Draw simulated room/camera info
        cv2.putText(frame, f"CAM SIMULATION: {self.source}", (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (140, 160, 200), 1, cv2.LINE_AA)
        
        # Draw current timestamp
        t_str = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, t_str, (30, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 120, 150), 1, cv2.LINE_AA)
        
        # Draw simulation note
        cv2.putText(frame, "Simulation active (No webcam/RTSP stream detected)", (30, self.height - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (80, 100, 120), 1, cv2.LINE_AA)

        # Draw a simulated person walking around
        cx = self.width // 2
        cy = self.height // 2

        # Make the person move in a circle over time
        angle = (self._frame_count * 0.05)
        px = int(cx + 100 * np.cos(angle))
        py = int(cy + 40 * np.sin(angle))
        
        # Draw a head
        cv2.circle(frame, (px, py - 35), 12, (0, 200, 80), -1)
        # Draw torso
        cv2.line(frame, (px, py - 23), (px, py + 20), (0, 200, 80), 3)
        # Draw arms
        cv2.line(frame, (px - 20, py - 12), (px + 20, py - 12), (0, 200, 80), 2)
        # Draw legs
        cv2.line(frame, (px, py + 20), (px - 12, py + 50), (0, 200, 80), 2)
        cv2.line(frame, (px, py + 20), (px + 12, py + 50), (0, 200, 80), 2)

        self._frame_count += 1
        return True, frame

    def get(self, propId: int) -> float:
        if propId == 3: # CAP_PROP_FRAME_WIDTH
            return float(self.width)
        elif propId == 4: # CAP_PROP_FRAME_HEIGHT
            return float(self.height)
        elif propId == 5: # CAP_PROP_FPS
            return 30.0
        return 0.0

    def set(self, propId: int, value: float) -> bool:
        return True

    def release(self) -> None:
        pass

