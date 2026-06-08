from __future__ import annotations

import argparse

import cv2

from src.video_source import VideoSource, probe_camera


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check laptop camera before running fall detection.")
    parser.add_argument("--camera", type=int, default=0, help="Camera index to preview.")
    parser.add_argument("--scan", type=int, default=3, help="Number of camera indexes to scan.")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print("Scanning cameras...")
    for index in range(args.scan):
        info = probe_camera(index, args.width, args.height)
        if info:
            print(f"[OK] camera {index}: {info.width}x{info.height}, fps={info.fps:.1f}")
        else:
            print(f"[--] camera {index}: unavailable")

    print("Opening preview. Press q or Esc to exit.")
    video = VideoSource(args.camera, width=args.width, height=args.height)
    try:
        while True:
            ok, frame = video.read()
            if not ok:
                break
            cv2.imshow("Camera check", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
    except KeyboardInterrupt:
        print("Camera preview stopped.")
    finally:
        video.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
