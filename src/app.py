from __future__ import annotations

import argparse
import time
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
    import winsound  # type: ignore
except Exception:
    winsound = None  # type: ignore


STATE_COLORS = {
    FallState.NORMAL: (70, 200, 90),
    FallState.LYING: (180, 180, 180),
    FallState.WARNING: (0, 190, 255),
    FallState.POSSIBLE_FALL: (0, 140, 255),
    FallState.FALLEN: (40, 40, 230),
    FallState.ALERT: (0, 0, 255),
}


class FallDetectionApp:
    def __init__(self):
        args = parse_args()
        config = load_config(args.config)

        self.latest_frame = None

        detector_config = config.detector
        if args.alert_on_long_lying:
            detector_config = replace(
                detector_config,
                alert_on_long_lying_without_fall=True
            )

        self.config = config
        self.detector = FallDetector(detector_config)
        self.feature_buffer = LandmarkFeatureBuffer(
            window_size=round(detector_config.assumed_fps)
        )
        self.ai_classifier = FallAIClassifier(config.ai)
        self.estimator = PoseEstimator()
        self.logger = EventLogger(config.app.event_log_path)

        source = (
            args.video
            if args.video
            else args.camera
            if args.camera is not None
            else args.source
        )

        self.video = VideoSource(
            source=source,
            width=config.app.camera_width,
            height=config.app.camera_height,
        )

        self.window_name = "NCKH Fall Detection"

        self.latest_result = {
            "is_fall": False,
            "confidence": 0.0,
            "timestamp": None,
        }

    def get_latest_result(self):
        return self.latest_result

    def get_latest_frame(self):
        return self.latest_frame

    def process_one_frame(self) -> bool:
        """
        Xử lý đúng 1 frame: đọc camera -> estimate pose -> detect fall -> update state.
        Đây là core logic dùng chung cho cả desktop (run) và server (run_headless).

        WHY tách riêng method này:
        Trước đây toàn bộ logic xử lý + cv2.imshow/waitKey (GUI) nằm chung 1 loop trong run().
        Khi chạy qua uvicorn (server.py), không có display, gọi cv2.imshow sẽ lỗi/crash.
        Tách phần xử lý "thuần logic" ra để server gọi lại được mà không dính GUI.

        Return False khi hết stream (video file kết thúc, camera mất kết nối hẳn)
        để caller biết dừng loop.
        """
        ok, frame = self.video.read()
        if not ok:
            return False

        points, pose_results = self.estimator.estimate(frame)

        if points:
            features = self.feature_buffer.append(points)
            ai_prediction = self.ai_classifier.predict(features)
            result = self.detector.update(points)

            # Đây là điểm MẤU CHỐT: latest_result chỉ được update tại đây.
            # Nếu loop chứa process_one_frame() không bao giờ được chạy
            # (bug gốc: server.py tạo FallDetectionApp() nhưng không chạy loop nào),
            # latest_result đứng yên ở giá trị default khai báo trong __init__,
            # tức là is_fall=False, confidence=0.0, timestamp=None mãi mãi.
            self.latest_result = {
                "is_fall": result.state in {
                    FallState.FALLEN,
                    FallState.ALERT,
                },
                "confidence": (
                    ai_prediction.probability
                    if ai_prediction.enabled
                    else 0.0
                ),
                "timestamp": time.time(),
            }

            if result.event_started:
                self.logger.write(result)
                _play_alert_sound()

            if self.config.app.draw_landmarks:
                self.estimator.draw(frame, pose_results)

            _draw_status(frame, result, ai_prediction)

        else:
            self.feature_buffer.reset()

            _draw_text(
                frame,
                "No pose detected",
                (20, 40),
                (180, 180, 180),
            )

        # luôn update frame dù có detect người hay không
        self.latest_frame = frame.copy()
        return True

    def run(self):
        """Chạy desktop, có cv2 window — dùng khi debug local bằng `python -m src.app`."""
        try:
            while True:
                if not self.process_one_frame():
                    break

                cv2.imshow(self.window_name, self.latest_frame)

                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break

                if key == ord("r"):
                    self.detector.reset()

        finally:
            self.estimator.close()
            self.video.release()
            cv2.destroyAllWindows()

    def run_headless(self):
        """
        Chạy không GUI — dùng cho server (uvicorn).

        WHY cần bản riêng:
        - Không gọi cv2.imshow/cv2.waitKey vì server không có display, gọi vào
          sẽ raise lỗi (hoặc treo) ngay từ frame đầu tiên.
        - Loop này được server.py chạy trong 1 background thread riêng (xem
          start_detection_loop trong server.py), không phải trong event loop
          của FastAPI, vì OpenCV/mediapipe là code đồng bộ (blocking) — nếu
          chạy trực tiếp trong async event loop sẽ đứng toàn bộ server, không
          serve được request nào khác trong lúc đang xử lý frame.
        """
        try:
            while True:
                if not self.process_one_frame():
                    break
        finally:
            self.estimator.close()
            self.video.release()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Realtime fall detection demo."
    )

    parser.add_argument(
        "--source",
        default="0",
        help="Camera index, video path, HTTP stream, or RTSP URL.",
    )

    parser.add_argument(
        "--camera",
        type=int,
        help="Shortcut for --source camera index."
    )

    parser.add_argument(
        "--video",
        type=str,
        help="Shortcut for --source video path."
    )

    parser.add_argument(
        "--config",
        default="configs/default.yaml",
        help="YAML config path."
    )

    parser.add_argument(
        "--alert-on-long-lying",
        action="store_true",
        help="Alert on long lying without fall transition.",
    )

    return parser.parse_known_args()[0]


def main() -> None:
    app = FallDetectionApp()
    app.run()


def _play_alert_sound() -> None:
    if winsound is None:
        return

    try:
        winsound.MessageBeep(winsound.MB_ICONHAND)
    except Exception:
        return


def _draw_status(frame, result, ai_prediction) -> None:
    color = STATE_COLORS[result.state]

    label = (
        f"{result.state.value.upper()} | "
        f"angle={result.torso_angle_deg:.1f} | "
        f"lie={result.lying_seconds:.1f}s | "
        f"profile={result.profile}"
    )

    _draw_text(frame, label, (20, 40), color)

    if ai_prediction.enabled:
        ai_label = (
            f"AI: {ai_prediction.label} "
            f"({ai_prediction.probability:.2f})"
        )

        ai_color = (
            (40, 40, 230)
            if ai_prediction.label == "fall"
            else (70, 200, 90)
        )

        _draw_text(frame, ai_label, (20, 80), ai_color)

    else:
        _draw_text(
            frame,
            "AI: disabled/no model",
            (20, 80),
            (180, 180, 180),
        )

    if result.state in {FallState.FALLEN, FallState.ALERT}:
        height, width = frame.shape[:2]

        cv2.rectangle(
            frame,
            (0, 0),
            (width - 1, height - 1),
            color,
            6,
        )


def _draw_text(
    frame,
    text: str,
    origin: tuple[int, int],
    color: tuple[int, int, int]
) -> None:
    cv2.putText(
        frame,
        text,
        origin,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 0, 0),
        4,
        cv2.LINE_AA,
    )

    cv2.putText(
        frame,
        text,
        origin,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        color,
        2,
        cv2.LINE_AA,
    )


if __name__ == "__main__":
    main()