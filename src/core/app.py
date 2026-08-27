"""
File: src/core/app.py
Chức năng chính: Điểm khởi chạy (entry point) của luồng Camera (Video/Webcam). 
File này liên kết và gọi các module khác để thực hiện chu trình:
1. Đọc video (từ src/camera/video_source.py)
2. Ước lượng tư thế bằng MediaPipe (từ src/detection/pose_estimator.py)
3. Nhận diện khuôn mặt (từ src/face/face_recognizer.py)
4. Phát hiện té ngã (từ src/detection/fall_detector.py)
5. Dự đoán bằng AI (từ src/ai/ai_classifier.py)
6. Ghi log sự kiện và vẽ lên màn hình.

File liên kết (Ảnh hưởng / Bị ảnh hưởng):
- Gọi tới: src.detection.*, src.face.*, src.ai.*
- Bị gọi bởi: src/web/shared/pipeline.py (khi chạy luồng AI chung với Server)
"""
from __future__ import annotations

import argparse
import threading
from dataclasses import replace
from pathlib import Path

import cv2

from src.ai.ai_classifier import FallAIClassifier
from src.core.config import load_config
from src.core.event_logger import EventLogger
from src.detection.feature_extractor import LandmarkFeatureBuffer
from src.detection.fall_detector import FallDetector, FallState
from src.detection.pose_estimator import PoseEstimator
from src.camera.video_source import VideoSource
from src.face import FaceRecognizer, PersonType, RecognizedFace

try:
    # Windows-only: dùng để phát "beep" khi có cảnh báo té ngã hoặc người lạ.
    import winsound  # type: ignore
except Exception:  # pragma: no cover
    winsound = None  # type: ignore


STATE_COLORS = {
    FallState.NORMAL: (70, 200, 90),
    FallState.LYING: (180, 180, 180),
    FallState.WARNING: (0, 190, 255),
    FallState.POSSIBLE_FALL: (0, 140, 255),
    FallState.FALLEN: (40, 40, 230),
    FallState.ALERT: (0, 0, 255),
}

PERSON_TYPE_COLORS = {
    PersonType.FAMILY: (70, 200, 90),
    PersonType.ATTENTION: (0, 220, 255),
    PersonType.STRANGER: (40, 40, 230),
}

# Kêu chuông ngay khi nghi ngờ / xác nhận té ngã, không đợi ALERT (10 giây).
FALL_ALARM_STATES = frozenset(
    {FallState.POSSIBLE_FALL, FallState.FALLEN, FallState.ALERT}
)


def parse_args() -> argparse.Namespace:
    """
    Hàm phân tích các tham số dòng lệnh (command line arguments) khi chạy file này trực tiếp.
    Ví dụ: python -m src.core.app --source 0 --config configs/default.yaml
    
    Returns:
        argparse.Namespace: Chứa các tham số cấu hình truyền vào.
    """
    parser = argparse.ArgumentParser(description="Realtime fall detection demo.")
    parser.add_argument(
        "--source",
        default="0",
        help="Camera index, video path, HTTP stream, or RTSP URL. Example: 0 or rtsp://user:pass@ip/stream",
    )
    parser.add_argument("--camera", type=int, help="Shortcut for --source camera index.")
    parser.add_argument("--video", type=str, help="Shortcut for --source video path.")
    parser.add_argument("--config", default="configs/default.yaml", help="YAML config path.")
    parser.add_argument(
        "--alert-on-long-lying",
        action="store_true",
        help="Demo mode: alert on long lying even without a fall-like transition.",
    )
    return parser.parse_args()


def main() -> None:
    """
    Hàm chính (main) của chương trình.
    Các bước thực hiện:
    1. Tải cấu hình từ yaml (load_config).
    2. Khởi tạo các module lõi: FallDetector, PoseEstimator, FaceRecognizer, AIClassifier.
    3. Mở luồng video (VideoSource).
    4. Vòng lặp chính:
       a. Đọc từng frame từ video/camera.
       b. Quét khuôn mặt nếu đến chu kỳ (process_every_n_frames).
       c. Trích xuất khung xương (PoseEstimator).
       d. Đưa khung xương vào thuật toán (FallDetector) và AI (AIClassifier) để dự đoán.
       e. Ghi log nếu có người ngã.
       f. Vẽ kết quả lên màn hình (khung xương, cảnh báo, khuôn mặt).
    5. Xử lý sự kiện phím bấm (nhấn 's' để lưu khuôn mặt mới, 'r' để reset trạng thái).
    """
    args = parse_args()
    config = load_config(args.config)
    detector_config = config.detector
    if args.alert_on_long_lying:
        detector_config = replace(detector_config, alert_on_long_lying_without_fall=True)
    detector = FallDetector(detector_config)
    feature_buffer = LandmarkFeatureBuffer(window_size=round(detector_config.assumed_fps))
    ai_classifier = FallAIClassifier(config.ai)
    estimator = PoseEstimator(model_complexity=config.app.model_complexity)
    logger = EventLogger(config.app.event_log_path)
    face_recognizer = FaceRecognizer(config.face)

    source = args.video if args.video else args.camera if args.camera is not None else args.source
    video = VideoSource(
        source=source,
        width=config.app.camera_width,
        height=config.app.camera_height,
    )

    window_name = "NCKH Fall Detection & Face Recognition"
    alert_beep_interval_frames = max(1, round(detector_config.assumed_fps * 2))
    frames_since_alert_beep = alert_beep_interval_frames
    prev_fall_state = FallState.NORMAL

    frame_count = 0
    cached_faces: list[RecognizedFace] = []

    try:
        while True:
            ok, frame = video.read()
            if not ok:
                break

            frame_count += 1
            # Quét khuôn mặt mỗi N frame để đảm bảo FPS mượt mà
            if config.face.enabled and (frame_count % config.face.process_every_n_frames == 0 or not cached_faces):
                cached_faces = face_recognizer.recognize(frame)

            # Lấy thông tin người đầu tiên nhận diện được trong frame (nếu có)
            current_person_name = cached_faces[0].name if cached_faces else "Unknown"
            current_person_type = cached_faces[0].person_type.value if cached_faces else "N/A"

            points, pose_results = estimator.estimate(frame)
            result = None
            if points:
                features = feature_buffer.append(points)
                ai_prediction = ai_classifier.predict(features)
                result = detector.update(points)
                if result.event_started:
                    logger.write(result, person_name=current_person_name, person_type=current_person_type)
                frames_since_alert_beep, prev_fall_state = _update_fall_alarm(
                    result.state,
                    prev_fall_state,
                    frames_since_alert_beep,
                    alert_beep_interval_frames,
                )
                if config.app.draw_landmarks:
                    estimator.draw(frame, pose_results)
                _draw_status(frame, result, ai_prediction, current_person_name, current_person_type)
            else:
                feature_buffer.reset()
                prev_fall_state = FallState.NORMAL
                frames_since_alert_beep = alert_beep_interval_frames
                _draw_text(frame, "No pose detected", (20, 40), (180, 180, 180))

            # Vẽ bounding boxes khuôn mặt
            _draw_faces(frame, cached_faces)

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
            if key == ord("r"):
                detector.reset()
                prev_fall_state = FallState.NORMAL
                frames_since_alert_beep = alert_beep_interval_frames
            if key == ord("s"):
                # Đăng ký ảnh mới từ camera
                print("\n[Save Face] Nhập tên người cần đăng ký (ví dụ: OngNoi_ATTENTION hoặc Me_FAMILY): ")
                new_name = input("Tên: ").strip()
                if new_name:
                    save_path = Path(config.face.known_faces_dir) / f"{new_name}.jpg"
                    cv2.imwrite(str(save_path), frame)
                    print(f"Đã lưu ảnh khuôn mặt tại: {save_path}")
                    face_recognizer.reload_known_faces()
    finally:
        estimator.close()
        video.release()
        cv2.destroyAllWindows()


def _update_fall_alarm( # type: ignore
    state: FallState,
    prev_state: FallState,
    frames_since_beep: int,
    beep_interval_frames: int,
) -> tuple[int, FallState]:
    """
    Kiểm tra trạng thái hiện tại và quyết định có phát chuông báo động hay không.
    
    Logic từng bước:
    1. Nếu trạng thái hiện tại là NGÃ (nằm trong FALL_ALARM_STATES):
       - Nếu trước đó chưa ngã -> Vừa mới ngã -> Kêu chuông lập tức.
       - Nếu trước đó đã ngã rồi -> Đang nằm -> Chờ hết chu kỳ (beep_interval_frames) rồi kêu tiếp.
    2. Trả về số frame đếm ngược cho lần kêu tiếp theo và trạng thái hiện tại.
    """

    if state in FALL_ALARM_STATES:
        if prev_state not in FALL_ALARM_STATES:
            frames_since_beep = 0
            _play_alert_sound()
        else:
            frames_since_beep += 1
            if frames_since_beep >= beep_interval_frames:
                frames_since_beep = 0
                _play_alert_sound()
    else:
        frames_since_beep = beep_interval_frames

    return frames_since_beep, state


def _play_alert_sound() -> None:
    """
    Phát âm thanh cảnh báo "bíp bíp" trên Windows.
    Sử dụng luồng riêng (threading.Thread) để việc phát âm thanh không làm đứng hình (lag) camera.
    """

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


def _draw_status(frame, result, ai_prediction) -> None:
    """
    Vẽ trạng thái té ngã và kết quả AI lên góc trái màn hình video.
    
    Args:
        frame: Khung hình hiện tại (OpenCV Mat).
        result: Kết quả từ FallDetector (chứa góc, thời gian nằm, trạng thái).
        ai_prediction: Kết quả dự đoán từ mô hình AI.
    """
    color = STATE_COLORS[result.state]
    label = (
        f"{result.state.value.upper()} | angle={result.torso_angle_deg:.1f} "
        f"| lie={result.lying_seconds:.1f}s | profile={result.profile}"
    )
    _draw_text(frame, label, (20, 40), color)
    if ai_prediction.enabled:
        ai_label = f"AI: {ai_prediction.label} ({ai_prediction.probability:.2f})"
        ai_color = (40, 40, 230) if ai_prediction.label == "fall" else (70, 200, 90)
        _draw_text(frame, ai_label, (20, 80), ai_color)
    else:
        _draw_text(frame, "AI: disabled/no model", (20, 80), (180, 180, 180))
    if result.state in FALL_ALARM_STATES:
        height, width = frame.shape[:2]
        cv2.rectangle(frame, (0, 0), (width - 1, height - 1), color, 6)


def _draw_text(frame, text: str, origin: tuple[int, int], color: tuple[int, int, int]) -> None:
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2, cv2.LINE_AA)


def _draw_faces(frame: cv2.Mat, faces: list[RecognizedFace]) -> None:
    """
    Vẽ khung viền (bounding box) và tên của những khuôn mặt nhận diện được lên màn hình.
    Đồng thời hiện cảnh báo góc phải màn hình nếu phát hiện người lạ (STRANGER).
    
    Args:
        frame: Khung hình hiện tại.
        faces: Danh sách các khuôn mặt đã được nhận diện.
    """
    has_stranger = False
    for face in faces:
        x, y, w, h = face.box
        color = PERSON_TYPE_COLORS.get(face.person_type, (200, 200, 200))

        # Khung viền mỏng đẹp
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

        # Định dạng nhãn sạch gọn
        ptype_str = face.person_type.value if hasattr(face.person_type, "value") else str(face.person_type)
        if ptype_str == "STRANGER":
            label = "NGUOI LA"
            has_stranger = True
        elif ptype_str == "ATTENTION":
            label = f"{face.name} [VIP]"
        else:
            label = f"{face.name}"

        # Thẻ nền phía trên bounding box
        (text_w, text_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        label_bg_y1 = max(0, y - text_h - 8)
        label_bg_y2 = max(text_h + 8, y)
        cv2.rectangle(frame, (x, label_bg_y1), (x + text_w + 10, label_bg_y2), color, cv2.FILLED)

        # Màu chữ tương phản
        text_color = (0, 0, 0) if ptype_str in ("FAMILY", "ATTENTION") else (255, 255, 255)
        cv2.putText(frame, label, (x + 5, label_bg_y2 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, text_color, 1, cv2.LINE_AA)

    if has_stranger:
        h_img, w_img = frame.shape[:2]
        badge_w = 230
        cv2.rectangle(frame, (w_img - badge_w - 20, 18), (w_img - 20, 52), (40, 40, 230), cv2.FILLED)
        cv2.putText(frame, "! CANH BAO: NGUOI LA !", (w_img - badge_w - 10, 41), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)


if __name__ == "__main__":
    main()


