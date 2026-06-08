from __future__ import annotations

import argparse
from dataclasses import replace

import cv2

from src.ai_classifier import FallAIClassifier
from src.config import load_config
from src.event_logger import EventLogger
from src.feature_extractor import LandmarkFeatureBuffer
from src.fall_detector import FallDetector, FallState
from src.pose_estimator import PoseEstimator
from src.video_source import VideoSource

try:
    # Windows-only: dùng để phát "beep" khi có cảnh báo té ngã.
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


def parse_args() -> argparse.Namespace:
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
    args = parse_args()
    config = load_config(args.config)
    detector_config = config.detector
    if args.alert_on_long_lying:
        detector_config = replace(detector_config, alert_on_long_lying_without_fall=True)
    detector = FallDetector(detector_config)
    feature_buffer = LandmarkFeatureBuffer(window_size=round(detector_config.assumed_fps))
    ai_classifier = FallAIClassifier(config.ai)
    estimator = PoseEstimator()
    logger = EventLogger(config.app.event_log_path)

    source = args.video if args.video else args.camera if args.camera is not None else args.source
    video = VideoSource(
        source=source,
        width=config.app.camera_width,
        height=config.app.camera_height,
    )

    window_name = "NCKH Fall Detection"

    try:
        while True:
            ok, frame = video.read()
            if not ok:
                break

            points, pose_results = estimator.estimate(frame)
            result = None
            if points:
                features = feature_buffer.append(points)
                ai_prediction = ai_classifier.predict(features)
                result = detector.update(points)
                if result.event_started:
                    logger.write(result)
                    _play_alert_sound()
                if config.app.draw_landmarks:
                    estimator.draw(frame, pose_results)
                _draw_status(frame, result, ai_prediction)
            else:
                feature_buffer.reset()
                _draw_text(frame, "No pose detected", (20, 40), (180, 180, 180))

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
            if key == ord("r"):
                detector.reset()
    finally:
        estimator.close()
        video.release()
        cv2.destroyAllWindows()

def _play_alert_sound() -> None:
    """Phát âm thanh khi có cảnh báo té ngã.

    Thiết kế: chỉ kêu khi detector bắn `event_started`, tức là thời điểm chuyển sang
    trạng thái `ALERT` (không kêu khi chỉ nằm ngủ bình thường).
    """

    if winsound is None:
        return
    try:
        # MessageBeep là "beep" hệ thống, không cần file âm thanh.
        winsound.MessageBeep(winsound.MB_ICONHAND)
    except Exception:
        # Nếu hệ thống không cho phát âm thanh thì bỏ qua để không làm crash app.
        return


def _draw_status(frame, result, ai_prediction) -> None:
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
    if result.state in {FallState.FALLEN, FallState.ALERT}:
        height, width = frame.shape[:2]
        cv2.rectangle(frame, (0, 0), (width - 1, height - 1), color, 6)


def _draw_text(frame, text: str, origin: tuple[int, int], color: tuple[int, int, int]) -> None:
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2, cv2.LINE_AA)


if __name__ == "__main__":
    main()
