from __future__ import annotations

import argparse

import cv2

from src.alert_sound import FallAlarmTracker
from src.config import load_config
from src.pipeline import FallDetectionPipeline, build_pipeline_config
from src.ui_overlay import draw_controls, draw_no_pose, draw_status
from src.video_source import VideoSource


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
    config = build_pipeline_config(
        load_config(args.config),
        alert_on_long_lying=args.alert_on_long_lying,
    )

    source = args.video if args.video else args.camera if args.camera is not None else args.source
    pipeline = FallDetectionPipeline(config, source=source)
    video = VideoSource(
        source=source,
        width=config.app.camera_width,
        height=config.app.camera_height,
    )
    alarm = FallAlarmTracker(
        beep_interval_frames=max(1, round(config.detector.assumed_fps * 2))
    )

    window_name = "NCKH Fall Detection"
    print(f"Running demo from source={source}. Look for the '{window_name}' window.")
    print("Press q/Esc in the video window, r to reset, or Ctrl+C in this terminal to stop.")

    try:
        while True:
            ok, frame = video.read()
            if not ok:
                break

            result = pipeline.process_frame(frame)
            if result.has_pose:
                if config.app.draw_landmarks:
                    pipeline.estimator.draw(frame, result.pose_results)
                assert result.detection is not None
                draw_status(
                    frame,
                    result.detection,
                    result.ai_prediction,
                    config.ai.decision_mode,
                    result.fps,
                    result.pose_ms,
                )
                alarm.update(result.detection.state)
            elif result.pose_lost_grace and result.detection is not None:
                draw_status(
                    frame,
                    result.detection,
                    result.ai_prediction,
                    config.ai.decision_mode,
                    result.fps,
                    result.pose_ms,
                )
                draw_no_pose(frame, result.fps, grace=True, pose_ms=result.pose_ms)
                alarm.update(result.detection.state)
            else:
                draw_no_pose(
                    frame,
                    result.fps,
                    waiting_first_pose=pipeline.waiting_first_pose,
                    pose_ms=result.pose_ms,
                )
                alarm.reset()

            draw_controls(frame)
            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
            if key == ord("r"):
                pipeline.reset()
                alarm.reset()
    except KeyboardInterrupt:
        print("\nDemo stopped by user.")
    finally:
        pipeline.close()
        video.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
