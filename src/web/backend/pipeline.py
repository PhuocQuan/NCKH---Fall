"""Fall detection pipeline for web streaming."""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass
from typing import Any

try:
    import winsound  # type: ignore
except Exception:  # pragma: no cover
    winsound = None  # type: ignore


def _import_runtime():
    import cv2

    from src.ai.ai_classifier import FallAIClassifier
    from src.camera.video_source import VideoSource
    from src.core.config import load_config
    from src.core.event_logger import EventLogger
    from src.detection.feature_extractor import LandmarkFeatureBuffer
    from src.detection.fall_detector import FallDetector, FallState
    from src.detection.pose_estimator import PoseEstimator

    return {
        "cv2": cv2,
        "FallAIClassifier": FallAIClassifier,
        "VideoSource": VideoSource,
        "load_config": load_config,
        "EventLogger": EventLogger,
        "LandmarkFeatureBuffer": LandmarkFeatureBuffer,
        "FallDetector": FallDetector,
        "FallState": FallState,
        "PoseEstimator": PoseEstimator,
    }


@dataclass
class PipelineStatus:
    running: bool = False
    source: str = ""
    state: str = "normal"
    torso_angle_deg: float = 0.0
    lying_seconds: float = 0.0
    hip_velocity: float = 0.0
    angle_velocity_deg: float = 0.0
    profile: str = "default"
    ai_label: str = "disabled"
    ai_probability: float = 0.0
    ai_enabled: bool = False
    pose_detected: bool = False
    fps: float = 0.0
    latency_ms: float = 0.0
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FallDetectionPipeline:
    """Background thread chạy camera + FallDetector, phục vụ MJPEG stream."""

    def __init__(self, config_path: str = "configs/default.yaml") -> None:
        self.config_path = config_path
        self._lock = threading.Lock()
        self._latest_jpeg: bytes | None = None
        self._status = PipelineStatus()
        self._thread: threading.Thread | None = None
        self._running = False
        self._video: VideoSource | None = None
        self._estimator: PoseEstimator | None = None
        self._detector: FallDetector | None = None
        self._feature_buffer: LandmarkFeatureBuffer | None = None
        self._ai_classifier: FallAIClassifier | None = None
        self._logger: EventLogger | None = None
        self._recent_alerts: list[dict[str, Any]] = []
        self._runtime: dict[str, Any] | None = None
        from collections import deque
        self._frame_buffer = deque(maxlen=150)


    @property
    def status(self) -> PipelineStatus:
        with self._lock:
            return PipelineStatus(**self._status.to_dict())

    def recent_alerts(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._recent_alerts)

    def get_jpeg_frame(self) -> bytes | None:
        with self._lock:
            return self._latest_jpeg

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def start(self, source: str | int = "0", camera_id: str | None = None) -> None:
        with self._lock:
            if self._running:
                return

        self.stop()
        self.camera_id = camera_id or "CAM-LOCAL"
        try:
            runtime = _import_runtime()
        except ImportError as exc:
            raise RuntimeError(
                "Thieu thu vien AI. Chay: pip install -r requirements.txt"
            ) from exc
        self._runtime = runtime
        load_config = runtime["load_config"]
        FallDetector = runtime["FallDetector"]
        LandmarkFeatureBuffer = runtime["LandmarkFeatureBuffer"]
        FallAIClassifier = runtime["FallAIClassifier"]
        PoseEstimator = runtime["PoseEstimator"]
        EventLogger = runtime["EventLogger"]
        VideoSource = runtime["VideoSource"]

        config = load_config(self.config_path)
        self._detector = FallDetector(config.detector)
        self._feature_buffer = LandmarkFeatureBuffer(window_size=round(config.detector.assumed_fps))
        self._ai_classifier = FallAIClassifier(config.ai)
        self._estimator = PoseEstimator(model_complexity=config.app.model_complexity)
        self._logger = EventLogger(config.app.event_log_path)

        normalized = int(source) if str(source).isdigit() else source
        self._video = VideoSource(
            source=normalized,
            width=config.app.camera_width,
            height=config.app.camera_height,
        )
        self._draw_landmarks = config.app.draw_landmarks
        self._running = True
        with self._lock:
            self._status = PipelineStatus(running=True, source=str(source))
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        if self._estimator:
            self._estimator.close()
            self._estimator = None
        if self._video:
            self._video.release()
            self._video = None
        self._detector = None
        self._feature_buffer = None
        self._ai_classifier = None
        self._runtime = None
        with self._lock:
            self._status = PipelineStatus()
            self._latest_jpeg = None

    def _loop(self) -> None:
        runtime = self._runtime
        if not runtime:
            return
        cv2 = runtime["cv2"]
        FallState = runtime["FallState"]
        state_colors = {
            FallState.NORMAL: (70, 200, 90),
            FallState.LYING: (180, 180, 180),
            FallState.WARNING: (0, 190, 255),
            FallState.POSSIBLE_FALL: (0, 140, 255),
            FallState.FALLEN: (40, 40, 230),
            FallState.ALERT: (0, 0, 255),
        }
        frames = 0
        started = time.perf_counter()
        while self._running and self._video and self._estimator and self._detector:
            frame_start = time.perf_counter()
            ok, frame = self._video.read()
            if not ok or frame is None:
                with self._lock:
                    self._status.last_error = "Khong doc duoc frame tu camera."
                time.sleep(0.05)
                continue

            points, pose_results = self._estimator.estimate(frame)
            ai_prediction = None
            if points and self._feature_buffer and self._ai_classifier:
                features = self._feature_buffer.append(points)
                ai_prediction = self._ai_classifier.predict(features)
                result = self._detector.update(points)
                
                event_triggered = result.event_started and self._logger
                
                if self._draw_landmarks:
                    self._estimator.draw(frame, pose_results)
                _draw_status(frame, result, ai_prediction, state_colors, cv2)
                
                # Append frame to history buffer
                self._frame_buffer.append(frame.copy())
                
                if event_triggered:
                    alert_id = f"AL-{int(time.time())}"
                    self._logger.write(result)
                    self._push_alert(result, alert_id)
                    
                    # Play alert sound in a separate background thread
                    threading.Thread(target=_play_alert_sound, daemon=True).start()
                    
                    # Save snapshot and video in a separate background thread
                    snapshot_frame = frame.copy()
                    video_frames = list(self._frame_buffer)
                    threading.Thread(
                        target=self._save_event_media,
                        args=(alert_id, snapshot_frame, video_frames),
                        daemon=True
                    ).start()
                
                status = PipelineStatus(
                    running=True,
                    source=self._status.source,
                    state=result.state.value,
                    torso_angle_deg=result.torso_angle_deg,
                    lying_seconds=result.lying_seconds,
                    hip_velocity=result.hip_velocity,
                    angle_velocity_deg=result.angle_velocity_deg,
                    profile=result.profile,
                    ai_label=ai_prediction.label if ai_prediction else "disabled",
                    ai_probability=ai_prediction.probability if ai_prediction else 0.0,
                    ai_enabled=bool(ai_prediction and ai_prediction.enabled),
                    pose_detected=True,
                    last_error="",
                )
            else:
                if self._feature_buffer:
                    self._feature_buffer.reset()
                _draw_text(frame, "No pose detected", (20, 40), (180, 180, 180), cv2)
                
                # Append to frame buffer as well so that video is continuous
                self._frame_buffer.append(frame.copy())
                
                status = PipelineStatus(
                    running=True,
                    source=self._status.source,
                    state="normal",
                    pose_detected=False,
                    last_error="",
                )

            frames += 1
            elapsed = max(time.perf_counter() - started, 0.001)
            status.fps = round(frames / elapsed, 1)
            status.latency_ms = round((time.perf_counter() - frame_start) * 1000, 1)


            ok_enc, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if ok_enc:
                with self._lock:
                    self._latest_jpeg = jpeg.tobytes()
                    self._status = status

            time.sleep(0.001)

    def _push_alert(self, result, alert_id: str) -> None:
        from datetime import datetime

        FallState = self._runtime["FallState"] if self._runtime else None
        level = "Cao"
        if FallState and result.state == FallState.ALERT:
            level = "Khẩn cấp"
        alert = {
            "id": alert_id,
            "time": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "camera": getattr(self, "camera_id", "CAM-LOCAL"),
            "person": "Phat hien tu AI",
            "confidence": min(99, int(70 + result.torso_angle_deg / 2)),
            "status": "Chưa xử lý",
            "level": level,
            "media": alert_id,
            "state": result.state.value,
            "cloud_img_url": None,
            "cloud_video_url": None,
        }
        self._recent_alerts.insert(0, alert)
        self._recent_alerts = self._recent_alerts[:50]

        try:
            from src.web.backend.db import get_db_client
            with get_db_client() as client:
                client.execute(
                    "INSERT INTO alerts (id, time, camera, person, confidence, status, level, media, state, cloud_img_url, cloud_video_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [alert_id, alert["time"], alert["camera"], alert["person"], alert["confidence"], alert["status"], alert["level"], alert["media"], alert["state"], None, None]
                )
        except Exception as e:
            print(f"[Database Error] Khong the luu alert vao Turso: {e}")

    def _save_event_media(self, alert_id: str, snapshot_frame, video_frames: list) -> None:
        import os
        from pathlib import Path
        
        project_root = Path(__file__).resolve().parents[3]
        media_dir = project_root / "data" / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Save snapshot image
        img_path = media_dir / f"{alert_id}.jpg"
        cv2 = self._runtime["cv2"] if self._runtime else None
        if cv2 is not None:
            cv2.imwrite(str(img_path), snapshot_frame)
            
            # 2. Save video clip
            video_written = False
            video_path = media_dir / f"{alert_id}.mp4"
            if video_frames:
                height, width = video_frames[0].shape[:2]
                
                # Try multiple common codecs for browser compatibility
                for codec in ["avc1", "H264", "mp4v"]:
                    try:
                        fourcc = cv2.VideoWriter_fourcc(*codec)
                        writer = cv2.VideoWriter(str(video_path), fourcc, 25.0, (width, height))
                        if writer.isOpened():
                            for f in video_frames:
                                writer.write(f)
                            writer.release()
                            video_written = True
                            break
                    except Exception:
                        continue
            
            # 3. Upload to Cloudinary if configured in db.json
            cloud_img_url = None
            cloud_video_url = None
            try:
                from src.web.backend.cloudinary_uploader import upload_to_cloudinary
                cloud_img_url = upload_to_cloudinary(str(img_path))
                if video_written:
                    cloud_video_url = upload_to_cloudinary(str(video_path))
            except Exception as e:
                print(f"[Cloudinary Error] Lỗi upload lên Cloud: {e}")
            
            # Update local memory and DB with cloud URLs
            with self._lock:
                for a in self._recent_alerts:
                    if a["id"] == alert_id:
                        a["cloud_img_url"] = cloud_img_url
                        a["cloud_video_url"] = cloud_video_url
                        a["media"] = f"{alert_id}_video" if video_written else f"{alert_id}_image"
                        break
            try:
                from src.web.backend.db import get_db_client
                with get_db_client() as client:
                    media_val = f"{alert_id}_video" if video_written else f"{alert_id}_image"
                    client.execute(
                        "UPDATE alerts SET cloud_img_url = ?, cloud_video_url = ?, media = ? WHERE id = ?",
                        [cloud_img_url, cloud_video_url, media_val, alert_id]
                    )
            except Exception as e:
                print(f"[Database Error] Khong the cap nhat Cloud URL va media vao Turso: {e}")
            
            # 4. Trigger actual notifications
            try:
                from src.web.backend.notifications import send_all_alerts
                send_all_alerts(
                    alert_id=alert_id,
                    image_path=str(img_path),
                    video_path=str(video_path) if video_written else None,
                    cloud_img_url=cloud_img_url,
                    cloud_video_url=cloud_video_url
                )
            except Exception as e:
                print(f"[Notification Error] Khong gui duoc canh bao: {e}")


def _play_alert_sound() -> None:
    if winsound is None:
        return
    try:
        # Dual-tone siren beep sequence (6 tones, total duration ~ 1.5 seconds)
        for _ in range(3):
            winsound.Beep(988, 250)  # B5
            winsound.Beep(1318, 250) # E6
    except Exception:
        # Fallback to standard beep if speaker device error
        try:
            winsound.MessageBeep(winsound.MB_ICONHAND)
        except Exception:
            return


def _draw_status(frame, result, ai_prediction, state_colors, cv2) -> None:
    color = state_colors[result.state]
    label = (
        f"{result.state.value.upper()} | angle={result.torso_angle_deg:.1f} "
        f"| lie={result.lying_seconds:.1f}s | profile={result.profile}"
    )
    _draw_text(frame, label, (20, 40), color, cv2)
    if ai_prediction.enabled:
        ai_label = f"AI: {ai_prediction.label} ({ai_prediction.probability:.2f})"
        ai_color = (40, 40, 230) if ai_prediction.label == "fall" else (70, 200, 90)
        _draw_text(frame, ai_label, (20, 80), ai_color, cv2)
    else:
        _draw_text(frame, "AI: disabled/no model", (20, 80), (180, 180, 180), cv2)
    if result.state.value in {"fallen", "alert"}:
        height, width = frame.shape[:2]
        cv2.rectangle(frame, (0, 0), (width - 1, height - 1), color, 6)


def _draw_text(frame, text: str, origin: tuple[int, int], color: tuple[int, int, int], cv2) -> None:
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2, cv2.LINE_AA)
