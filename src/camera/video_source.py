from __future__ import annotations

from dataclasses import dataclass
from time import sleep

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

    def _open(self) -> cv2.VideoCapture:
        capture = cv2.VideoCapture(self.source)
        if self.width:
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        if self.height:
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        if not capture.isOpened():
            raise RuntimeError(f"Khong mo duoc nguon camera/video: {self.source}")
        return capture

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
    capture = cv2.VideoCapture(index)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    ok, frame = capture.read()
    if not capture.isOpened() or not ok or frame is None:
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

