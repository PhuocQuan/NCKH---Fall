from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2

from src.feature_extractor import FEATURE_NAMES, LandmarkFeatureBuffer
from src.pose_estimator import PoseEstimator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build feature CSV from labeled videos.")
    parser.add_argument("--input", required=True, help="Root folder with label subfolders.")
    parser.add_argument("--output", default="data/features.csv", help="Output CSV path.")
    parser.add_argument("--window-size", type=int, default=30, help="Frames per feature window.")
    parser.add_argument("--stride", type=int, default=10, help="Write one sample every N frames.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_root = Path(args.input)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    video_paths = sorted(
        path
        for path in input_root.rglob("*")
        if path.suffix.lower() in {".mp4", ".avi", ".mov", ".mkv"}
    )
    if not video_paths:
        raise ValueError(f"Khong tim thay video trong {input_root}")

    estimator = PoseEstimator(static_image_mode=False)
    rows_written = 0
    try:
        with output.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["video", "label", *FEATURE_NAMES])

            for video_path in video_paths:
                label = video_path.parent.name
                rows_written += _process_video(
                    video_path=video_path,
                    label=label,
                    estimator=estimator,
                    writer=writer,
                    window_size=args.window_size,
                    stride=args.stride,
                )
                print(f"{video_path}: label={label}")
    finally:
        estimator.close()

    print(f"Saved {rows_written} samples to {output}")


def _process_video(
    video_path: Path,
    label: str,
    estimator: PoseEstimator,
    writer,
    window_size: int,
    stride: int,
) -> int:
    capture = cv2.VideoCapture(str(video_path))
    buffer = LandmarkFeatureBuffer(window_size=window_size)
    frame_index = 0
    rows = 0

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            points, _ = estimator.estimate(frame)
            if points is None:
                buffer.reset()
                frame_index += 1
                continue

            features = buffer.append(points)
            if frame_index >= window_size and frame_index % stride == 0:
                writer.writerow([str(video_path), label, *features.values.tolist()])
                rows += 1
            frame_index += 1
    finally:
        capture.release()
    return rows


if __name__ == "__main__":
    main()

