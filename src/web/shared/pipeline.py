"""
File: src/web/shared/pipeline.py
Chức năng chính: Quản lý luồng chạy ngầm (Background Thread) cho Camera và thuật toán AI.
Thay vì chạy trực tiếp trên giao diện như src/core/app.py, file này cho phép chạy AI
ngầm trên Server, đồng thời liên tục trích xuất từng khung hình (frame) thành dạng ảnh JPEG
để phát trực tiếp (livestream) lên giao diện Web/App thông qua API MJPEG.

File liên kết:
- Gọi tới: src.core.app (sử dụng lại logic vẽ hình, phát hiện té ngã)
- Gọi bởi: src.web.shared.router.py (khi có lệnh Start/Stop Camera từ App)
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

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
    from src.detection.object_detector import DetectedObject, ObjectDetector
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
        "ObjectDetector": ObjectDetector,
        "DetectedObject": DetectedObject,
        "PoseEstimator": PoseEstimator,
        "FaceRecognizer": FaceRecognizer,
        "PersonType": PersonType,
        "RecognizedFace": RecognizedFace,
    }


def filter_anatomical_faces(
    faces: list[Any],
    points: Mapping[str, Any] | None,
    frame_height: int,
) -> list[Any]:
    """
    Bộ lọc Giải phẫu Khuôn mặt (Anatomical Face Position Filter):
    Loại bỏ các khuôn mặt ảo do phát hiện nhầm trên bàn tay gõ phím, bàn phím máy tính hoặc đùi.
    Về mặt giải phẫu sinh học, tâm khuôn mặt người không thể nằm sâu dưới đường vai.
    Nếu face_center_y > sh_y + 0.12, loại bỏ box ảo này.
    """
    if not faces or frame_height <= 0:
        return faces

    if not points:
        # Khi không phát hiện được dáng người (ví dụ chỉ có cẳng tay, nắm đấm hoặc bức tường),
        # loại bỏ các box khuôn mặt quá nhỏ (< 36px) hoặc độ tin cậy thấp (< 0.60) trên nếp nhăn/da tay
        valid_faces = []
        for f in faces:
            box = getattr(f, "box", None)
            if not box or len(box) < 4:
                continue
            fw = box[2] if box[2] > 1.0 else box[2] * frame_height
            fh = box[3] if box[3] > 1.0 else box[3] * frame_height
            conf = float(getattr(f, "confidence", 0.0))
            if min(fw, fh) < 36 or conf < 0.60:
                continue
            valid_faces.append(f)
        return valid_faces

    l_sh = points.get("left_shoulder")
    r_sh = points.get("right_shoulder")
    sh_candidates = [
        getattr(p, "y", p.get("y") if isinstance(p, dict) else None)
        for p in (l_sh, r_sh)
        if p is not None and getattr(p, "visibility", p.get("visibility", 1.0) if isinstance(p, dict) else 1.0) > 0.20
    ]
    sh_candidates = [y for y in sh_candidates if y is not None]
    if not sh_candidates:
        return faces

    sh_y = min(sh_candidates)
    valid_faces = []
    for f in faces:
        box = getattr(f, "box", None)
        if not box or not isinstance(box, (list, tuple)) or len(box) < 4:
            valid_faces.append(f)
            continue
        fx, fy, fw, fh = box
        if fy <= 1.0 and fh <= 1.0 and (fy + fh) <= 1.0:
            face_center_y = float(fy + fh / 2.0)
        else:
            face_center_y = (fy + fh / 2.0) / float(frame_height)
        if face_center_y > sh_y + 0.12:
            # Face center is > 12% below shoulder line -> reject as anatomical artifact
            continue
        valid_faces.append(f)
    return valid_faces


@dataclass
class PipelineStatus:
    """Class lưu trữ trạng thái hiện tại của luồng Camera (Đang chạy, Góc nghiêng, Lỗi...)."""
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
    detected_objects: list[str] = field(default_factory=list)
    safe_resting: bool = False
    resting_object: str = ""
    pre_fall: bool = False
    pre_fall_type: str = ""
    postural_sway: float = 0.0
    is_seated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FallDetectionPipeline:
    """
    Class khởi tạo và quản lý Luồng Camera ngầm.
    Chịu trách nhiệm:
    - Bật camera, chạy AI nhận diện y hệt như app.py.
    - Mã hóa (encode) từng khung hình thành chuỗi byte JPEG.
    - Cung cấp hình ảnh cho API (để truyền lên Web/App).
    - Lưu lại đoạn video (15-30 frame) khi có người té ngã.
    """

    def __init__(self, config_path: str = "configs/default.yaml") -> None:
        self.config_path = config_path
        self._lock = threading.Lock()
        self._lifecycle_lock = threading.RLock()
        self._overlay_lock = threading.Lock()
        self._new_jpeg_event = threading.Event()
        self._frame_cond = threading.Condition(self._lock)
        self._frame_id = 0
        self._latest_jpeg: bytes | None = None
        self._status = PipelineStatus()
        self._thread: threading.Thread | None = None
        self._stream_thread: threading.Thread | None = None
        self._ai_thread: threading.Thread | None = None
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
        self._stranger_consecutive_frames: int = 0
        self._stranger_active_session: bool = False
        self._last_stranger_seen_time: float = 0.0
        self._frame_buffer = deque(maxlen=200)

        # Decoupled AI pipeline state
        self._latest_ai_frame: Any = None
        self._ai_trigger_event = threading.Event()
        self._cached_pose_results: Any = None
        self._cached_pose_ts: float = 0.0
        self._cached_points: dict | None = None
        self._cached_faces: list = []
        self._cached_faces_ts: float = 0.0
        self._cached_fall_result: Any = None
        self._cached_ai_prediction: Any = None
        self._cached_track_box: tuple | None = None
        self._cached_objects: list = []
        self._object_detector: Any | None = None

    def _buffer_frame(self, frame, cv2) -> None:
        """Lưu frame vào buffer để ghi clip khi té ngã. Tối ưu kích thước để không tràn RAM."""
        try:
            h, w = frame.shape[:2]
            if w > 640 or h > 360:
                buf_frame = cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA)
            else:
                buf_frame = frame.copy()
            self._frame_buffer.append(buf_frame)
        except Exception:
            self._frame_buffer.append(frame.copy())

    @property
    def status(self) -> PipelineStatus:
        with self._lock:
            return PipelineStatus(**self._status.to_dict())

    def recent_alerts(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._recent_alerts)

    def get_jpeg_frame(self, wait_new: bool = False, timeout: float = 0.04) -> bytes | None:
        if wait_new:
            self._new_jpeg_event.wait(timeout=timeout)
            self._new_jpeg_event.clear()
        with self._lock:
            return self._latest_jpeg

    def get_next_jpeg_frame(self, last_frame_id: int = -1, timeout: float = 0.04) -> tuple[int, bytes | None]:
        with self._frame_cond:
            if self._frame_id == last_frame_id or self._latest_jpeg is None:
                self._frame_cond.wait(timeout=timeout)
            return self._frame_id, self._latest_jpeg

    def is_running(self) -> bool:
        with self._lock:
            stream_alive = bool(self._stream_thread and self._stream_thread.is_alive())
            return bool(self._running and stream_alive)

    def start(self, source: str | int = "0", camera_id: str | None = None) -> None:
        target_cam = camera_id or "CAM-LOCAL"
        target_source = str(source)
        with self._lifecycle_lock:
            with self._lock:
                if self._running and str(self._status.source) == target_source and self._stream_thread and self._stream_thread.is_alive():
                    self.camera_id = target_cam
                    return

            self.stop()
            self.camera_id = target_cam
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
            ObjectDetector = runtime["ObjectDetector"]
            self._object_detector = ObjectDetector(getattr(config, "object_detection", None))
            self._cached_objects = []

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

            # Khởi chạy luồng AI inference ngầm (chạy song song, không nghẽn luồng video)
            self._ai_thread = threading.Thread(target=self._ai_worker_loop, daemon=True)
            self._ai_thread.start()

            # Khởi chạy luồng render stream (chạy ở tốc độ gốc 25-30 FPS của camera, mượt mà 0ms delay)
            self._stream_thread = threading.Thread(target=self._stream_loop, daemon=True)
            self._stream_thread.start()
            self._thread = self._stream_thread

    def stop(self) -> None:
        """Tắt Camera và dừng các luồng AI/Stream."""
        with self._lifecycle_lock:
            self._running = False
            self._ai_trigger_event.set()
            with self._frame_cond:
                self._frame_cond.notify_all()
            self._new_jpeg_event.set()

            if self._stream_thread and self._stream_thread.is_alive() and threading.current_thread() != self._stream_thread:
                self._stream_thread.join(timeout=2.0)
            self._stream_thread = None

            if self._ai_thread and self._ai_thread.is_alive() and threading.current_thread() != self._ai_thread:
                self._ai_thread.join(timeout=2.0)
            self._ai_thread = None
            self._thread = None

            if self._estimator:
                try:
                    self._estimator.close()
                except Exception:
                    pass
                self._estimator = None
            if self._video:
                try:
                    self._video.release()
                except Exception:
                    pass
                self._video = None
            self._detector = None
            self._feature_buffer = None
            self._ai_classifier = None
            self._runtime = None
            with self._overlay_lock:
                self._latest_ai_frame = None
                self._cached_pose_results = None
                self._cached_pose_ts = 0.0
                self._cached_points = None
                self._cached_faces = []
                self._cached_faces_ts = 0.0
                self._cached_fall_result = None
                self._cached_ai_prediction = None
                self._cached_track_box = None
                self._cached_objects = []
            with self._lock:
                self._status = PipelineStatus()
                self._latest_jpeg = None

    def _loop(self) -> None:
        """Alias tương thích ngược."""
        self._stream_loop()

    def _stream_loop(self) -> None:
        runtime = self._runtime
        if not runtime:
            return
        cv2 = runtime["cv2"]
        FallState = runtime["FallState"]
        PersonType = runtime["PersonType"]
        state_colors = {
            FallState.NORMAL: (70, 200, 90),
            FallState.PRE_FALL: (0, 165, 255),
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
        fps_counter = 0
        fps_last_time = time.perf_counter()
        current_fps = 0.0

        encode_params = [
            int(cv2.IMWRITE_JPEG_QUALITY), 68,
            int(cv2.IMWRITE_JPEG_OPTIMIZE), 0,
        ]

        while self._running and self._video:
            try:
                frame_start = time.perf_counter()
                ok, frame = self._video.read(timeout=0.04)
                if not ok or frame is None:
                    with self._lock:
                        self._status.last_error = "Dang ket noi camera..."
                    time.sleep(0.01)
                    continue

                # Chuẩn hóa kích thước khung hình stream: Giảm tải CPU khi camera Full HD/2K
                h_orig, w_orig = frame.shape[:2]
                if w_orig > 800:
                    scale = 800.0 / w_orig
                    frame = cv2.resize(frame, (800, int(h_orig * scale)), interpolation=cv2.INTER_LINEAR)

                # Gửi bản frame sạch cho AI worker xử lý ngầm (không chờ AI, không delay stream)
                with self._overlay_lock:
                    self._latest_ai_frame = frame
                self._ai_trigger_event.set()

                # Sao chép frame để vẽ overlay (frame gốc được giữ sạch cho AI)
                display_frame = frame.copy()

                # Lấy kết quả AI mới nhất từ bộ nhớ đệm
                now_overlay = time.time()
                with self._overlay_lock:
                    # TTL: Chỉ vẽ khuôn mặt nếu kết quả nhận diện mới cập nhật trong vòng 0.40s
                    # Tránh tuyệt đối hiện tượng khung mặt bị đông cứng/đứng hình khi người di chuyển
                    if (now_overlay - self._cached_faces_ts) <= 0.40:
                        cached_faces = list(self._cached_faces)
                    else:
                        cached_faces = []
                    # TTL: Chỉ vẽ khung xương nếu kết quả mới cập nhật trong vòng 0.45s
                    # Tránh hiện tượng khung xương cũ bị giật, lag hoặc trôi nổi khi người di chuyển
                    if (now_overlay - getattr(self, "_cached_pose_ts", 0.0)) <= 0.45:
                        cached_pose = self._cached_pose_results
                    else:
                        cached_pose = None
                    cached_result = self._cached_fall_result
                    cached_ai = self._cached_ai_prediction
                    cached_track = self._cached_track_box
                    cached_objects = list(self._cached_objects)
                    pose_detected = (self._cached_points is not None)

                # 1. Vẽ nhận diện khuôn mặt (chỉ 1 khung vuông tại khuôn mặt từng người)
                if cached_faces:
                    show_stranger_badge = bool(self._stranger_active_session or self._stranger_consecutive_frames >= 12)
                    _draw_faces(display_frame, cached_faces, person_type_colors, cv2, show_stranger_alert=show_stranger_badge)

                # 2. Vẽ skeleton khung xương
                if cached_pose and self._estimator:
                    self._estimator.draw(display_frame, cached_pose)

                # 3. Vẽ trạng thái Fall Detection HUD
                _draw_status(display_frame, cached_result, cached_ai, state_colors, cv2, pose_detected=pose_detected)

                # 3.5. Hiển thị thông báo Nằm nghỉ an toàn nếu người ở trên giường/sofa hoặc ngồi làm việc
                if cached_result and getattr(cached_result, "safe_resting", False):
                    obj_name = getattr(cached_result, "resting_object", "giuong").upper()
                    cv2.rectangle(display_frame, (10, 10), (330, 42), (180, 130, 30), -1)
                    cv2.putText(display_frame, f"NGHI NGOI AN TOAN ({obj_name})", (18, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
                elif cached_result and getattr(cached_result, "is_seated", False):
                    obj_name = getattr(cached_result, "resting_object", "").upper()
                    seat_lbl = f"NGOI AN TOAN ({obj_name})" if obj_name and obj_name != "DESK_OCCLUSION" else "NGOI LAM VIEC (BAN)"
                    cv2.rectangle(display_frame, (10, 10), (330, 42), (50, 150, 70), -1)
                    cv2.putText(display_frame, seat_lbl, (18, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

                # 5. Lưu vào buffer ghi clip té ngã
                self._buffer_frame(display_frame, cv2)

                # 6. Tính FPS thực tế
                frames += 1
                fps_counter += 1
                now_perf = time.perf_counter()
                if now_perf - fps_last_time >= 0.8:
                    current_fps = round(fps_counter / (now_perf - fps_last_time), 1)
                    fps_counter = 0
                    fps_last_time = now_perf

                # 7. Encode JPEG siêu tốc và thông báo cho các client
                ok_enc, jpeg = cv2.imencode(".jpg", display_frame, encode_params)
                if ok_enc:
                    jpeg_bytes = jpeg.tobytes()
                    with self._frame_cond:
                        self._latest_jpeg = jpeg_bytes
                        self._frame_id += 1
                        self._status.fps = current_fps or round(frames / max(now_perf - started, 0.001), 1)
                        self._status.latency_ms = round((now_perf - frame_start) * 1000, 1)
                        self._status.running = True
                        self._status.last_error = ""
                        self._frame_cond.notify_all()
                    self._new_jpeg_event.set()

            except Exception as stream_err:
                with self._lock:
                    self._status.last_error = f"Lỗi Stream: {str(stream_err)[:40]}"
                time.sleep(0.01)

    def _process_face_recognition(self, clean_frame: Any) -> list[Any]:
        """Xử lý nhận diện khuôn mặt người quen / người lạ thời gian thực."""
        if hasattr(self, "_face_recognizer") and self._face_recognizer is not None:
            try:
                return self._face_recognizer.recognize(clean_frame)
            except Exception as face_err:
                print(f"[Face Recognizer Error] {face_err}")
        return []

    def _process_pose_estimation(self, clean_frame: Any, current_faces: list[Any]) -> tuple[dict[str, Any] | None, Any]:
        """Xử lý ước tính khung xương dáng người (hỗ trợ đơn/đa người)."""
        points = None
        pose_results = None
        try:
            if current_faces and hasattr(self._estimator, "estimate_multi"):
                multi_poses = self._estimator.estimate_multi(clean_frame, current_faces)
                if multi_poses:
                    pose_results = [res for _, res in multi_poses]
                    points = multi_poses[0][0]
                    for p_pts, _ in multi_poses:
                        sh = p_pts.get("left_shoulder") or p_pts.get("right_shoulder")
                        if sh and sh.y > 0.50:
                            points = p_pts
                            break
            elif self._estimator:
                points, pose_results = self._estimator.estimate(clean_frame)
        except Exception as pose_err:
            print(f"[Pose Estimator Error] {pose_err}")
        return points, pose_results

    def _check_stranger_alert(self, current_faces: list[Any], clean_frame: Any, now_ts: float) -> None:
        """Kiểm tra và kích hoạt cảnh báo khi phát hiện người lạ duy trì liên tục."""
        stranger_faces = []
        for f in current_faces:
            ptype = f.person_type.value if hasattr(f.person_type, "value") else str(f.person_type)
            if ptype == "STRANGER":
                if (
                    hasattr(self, "_face_recognizer")
                    and self._face_recognizer is not None
                    and hasattr(self._face_recognizer, "is_near_recent_known_face")
                    and self._face_recognizer.is_near_recent_known_face(f.box, max_seconds=4.0)
                ):
                    continue
                stranger_faces.append(f)

        has_stranger = len(stranger_faces) > 0
        if has_stranger:
            self._last_stranger_seen_time = now_ts
            self._stranger_consecutive_frames += 1
        else:
            self._stranger_consecutive_frames = max(0, self._stranger_consecutive_frames - 1)
            if self._stranger_active_session and (now_ts - self._last_stranger_seen_time > 15.0):
                self._stranger_active_session = False
                print("[Stranger Session] Người lạ đã rời đi khỏi khu vực giám sát.")

        if (has_stranger and (self._stranger_consecutive_frames >= 16)
                and not self._stranger_active_session
                and (now_ts - self._last_stranger_alert_time > 20.0)):
            best_face_conf = max((getattr(f, "confidence", 0.85) for f in stranger_faces), default=0.85)
            if best_face_conf >= 0.60:
                self._last_stranger_alert_time = now_ts
                self._stranger_active_session = True
                self._stranger_consecutive_frames = 0
                stranger_id = f"STRANGER-{int(now_ts)}"
                conf_pct = min(99, max(60, int(round(best_face_conf * 100))))
                print(f"[Stranger Alert] 🚨 Phát hiện người lạ mới! Độ tin cậy AI: {conf_pct}% - {stranger_id}")

                self._push_stranger_alert(stranger_id, confidence=conf_pct)
                threading.Thread(target=_play_alert_sound, daemon=True).start()

                snapshot = clean_frame.copy()
                threading.Thread(
                    target=self._save_event_media,
                    args=(stranger_id, snapshot, []),
                    daemon=True,
                ).start()

    def _ai_worker_loop(self) -> None:
        runtime = self._runtime
        if not runtime:
            return
        cv2 = runtime["cv2"]
        ai_frame_count = 0

        while self._running and self._estimator and self._detector:
            try:
                if not self._ai_trigger_event.wait(timeout=0.05):
                    continue
                self._ai_trigger_event.clear()

                with self._overlay_lock:
                    if self._latest_ai_frame is None:
                        continue
                    clean_frame = self._latest_ai_frame
                    self._latest_ai_frame = None

                ai_frame_count += 1

                # 1. Face recognition (Chạy liên tục mỗi chu kỳ AI để bám sát khuôn mặt theo thời gian thực)
                current_faces = self._process_face_recognition(clean_frame)

                # 2. Pose estimation (MediaPipe Lite - hỗ trợ Multi-Person Pose khi có nhiều người)
                points, pose_results = self._process_pose_estimation(clean_frame, current_faces)

                # Bộ lọc Giải phẫu Khuôn mặt: loại bỏ box ảo trên bàn phím / bàn tay nằm sâu dưới vai
                if points and current_faces:
                    current_faces = filter_anatomical_faces(current_faces, points, clean_frame.shape[0])

                current_person_name = current_faces[0].name if current_faces else "Unknown"
                current_person_type = current_faces[0].person_type.value if current_faces else "N/A"

                # 3. Xử lý cảnh báo người lạ
                now_ts = time.time()
                self._check_stranger_alert(current_faces, clean_frame, now_ts)

                # 3.5. Nhận diện vật phẩm & nội thất (YOLOv8-nano Object Detection)
                # Chỉ chạy khi người dùng bật trong config, mặc định tắt để dồn 100% CPU cho con người
                current_objects = []
                obj_cfg = getattr(getattr(self, "_config", None), "object_detection", None)
                if (
                    obj_cfg
                    and getattr(obj_cfg, "enabled", False)
                    and hasattr(self, "_object_detector")
                    and self._object_detector is not None
                    and self._object_detector.is_ready()
                ):
                    n_obj_frames = getattr(obj_cfg, "process_every_n_frames", 4)
                    if ai_frame_count % max(1, n_obj_frames) == 0 or (points and self._cached_points is None):
                        try:
                            current_objects = self._object_detector.detect(clean_frame)
                        except Exception as obj_err:
                            print(f"[Object Detector Error] {obj_err}")

                # 4. Phân tích tư thế Té ngã
                ai_prediction = None
                result = None
                track_box = None
                h_f, w_f = clean_frame.shape[:2]

                if points and self._feature_buffer and self._ai_classifier:
                    features = self._feature_buffer.append(points)
                    ai_prediction = self._ai_classifier.predict(features)
                    result = self._detector.update(points, nearby_objects=current_objects)

                    event_triggered = result.event_started and self._logger
                    if event_triggered:
                        alert_id = f"AL-{int(time.time())}"
                        print(f"[Fall Alert] 🚨 PHÁT HIỆN TÉ NGÃ: {alert_id} | Người: {current_person_name} | Góc thân: {result.torso_angle_deg:.1f}° | Trạng thái: {result.state.value}")
                        self._logger.write(result, person_name=current_person_name, person_type=current_person_type)
                        self._push_alert(result, alert_id, person_name=current_person_name)

                        threading.Thread(target=_play_alert_sound, daemon=True).start()

                        fall_snapshot = clean_frame.copy()
                        if pose_results:
                            self._estimator.draw(fall_snapshot, pose_results)

                        video_frames = list(self._frame_buffer)
                        threading.Thread(
                            target=self._save_event_media,
                            args=(alert_id, fall_snapshot, video_frames),
                            daemon=True
                        ).start()

                    if result.state.value in {"pre_fall", "warning", "possible_fall", "fallen", "alert"}:
                        xs = [p.x * w_f for p in points.values() if getattr(p, "visibility", 0) > 0.20]
                        ys = [p.y * h_f for p in points.values() if getattr(p, "visibility", 0) > 0.20]
                        if xs and ys:
                            track_box = (max(0, int(min(xs) - 15)), max(0, int(min(ys) - 15)), min(w_f, int(max(xs) + 15)), min(h_f, int(max(ys) + 15)))

                    with self._lock:
                        self._status.state = result.state.value
                        self._status.torso_angle_deg = result.torso_angle_deg
                        self._status.lying_seconds = result.lying_seconds
                        self._status.hip_velocity = result.hip_velocity
                        self._status.angle_velocity_deg = result.angle_velocity_deg
                        self._status.profile = result.profile
                        self._status.ai_label = ai_prediction.label if ai_prediction else "disabled"
                        self._status.ai_probability = ai_prediction.probability if ai_prediction else 0.0
                        self._status.ai_enabled = bool(ai_prediction and ai_prediction.enabled)
                        self._status.pose_detected = True
                        self._status.detected_objects = [f"{o.display_name} ({int(o.confidence * 100)}%)" for o in current_objects]
                        self._status.safe_resting = getattr(result, "safe_resting", False)
                        self._status.resting_object = getattr(result, "resting_object", "")
                        self._status.pre_fall = getattr(result, "pre_fall", False)
                        self._status.pre_fall_type = getattr(result, "pre_fall_type", "")
                        self._status.postural_sway = getattr(result, "postural_sway", 0.0)
                        self._status.is_seated = getattr(result, "is_seated", False)
                else:
                    if self._feature_buffer:
                        self._feature_buffer.reset()
                    with self._lock:
                        self._status.state = "normal"
                        self._status.pose_detected = False
                        self._status.detected_objects = [f"{o.display_name} ({int(o.confidence * 100)}%)" for o in current_objects]
                        self._status.safe_resting = False
                        self._status.resting_object = ""
                        self._status.pre_fall = False
                        self._status.pre_fall_type = ""
                        self._status.postural_sway = 0.0
                        self._status.is_seated = False

                # 5. Cập nhật cache overlay để Stream Loop lấy vẽ
                with self._overlay_lock:
                    self._cached_pose_results = pose_results
                    self._cached_pose_ts = time.time()
                    self._cached_points = points
                    self._cached_faces = current_faces
                    self._cached_faces_ts = time.time()
                    self._cached_fall_result = result
                    self._cached_ai_prediction = ai_prediction
                    self._cached_track_box = track_box
                    self._cached_objects = current_objects

            except Exception as ai_err:
                with self._lock:
                    self._status.last_error = f"Lỗi AI Worker: {str(ai_err)[:40]}"
                time.sleep(0.02)

    def _push_alert(self, result, alert_id: str, person_name: str | None = None) -> None:
        FallState = self._runtime["FallState"] if self._runtime else None
        level = "Cao"
        if FallState and result.state == FallState.ALERT:
            level = "Khẩn cấp"
        display_person = person_name if (person_name and person_name != "Unknown") else "Phát hiện từ AI"
        alert = {
            "id": alert_id,
            "time": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "camera": getattr(self, "camera_id", "CAM-LOCAL"),
            "person": display_person,
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

    def _push_stranger_alert(self, alert_id: str, confidence: int = 90) -> None:
        from datetime import datetime

        alert = {
            "id": alert_id,
            "time": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "camera": getattr(self, "camera_id", "CAM-LOCAL"),
            "person": "Người lạ xuất hiện",
            "confidence": confidence,
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
                        cloud_video_url=cloud_video_url,
                        alert_type="stranger" if alert_id.startswith("STRANGER-") else "fall"
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
        if result.state.value == "pre_fall":
            color = state_colors.get(result.state, (0, 165, 255))
            ptype = getattr(result, "pre_fall_type", "swaying").upper()
            sway_pct = int(getattr(result, "postural_sway", 0.0) * 100)
            if ptype == "SWAYING":
                type_str = "LAO DAO"
            elif ptype == "STUMBLE":
                type_str = "BUOC HUT / VAP"
            elif ptype == "DIZZY":
                type_str = "CHONG MAT"
            else:
                type_str = "MAT THANG BANG"
            status_text = f"TIEN TE NGA: {type_str} ({sway_pct}%) | {result.torso_angle_deg:.1f}deg"
        else:
            state_str = result.state.value.upper()
            if getattr(result, "is_seated", False):
                state_str = "NORMAL (SEATED)"
            status_text = f"{state_str} | Angle: {result.torso_angle_deg:.1f}deg | Lie: {result.lying_seconds:.1f}s"
    else:
        color = (140, 145, 150)
        status_text = "SEARCHING POSE... | Camera Active"

    if ai_prediction and ai_prediction.enabled:
        ai_text = f"Fall AI: {ai_prediction.label.upper()} ({ai_prediction.probability:.2f}) | Face: YuNet"
        ai_color = (40, 40, 230) if ai_prediction.label == "fall" else (70, 200, 90)
    else:
        ai_text = "Fall AI: MediaPipe Active | Face: YuNet"
        ai_color = (70, 200, 90)

    font_scale = max(0.35, min(0.45, h / 950.0))
    font = cv2.FONT_HERSHEY_SIMPLEX

    # Draw semi-transparent background badge with comfortable safe margins (margin_x >= 30, margin_y >= 18)
    margin_x = int(max(30, w * 0.05))
    margin_y = int(max(18, h * 0.04))

    badge_h = int(max(36, 42 * (h / 480.0)))
    badge_w = int(min(w * 0.65, 360 * (w / 640.0)))
    
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


def _compute_box_overlap_ratio(box1: tuple[int, int, int, int], box2: tuple[int, int, int, int]) -> float:
    """Tính tỷ lệ giao nhau giữa 2 box (x1, y1, x2, y2) trên diện tích box nhỏ hơn (Containment)."""
    ix1 = max(box1[0], box2[0])
    iy1 = max(box1[1], box2[1])
    ix2 = min(box1[2], box2[2])
    iy2 = min(box1[3], box2[3])
    iw = max(0, ix2 - ix1)
    ih = max(0, iy2 - iy1)
    inter = iw * ih
    if inter == 0:
        return 0.0
    area1 = max(1, (box1[2] - box1[0]) * (box1[3] - box1[1]))
    area2 = max(1, (box2[2] - box2[0]) * (box2[3] - box2[1]))
    return inter / float(min(area1, area2))


def _draw_multi_person_boxes(
    frame: np.ndarray,
    faces: list[Any],
    points: dict[str, Any] | None,
    cached_objects: list[Any] | None,
    fall_result: Any | None,
    cv2: Any,
) -> None:
    """
    Vẽ khung xác định người độc lập cho từng người xuất hiện trong khung hình.
    Đảm bảo: "Mỗi người mỗi khung riêng" (Multi-Person Bounding Boxes).
    
    1. Lấy bounding box của người từ YOLOv8 (nếu có).
    2. Nếu có MediaPipe Pose skeleton: dựng khung bao quanh cơ thể người đang được phân tích tư thế.
    3. Đối với các khuôn mặt còn lại chưa có khung thân người: ước lượng khung thân trên (upper-body box).
    4. Gán nhãn tên người và trạng thái an toàn / té ngã riêng cho từng người.
    """
    if frame is None:
        return
    h_f, w_f = frame.shape[:2]

    person_boxes: list[dict[str, Any]] = []

    # 1. Thu thập box từ YOLOv8 object detector nếu có
    if cached_objects:
        for obj in cached_objects:
            if getattr(obj, "label", "") == "person":
                ox, oy, ow, oh = obj.box
                bx1 = max(0, int(ox))
                by1 = max(0, int(oy))
                bx2 = min(w_f - 1, int(ox + ow))
                by2 = min(h_f - 1, int(oy + oh))
                if (bx2 - bx1) >= 30 and (by2 - by1) >= 40:
                    person_boxes.append({
                        "box": (bx1, by1, bx2, by2),
                        "name": "",
                        "person_type": "NORMAL",
                        "confidence": float(getattr(obj, "confidence", 0.85)),
                        "has_pose": False,
                        "source": "yolo",
                    })

    # 2. Thu thập box từ MediaPipe Pose skeleton (người đang được phân tích thăng bằng/té ngã)
    if points:
        vis_pts = [p for p in points.values() if getattr(p, "visibility", 0) > 0.22]
        if len(vis_pts) >= 4:
            xs = [p.x * w_f for p in vis_pts]
            ys = [p.y * h_f for p in vis_pts]
            pose_box = (
                max(0, int(min(xs) - 18)),
                max(0, int(min(ys) - 18)),
                min(w_f - 1, int(max(xs) + 18)),
                min(h_f - 1, int(max(ys) + 18)),
            )
            matched_yolo = False
            for pb in person_boxes:
                if _compute_box_overlap_ratio(pb["box"], pose_box) >= 0.40:
                    pb["has_pose"] = True
                    matched_yolo = True
                    break
            if not matched_yolo and (pose_box[2] - pose_box[0] >= 30) and (pose_box[3] - pose_box[1] >= 40):
                person_boxes.append({
                    "box": pose_box,
                    "name": "",
                    "person_type": "NORMAL",
                    "confidence": 0.92,
                    "has_pose": True,
                    "source": "pose",
                })

    # 3. Với mỗi khuôn mặt, liên kết vào person_box hoặc tạo upper-body box mới nếu chưa có
    for face in (faces or []):
        fx, fy, fw, fh = int(face.box[0]), int(face.box[1]), int(face.box[2]), int(face.box[3])
        fcx, fcy = fx + fw // 2, fy + fh // 2
        fname = getattr(face, "name", "")
        ptype = getattr(face.person_type, "value", str(face.person_type))

        matched_pb = None
        for pb in person_boxes:
            bx1, by1, bx2, by2 = pb["box"]
            if (bx1 - 25) <= fcx <= (bx2 + 25) and (by1 - 30) <= fcy <= (by2 * 0.80 + by1 * 0.20):
                matched_pb = pb
                break

        if matched_pb is not None:
            if not matched_pb["name"] or matched_pb["name"] == "Unknown":
                matched_pb["name"] = fname
                matched_pb["person_type"] = ptype
        else:
            est_box = (
                max(0, int(fx - 0.70 * fw)),
                max(0, int(fy - 0.15 * fh)),
                min(w_f - 1, int(fx + 1.70 * fw)),
                min(h_f - 1, int(fy + 3.80 * fh)),
            )
            is_dup = any(_compute_box_overlap_ratio(pb["box"], est_box) >= 0.45 for pb in person_boxes)
            if not is_dup:
                person_boxes.append({
                    "box": est_box,
                    "name": fname,
                    "person_type": ptype,
                    "confidence": getattr(face, "confidence", 0.80),
                    "has_pose": False,
                    "source": "face_est",
                })

    # 4. Vẽ từng khung người độc lập ("Mỗi người mỗi khung riêng")
    for pb in person_boxes:
        bx1, by1, bx2, by2 = pb["box"]
        ptype = pb["person_type"]
        pname = pb["name"]
        has_pose = pb["has_pose"]

        if ptype == "STRANGER":
            border_color = (40, 40, 230)
            display_title = "Nguoi la"
        elif ptype in ("ATTENTION", "VIP"):
            border_color = (220, 160, 50)
            display_title = f"Nguoi: {pname} [VIP]" if pname else "Nguoi [VIP]"
        elif pname and pname != "Unknown":
            border_color = (80, 200, 120)
            display_title = f"Nguoi: {pname}"
        else:
            border_color = (80, 200, 120)
            display_title = f"Nguoi ({int(pb['confidence'] * 100)}%)"

        if has_pose and fall_result:
            st = fall_result.state.value if hasattr(fall_result.state, "value") else str(fall_result.state)
            if st == "pre_fall":
                border_color = (0, 165, 255)
                display_title += " [TIEN TE NGA]"
            elif st in ("warning", "possible_fall", "fallen", "alert"):
                border_color = (30, 30, 240)
                display_title += f" [{st.upper()}]"

        cv2.rectangle(frame, (bx1, by1), (bx2, by2), border_color, 2)

        (tw, th), _ = cv2.getTextSize(display_title, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        lbl_y1 = max(0, by1 - th - 8)
        lbl_y2 = by1
        lbl_x2 = min(w_f - 1, bx1 + tw + 10)
        cv2.rectangle(frame, (bx1, lbl_y1), (lbl_x2, lbl_y2), border_color, cv2.FILLED)

        text_color = (0, 0, 0) if border_color in ((80, 200, 120), (220, 160, 50)) else (255, 255, 255)
        cv2.putText(
            frame,
            display_title,
            (bx1 + 5, lbl_y2 - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            text_color,
            1,
            cv2.LINE_AA,
        )


def _draw_faces(frame, faces, person_type_colors, cv2, show_stranger_alert: bool = False) -> None:
    has_stranger = False
    
    for face in faces:
        x, y, w, h = int(face.box[0]), int(face.box[1]), int(face.box[2]), int(face.box[3])
        color = person_type_colors.get(face.person_type, (200, 200, 200))

        # Khung viền mỏng đẹp
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        
        ptype_str = face.person_type.value if hasattr(face.person_type, "value") else str(face.person_type)
        conf_str = f" ({face.confidence:.2f})" if hasattr(face, "confidence") else ""
        if ptype_str == "STRANGER":
            label = f"NGUOI LA{conf_str}"
            has_stranger = True
        elif ptype_str == "ATTENTION":
            label = f"{face.name} [VIP]"
        else:
            label = f"{face.name}{conf_str}"

        # Vẽ thẻ nền phía trên bounding box
        (text_w, text_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        label_bg_y1 = max(0, y - text_h - 8)
        label_bg_y2 = max(text_h + 8, y)
        cv2.rectangle(frame, (x, label_bg_y1), (x + text_w + 10, label_bg_y2), color, cv2.FILLED)

        # Màu chữ tương phản
        text_color = (0, 0, 0) if ptype_str in ("FAMILY", "ATTENTION") else (255, 255, 255)
        cv2.putText(frame, label, (x + 5, label_bg_y2 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, text_color, 1, cv2.LINE_AA)

    if show_stranger_alert and has_stranger:
        h_img, w_img = frame.shape[:2]
        # Báo động ở góc trên bên phải (tránh đè lên Status Badge ở góc trái)
        badge_w = 230
        cv2.rectangle(frame, (w_img - badge_w - 20, 18), (w_img - 20, 52), (40, 40, 230), cv2.FILLED)
        cv2.putText(frame, "! CANH BAO: NGUOI LA !", (w_img - badge_w - 10, 41), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)


pipeline = FallDetectionPipeline()



