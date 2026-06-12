from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2

from src.alert_sound import FallAlarmTracker
from src.config import ProjectConfig, load_config
from src.fall_detector import FallState
from src.pipeline import FallDetectionPipeline, PipelineResult, build_pipeline_config
from src.snapshot import DEFAULT_SNAPSHOT_DIR, save_alert_snapshot
from src.ui_theme import STATUS_DISPLAY
from src.ui_overlay import draw_no_pose, draw_status
from src.user_settings import apply_user_settings, load_user_settings
from src.video_source import VideoSource

MJPEG_BOUNDARY = b"--frame"
STREAM_MAX_WIDTH = 640
STREAM_JPEG_QUALITY = 72


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _status_key(pipeline_result: PipelineResult, waiting_first_pose: bool) -> str:
    if pipeline_result.has_pose and pipeline_result.detection is not None:
        return pipeline_result.detection.state.value.upper()
    if pipeline_result.pose_lost_grace:
        return "TRACKING"
    if waiting_first_pose:
        return "CHO POSE"
    return "NO POSE"


def _latest_snapshot(snapshot_dir: Path) -> str | None:
    if not snapshot_dir.exists():
        return None
    files = sorted(snapshot_dir.glob("alert_*.jpg"), key=lambda path: path.stat().st_mtime)
    if not files:
        return None
    return files[-1].name


@dataclass
class MonitorStatus:
    running: bool = False
    source: str = ""
    camera_id: str | None = None
    status: str = "READY"
    status_label: str = STATUS_DISPLAY["READY"]
    state: str | None = None
    fps: float | None = None
    pose_ms: float | None = None
    lying_seconds: float | None = None
    has_pose: bool = False
    last_alert_at: str | None = None
    last_snapshot: str | None = None
    updated_at: str = field(default_factory=_utc_now)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "source": self.source,
            "camera_id": self.camera_id,
            "status": self.status,
            "status_label": self.status_label,
            "state": self.state,
            "fps": self.fps,
            "pose_ms": self.pose_ms,
            "lying_seconds": self.lying_seconds,
            "has_pose": self.has_pose,
            "last_alert_at": self.last_alert_at,
            "last_snapshot": self.last_snapshot,
            "updated_at": self.updated_at,
            "error": self.error,
        }


class MobileMonitorService:
    """Background fall-detection loop for the mobile API server."""

    def __init__(
        self,
        *,
        config_path: str = "configs/default.yaml",
        user_settings_path: str = "configs/user.yaml",
        snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
    ) -> None:
        self._config_path = config_path
        self._user_settings_path = user_settings_path
        self._snapshot_dir = snapshot_dir
        self._lock = threading.Lock()
        self._frame_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._active_camera_id: str | None = None
        self._pipeline: FallDetectionPipeline | None = None
        self._video: VideoSource | None = None
        self._status = MonitorStatus()
        self._config: ProjectConfig | None = None
        self._latest_jpeg: bytes | None = None
        self._alarm: FallAlarmTracker | None = None

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            return self._status.to_dict()

    def is_running(self) -> bool:
        with self._lock:
            return self._status.running

    def get_latest_jpeg(self) -> bytes | None:
        with self._frame_lock:
            return self._latest_jpeg

    def iter_mjpeg(self) -> Iterator[bytes]:
        while not self._stop_event.is_set():
            if not self.is_running():
                break
            jpeg = self.get_latest_jpeg()
            if jpeg:
                yield (
                    MJPEG_BOUNDARY
                    + b"\r\nContent-Type: image/jpeg\r\n\r\n"
                    + jpeg
                    + b"\r\n"
                )
            time.sleep(1.0 / 20.0)

    def start(
        self,
        source: int | str = 0,
        *,
        config_path: str | None = None,
        camera_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if self._status.running:
                raise RuntimeError("Monitor dang chay. Hay goi stop() truoc.")

        if config_path:
            self._config_path = config_path

        self._active_camera_id = camera_id
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            args=(source,),
            name="mobile-monitor",
            daemon=True,
        )
        self._thread.start()

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            with self._lock:
                if self._status.running:
                    return self._status.to_dict()
                if self._status.error:
                    raise RuntimeError(self._status.error)
            time.sleep(0.05)

        with self._lock:
            if self._status.error:
                raise RuntimeError(self._status.error)
            return self._status.to_dict()

    def stop(self) -> dict[str, Any]:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=3.0)
        self._cleanup_runtime()
        with self._lock:
            self._status = MonitorStatus(
                status="STOPPED",
                status_label=STATUS_DISPLAY["STOPPED"],
                last_snapshot=_latest_snapshot(self._snapshot_dir),
            )
            return self._status.to_dict()

    def reset(self) -> dict[str, Any]:
        with self._lock:
            if self._pipeline is not None:
                self._pipeline.reset()
            return self._status.to_dict()

    def read_events(self, limit: int = 20) -> list[dict[str, str]]:
        config = self._config
        if config is None:
            config = apply_user_settings(
                load_config(self._config_path),
                load_user_settings(self._user_settings_path),
            )
        from src.cloud_db import use_cloud_storage
        from src.event_logger import EventLogger

        if use_cloud_storage():
            from src.cloud_sync import read_fall_events_recent

            cloud_events = read_fall_events_recent(limit=limit)
            if cloud_events:
                return cloud_events
        return EventLogger(config.app.event_log_path).read_recent(limit=limit)

    def snapshot_path(self, name: str) -> Path:
        path = (self._snapshot_dir / Path(name).name).resolve()
        snapshot_root = self._snapshot_dir.resolve()
        if snapshot_root not in path.parents and path != snapshot_root:
            raise ValueError("Duong dan snapshot khong hop le.")
        if not path.exists():
            raise FileNotFoundError(f"Khong tim thay snapshot: {name}")
        return path

    def latest_snapshot_path(self) -> Path | None:
        name = _latest_snapshot(self._snapshot_dir)
        if name is None:
            return None
        return self.snapshot_path(name)

    def _run_loop(self, source: int | str) -> None:
        pipeline: FallDetectionPipeline | None = None
        video: VideoSource | None = None
        try:
            config = apply_user_settings(
                load_config(self._config_path),
                load_user_settings(self._user_settings_path),
            )
            config = build_pipeline_config(config)
            self._config = config
            video = VideoSource(
                source,
                width=config.app.camera_width,
                height=config.app.camera_height,
            )
            pipeline = FallDetectionPipeline(config, source=source)
            self._pipeline = pipeline
            self._video = video
            settings = load_user_settings(self._user_settings_path)
            self._alarm = FallAlarmTracker(
                beep_interval_frames=max(1, round(config.detector.assumed_fps * 2)),
            )

            with self._lock:
                self._status = MonitorStatus(
                    running=True,
                    source=str(source),
                    camera_id=self._active_camera_id,
                    status="RUNNING",
                    status_label=STATUS_DISPLAY["RUNNING"],
                    last_snapshot=_latest_snapshot(self._snapshot_dir),
                )

            while not self._stop_event.is_set():
                ok, frame = video.read()
                if not ok:
                    with self._lock:
                        self._status.error = "Mat nguon video."
                    break

                result = pipeline.process_frame(frame)
                self._update_status(result, pipeline, settings.snapshot_on_alert, frame)
                self._publish_frame(frame, result, pipeline)

                if self._stop_event.is_set():
                    break
                time.sleep(0.001)
        except Exception as exc:  # pragma: no cover - surfaced via status.error
            with self._lock:
                self._status.error = str(exc)
        finally:
            if pipeline is not None:
                pipeline.close()
            if video is not None:
                video.release()
            with self._lock:
                self._status.running = False
                if self._status.status == "RUNNING":
                    self._status.status = "STOPPED"
                    self._status.status_label = STATUS_DISPLAY["STOPPED"]
                self._status.updated_at = _utc_now()
        self._pipeline = None
        self._video = None
        if self._alarm is not None:
            self._alarm.reset()
            self._alarm = None
        self._clear_frame()

    def _clear_frame(self) -> None:
        with self._frame_lock:
            self._latest_jpeg = None

    def _publish_frame(
        self,
        frame: Any,
        pipeline_result: PipelineResult,
        pipeline: FallDetectionPipeline,
    ) -> None:
        display = frame.copy()
        config = pipeline.config

        if pipeline_result.has_pose and pipeline_result.detection is not None:
            if config.app.draw_landmarks:
                pipeline.estimator.draw(display, pipeline_result.pose_results)
            draw_status(
                display,
                pipeline_result.detection,
                pipeline_result.ai_prediction,
                config.ai.decision_mode,
                pipeline_result.fps,
                pose_ms=pipeline_result.pose_ms,
            )
        elif pipeline_result.pose_lost_grace and pipeline_result.detection is not None:
            draw_status(
                display,
                pipeline_result.detection,
                pipeline_result.ai_prediction,
                config.ai.decision_mode,
                pipeline_result.fps,
                pose_ms=pipeline_result.pose_ms,
            )
            draw_no_pose(
                display,
                pipeline_result.fps,
                grace=True,
                pose_ms=pipeline_result.pose_ms,
            )
        else:
            draw_no_pose(
                display,
                pipeline_result.fps,
                waiting_first_pose=pipeline.waiting_first_pose,
                pose_ms=pipeline_result.pose_ms,
            )

        height, width = display.shape[:2]
        if width > STREAM_MAX_WIDTH:
            scale = STREAM_MAX_WIDTH / width
            display = cv2.resize(
                display,
                (STREAM_MAX_WIDTH, max(1, int(height * scale))),
                interpolation=cv2.INTER_AREA,
            )

        ok, encoded = cv2.imencode(
            ".jpg",
            display,
            [int(cv2.IMWRITE_JPEG_QUALITY), STREAM_JPEG_QUALITY],
        )
        if not ok:
            return
        with self._frame_lock:
            self._latest_jpeg = encoded.tobytes()

    def _update_status(
        self,
        pipeline_result: PipelineResult,
        pipeline: FallDetectionPipeline,
        snapshot_on_alert: bool,
        frame: Any,
    ) -> None:
        key = _status_key(pipeline_result, pipeline.waiting_first_pose)
        detection = pipeline_result.detection
        state_value = detection.state.value if detection is not None else None
        lying_seconds = detection.lying_seconds if detection is not None else None

        last_alert_at = None
        last_snapshot = _latest_snapshot(self._snapshot_dir)
        if pipeline_result.event_logged:
            last_alert_at = _utc_now()
            if snapshot_on_alert:
                try:
                    saved = save_alert_snapshot(frame, self._snapshot_dir)
                    last_snapshot = saved.name
                except OSError:
                    pass

        with self._lock:
            if last_alert_at is not None:
                self._status.last_alert_at = last_alert_at
            if last_snapshot is not None:
                self._status.last_snapshot = last_snapshot
            self._status.status = key
            self._status.status_label = STATUS_DISPLAY.get(key, key)
            self._status.state = state_value
            self._status.fps = round(pipeline_result.fps, 2)
            self._status.pose_ms = round(pipeline_result.pose_ms, 2)
            self._status.lying_seconds = (
                round(lying_seconds, 2) if lying_seconds is not None else None
            )
            self._status.has_pose = pipeline_result.has_pose
            self._status.updated_at = _utc_now()
            self._status.error = None

        if self._alarm is not None and detection is not None:
            self._alarm.update(detection.state)
        elif self._alarm is not None:
            self._alarm.update(FallState.NORMAL)

    def _cleanup_runtime(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=3.0)
        if self._pipeline is not None:
            self._pipeline.close()
        if self._video is not None:
            self._video.release()
        self._pipeline = None
        self._video = None
        self._thread = None
        self._clear_frame()
