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
    from src.face import FaceRecognizer, PersonType, RecognizedFace

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
        "FaceRecognizer": FaceRecognizer,
        "PersonType": PersonType,
        "RecognizedFace": RecognizedFace,
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
        self._last_stranger_alert_time: float = 0.0
        from collections import deque
        self._frame_buffer = deque(maxlen=200)




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
        FaceRecognizer = runtime["FaceRecognizer"]

        config = load_config(self.config_path)
        self._config = config
        self._detector = FallDetector(config.detector)
        self._feature_buffer = LandmarkFeatureBuffer(window_size=round(config.detector.assumed_fps))
        self._ai_classifier = FallAIClassifier(config.ai)
        self._estimator = PoseEstimator(model_complexity=config.app.model_complexity)
        self._logger = EventLogger(config.app.event_log_path)
        self._face_recognizer = FaceRecognizer(config.face)


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
        PersonType = runtime["PersonType"]
        state_colors = {
            FallState.NORMAL: (70, 200, 90),
            FallState.LYING: (180, 180, 180),
            FallState.WARNING: (0, 190, 255),
            FallState.POSSIBLE_FALL: (0, 140, 255),
            FallState.FALLEN: (40, 40, 230),
            FallState.ALERT: (0, 0, 255),
        }
        person_type_colors = {
            PersonType.FAMILY: (70, 200, 90),
            PersonType.ATTENTION: (0, 220, 255),
            PersonType.STRANGER: (40, 40, 230),
        }
        frames = 0
        started = time.perf_counter()
        cached_faces = []
        raw_faces = None
        last_face_nose = None

        while self._running and self._video and self._estimator and self._detector:
            frame_start = time.perf_counter()
            ok, frame = self._video.read()
            if not ok or frame is None:
                with self._lock:
                    self._status.last_error = "Khong doc duoc frame tu camera."
                time.sleep(0.05)
                continue

            frames += 1
            clean_frame = frame.copy()
            points, pose_results = self._estimator.estimate(frame)

            # Lấy vị trí mũi từ MediaPipe Pose để xác minh & tracking
            h_img, w_img = frame.shape[:2]
            nose_pos = None
            if points and "nose" in points and getattr(points["nose"], "visibility", 0) > 0.35:
                nose_pos = (int(points["nose"].x * w_img), int(points["nose"].y * h_img))

            # Xử lý nhận diện và tracking khuôn mặt linh hoạt
            if getattr(self, "_face_recognizer", None) and getattr(self, "_config", None):
                n_frames = max(1, getattr(self._config.face, "process_every_n_frames", 4))

                if frames % n_frames == 0 or raw_faces is None:
                    detected_faces = self._face_recognizer.recognize(frame)

                    # Lọc bỏ các bọc mặt giả xuất hiện trên áo/tường xa vị trí đầu thật
                    if nose_pos and detected_faces:
                        nx, ny = nose_pos
                        valid_faces = []
                        for f in detected_faces:
                            fx, fy, fw, fh = f.box
                            fc_x, fc_y = fx + fw // 2, fy + fh // 2
                            dist = ((fc_x - nx) ** 2 + (fc_y - ny) ** 2) ** 0.5
                            max_dist = max(200, int(max(fw, fh) * 2.0))
                            if dist <= max_dist:
                                valid_faces.append(f)
                        raw_faces = valid_faces
                    else:
                        raw_faces = detected_faces

                    last_face_nose = nose_pos
                    cached_faces = list(raw_faces)
                elif raw_faces and nose_pos and last_face_nose:
                    # Cập nhật vị trí khung mặt dịch chuyển thời gian thực theo đầu người
                    dx = nose_pos[0] - last_face_nose[0]
                    dy = nose_pos[1] - last_face_nose[1]
                    tracked_faces = []
                    for f in raw_faces:
                        fx, fy, fw, fh = f.box
                        new_box = (max(0, fx + dx), max(0, fy + dy), fw, fh)
                        tracked_faces.append(
                            runtime["RecognizedFace"](
                                name=f.name,
                                person_type=f.person_type,
                                box=new_box,
                                confidence=f.confidence
                            )
                        )
                    cached_faces = tracked_faces
                elif not raw_faces:
                    cached_faces = []

            current_person_name = cached_faces[0].name if cached_faces else "Unknown"
            current_person_type = cached_faces[0].person_type.value if cached_faces else "N/A"
            ai_prediction = None
            if points and self._feature_buffer and self._ai_classifier:
                features = self._feature_buffer.append(points)
                ai_prediction = self._ai_classifier.predict(features)
                result = self._detector.update(points)

                event_triggered = result.event_started and self._logger

                # KHÔNG vẽ khung xương lên live frame để màn hình camera sạch sẽ, rõ nét
                _draw_status(frame, result, ai_prediction, state_colors, cv2)
                _draw_faces(frame, cached_faces, person_type_colors, cv2)

                # Lưu frame live vào lịch sử buffer
                self._frame_buffer.append(frame.copy())

                # 1. Xử lý Cảnh báo người lạ -> Ảnh SẠCH (KHÔNG KHUNG XƯƠNG)
                now_ts = time.time()
                has_stranger = any(
                    (f.person_type.value if hasattr(f.person_type, "value") else str(f.person_type)) == "STRANGER"
                    for f in cached_faces
                )
                if has_stranger and (now_ts - self._last_stranger_alert_time > 20.0):
                    self._last_stranger_alert_time = now_ts
                    stranger_id = f"STRANGER-{int(now_ts)}"
                    print(f"[Stranger Alert] Phát hiện người lạ! Chụp ảnh sạch & gửi server: {stranger_id}")

                    # Gửi alert vao DB & Danh sach Web Dashboard
                    self._push_stranger_alert(stranger_id)

                    # Kêu chuông cảnh báo
                    threading.Thread(target=_play_alert_sound, daemon=True).start()

                    # Lưu ảnh SẠCH (KHÔNG KHUNG XƯƠNG) gửi lên server Cloudinary
                    snapshot = clean_frame.copy()
                    threading.Thread(
                        target=self._save_event_media,
                        args=(stranger_id, snapshot, []),
                        daemon=True,
                    ).start()

                # 2. Xử lý Cảnh báo Té ngã -> BẢO TOÀN KHUNG XƯƠNG làm bằng chứng
                if event_triggered:
                    alert_id = f"AL-{int(time.time())}"
                    self._logger.write(result, person_name=current_person_name, person_type=current_person_type)
                    self._push_alert(result, alert_id)

                    # Phát chuông cảnh báo
                    threading.Thread(target=_play_alert_sound, daemon=True).start()

                    # Tạo ảnh cảnh báo té ngã CÓ KHUNG XƯƠNG để làm bằng chứng chứng minh tư thế té ngã
                    fall_snapshot = clean_frame.copy()
                    if pose_results:
                        self._estimator.draw(fall_snapshot, pose_results)

                    video_frames = list(self._frame_buffer)
                    threading.Thread(
                        target=self._save_event_media,
                        args=(alert_id, fall_snapshot, video_frames),
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
                _draw_status(frame, None, ai_prediction, state_colors, cv2, pose_detected=False)
                
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
            from src.web.shared.db import get_db_client
            with get_db_client() as client:
                client.execute(
                    "INSERT INTO alerts (id, time, camera, person, confidence, status, level, media, state, cloud_img_url, cloud_video_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [alert_id, alert["time"], alert["camera"], alert["person"], alert["confidence"], alert["status"], alert["level"], alert["media"], alert["state"], None, None]
                )
        except Exception as e:
            print(f"[Database Error] Khong the luu alert vao Turso: {e}")

    def _push_stranger_alert(self, alert_id: str) -> None:
        from datetime import datetime

        alert = {
            "id": alert_id,
            "time": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "camera": getattr(self, "camera_id", "CAM-LOCAL"),
            "person": "Người lạ xuất hiện",
            "confidence": 95,
            "status": "Chưa xử lý",
            "level": "Cảnh báo",
            "media": alert_id,
            "state": "STRANGER_DETECTED",
            "cloud_img_url": None,
            "cloud_video_url": None,
        }
        self._recent_alerts.insert(0, alert)
        self._recent_alerts = self._recent_alerts[:50]

        try:
            from src.web.shared.db import get_db_client
            with get_db_client() as client:
                client.execute(
                    "INSERT INTO alerts (id, time, camera, person, confidence, status, level, media, state, cloud_img_url, cloud_video_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [alert_id, alert["time"], alert["camera"], alert["person"], alert["confidence"], alert["status"], alert["level"], alert["media"], alert["state"], None, None]
                )
        except Exception as e:
            print(f"[Database Error] Khong the luu stranger alert vao Turso: {e}")


    def _save_event_media(self, alert_id: str, snapshot_frame, video_frames: list) -> None:
        import os
        import time
        from pathlib import Path
        
        project_root = Path(__file__).resolve().parents[3]
        media_dir = project_root / "data" / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        
        img_path = media_dir / f"{alert_id}.jpg"
        video_path = media_dir / f"{alert_id}.mp4"
        video_written = False
        cloud_img_url = None
        cloud_video_url = None

        # Đợi 2.5 giây sau sự kiện để ghi trọn vẹn diễn biến té ngã
        time.sleep(2.5)
        try:
            with self._lock:
                if self._frame_buffer:
                    video_frames = list(self._frame_buffer)
        except Exception:
            pass

        try:
            # 1. Save snapshot image
            cv2 = self._runtime.get("cv2") if self._runtime else None
            if cv2 is None:
                import cv2

            if cv2 is not None:
                cv2.imwrite(str(img_path), snapshot_frame)

                # 2. Save video clip với FPS khớp thực tế (Tạo đoạn video dài 5-10 giây)
                if video_frames and len(video_frames) >= 10:
                    height, width = video_frames[0].shape[:2]
                    write_fps = max(8.0, min(15.0, self._status.fps or 12.0))

                    # Thử ghi video với các codec tương thích
                    for codec in ["mp4v", "XVID", "MJPG", "avc1", "H264"]:
                        try:
                            fourcc = cv2.VideoWriter_fourcc(*codec)
                            writer = cv2.VideoWriter(str(video_path), fourcc, write_fps, (width, height))
                            if writer.isOpened():
                                for f in video_frames:
                                    writer.write(f)
                                writer.release()
                                # Kiểm tra file video ghi thành công (>1KB)
                                if video_path.exists() and video_path.stat().st_size > 1000:
                                    video_written = True
                                    print(f"[Media] Recorded video clip ({len(video_frames)} frames @ {write_fps:.1f}fps): {video_path}")
                                    break
                                else:
                                    if video_path.exists():
                                        video_path.unlink()
                        except Exception as codec_err:
                            print(f"[Media Warning] Codec {codec} failed: {codec_err}")
                            if video_path.exists():
                                try:
                                    video_path.unlink()
                                except Exception:
                                    pass
                            continue

                
                # 3. Upload to Cloudinary if configured in db.json
                try:
                    from src.web.shared.cloudinary_uploader import upload_to_cloudinary
                    if img_path.exists():
                        cloud_img_url = upload_to_cloudinary(str(img_path))
                    if video_written and video_path.exists():
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
                    from src.web.shared.db import get_db_client
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
                    from src.web.shared.notifications import send_all_alerts
                    send_all_alerts(
                        alert_id=alert_id,
                        image_path=str(img_path) if img_path.exists() else None,
                        video_path=str(video_path) if (video_written and video_path.exists()) else None,
                        cloud_img_url=cloud_img_url,
                        cloud_video_url=cloud_video_url
                    )
                except Exception as e:
                    print(f"[Notification Error] Khong gui duoc canh bao: {e}")
        finally:
            # Only delete local files if Cloudinary upload succeeded to retain fallback media locally
            try:
                if cloud_img_url and img_path.exists():
                    img_path.unlink()
                if cloud_video_url and video_path.exists():
                    video_path.unlink()
            except Exception as cleanup_err:
                print(f"[Media Cleanup Error] Không thể xóa file tạm: {cleanup_err}")


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


def _draw_status(frame, result, ai_prediction, state_colors, cv2, pose_detected: bool = True) -> None:
    h, w = frame.shape[:2]
    
    if pose_detected and result:
        color = state_colors.get(result.state, (70, 200, 90))
        state_str = result.state.value.upper()
        status_text = f"{state_str} | Angle: {result.torso_angle_deg:.1f}deg | Lie: {result.lying_seconds:.1f}s"
    else:
        color = (140, 145, 150)
        status_text = "SEARCHING POSE... | Camera Active"

    if ai_prediction and ai_prediction.enabled:
        ai_text = f"AI: {ai_prediction.label} ({ai_prediction.probability:.2f})"
        ai_color = (40, 40, 230) if ai_prediction.label == "fall" else (70, 200, 90)
    else:
        ai_text = "AI: Disabled"
        ai_color = (170, 175, 180)

    font_scale = max(0.35, min(0.45, h / 950.0))
    font = cv2.FONT_HERSHEY_SIMPLEX

    # Draw semi-transparent background badge with comfortable safe margins (margin_x >= 30, margin_y >= 18)
    margin_x = int(max(30, w * 0.05))
    margin_y = int(max(18, h * 0.04))

    badge_h = int(max(36, 42 * (h / 480.0)))
    badge_w = int(min(w * 0.58, 330 * (w / 640.0)))
    
    overlay = frame.copy()
    cv2.rectangle(overlay, (margin_x, margin_y), (margin_x + badge_w, margin_y + badge_h), (18, 20, 26), -1)
    cv2.rectangle(overlay, (margin_x, margin_y), (margin_x + 5, margin_y + badge_h), color, -1)
    
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    text_y1 = margin_y + int(badge_h * 0.44)
    text_y2 = margin_y + int(badge_h * 0.84)

    cv2.putText(frame, status_text, (margin_x + 12, text_y1), font, font_scale, (245, 245, 245), 1, cv2.LINE_AA)
    cv2.putText(frame, ai_text, (margin_x + 12, text_y2), font, font_scale * 0.9, ai_color, 1, cv2.LINE_AA)

    if pose_detected and result and result.state.value in {"fallen", "alert"}:
        cv2.rectangle(frame, (0, 0), (w - 1, h - 1), color, 4)


def _draw_text(frame, text: str, origin: tuple[int, int], color: tuple[int, int, int], cv2) -> None:
    h = frame.shape[0]
    font_scale = max(0.40, min(0.52, h / 850.0))
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, 1, cv2.LINE_AA)


def _draw_faces(frame, faces, person_type_colors, cv2) -> None:
    has_stranger = False
    for face in faces:
        x, y, w, h = face.box
        color = person_type_colors.get(face.person_type, (200, 200, 200))

        # Khung viền mỏng đẹp
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

        # Định dạng nhãn sạch gọn, không lặp từ
        ptype_str = face.person_type.value if hasattr(face.person_type, "value") else str(face.person_type)
        if ptype_str == "STRANGER":
            label = "NGUOI LA"
            has_stranger = True
        elif ptype_str == "ATTENTION":
            label = f"{face.name} [VIP]"
        else:
            label = f"{face.name}"

        # Vẽ thẻ nền phía trên bounding box
        (text_w, text_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        label_bg_y1 = max(0, y - text_h - 8)
        label_bg_y2 = max(text_h + 8, y)
        cv2.rectangle(frame, (x, label_bg_y1), (x + text_w + 10, label_bg_y2), color, cv2.FILLED)

        # Màu chữ tương phản
        text_color = (0, 0, 0) if ptype_str in ("FAMILY", "ATTENTION") else (255, 255, 255)
        cv2.putText(frame, label, (x + 5, label_bg_y2 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, text_color, 1, cv2.LINE_AA)

    if has_stranger:
        h_img, w_img = frame.shape[:2]
        # Báo động ở góc trên bên phải (tránh đè lên Status Badge ở góc trái)
        badge_w = 230
        cv2.rectangle(frame, (w_img - badge_w - 20, 18), (w_img - 20, 52), (40, 40, 230), cv2.FILLED)
        cv2.putText(frame, "! CANH BAO: NGUOI LA !", (w_img - badge_w - 10, 41), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)


pipeline = FallDetectionPipeline()



