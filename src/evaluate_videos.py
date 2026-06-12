from __future__ import annotations

import argparse
import csv
from dataclasses import replace
from pathlib import Path

import cv2

from src.ai_classifier import FallAIClassifier
from src.config import load_config
from src.decision_fusion import fuse_detection_with_ai
from src.feature_extractor import LandmarkFeatureBuffer
from src.fall_detector import FallDetector, FallState
from src.pose_estimator import PoseEstimator


FALL_LABELS = {"fall", "falls", "te_nga"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate fall detection on labeled videos.")
    parser.add_argument("--input", default="data/videos", help="Root folder with label subfolders.")
    parser.add_argument("--config", default="configs/default.yaml", help="YAML config path.")
    parser.add_argument("--output", default="data/evaluation/video_results.csv", help="Per-video CSV.")
    parser.add_argument(
        "--positive-states",
        default="fallen,alert",
        help="Comma-separated states counted as predicted fall.",
    )
    parser.add_argument(
        "--alert-on-long-lying",
        action="store_true",
        help="Use demo mode while evaluating. Not recommended for final report.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_root = Path(args.input)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    positive_states = {
        FallState(value.strip()) for value in args.positive_states.split(",") if value.strip()
    }

    video_paths = sorted(
        path
        for path in input_root.rglob("*")
        if path.suffix.lower() in VIDEO_EXTENSIONS and path.is_file()
    )
    if not video_paths:
        raise ValueError(f"Khong tim thay video trong {input_root}")

    config = load_config(args.config)
    detector_config = config.detector
    if args.alert_on_long_lying:
        detector_config = replace(detector_config, alert_on_long_lying_without_fall=True)

    estimator = PoseEstimator(config.pose)
    ai_classifier = FallAIClassifier(config.ai)
    rows: list[dict[str, str | int | float]] = []
    try:
        for video_path in video_paths:
            row = _evaluate_video(
                video_path=video_path,
                label=video_path.parent.name,
                detector_config=detector_config,
                estimator=estimator,
                ai_classifier=ai_classifier,
                ai_config=config.ai,
                positive_states=positive_states,
            )
            rows.append(row)
            print(
                f"{video_path}: truth={row['truth']} predicted={row['predicted']} "
                f"state={row['max_state']}"
            )
    finally:
        estimator.close()

    _write_rows(output, rows)
    _print_summary(rows)


def _evaluate_video(
    video_path: Path,
    label: str,
    detector_config,
    estimator: PoseEstimator,
    ai_classifier: FallAIClassifier,
    ai_config,
    positive_states: set[FallState],
) -> dict[str, str | int | float]:
    detector = FallDetector(detector_config)
    feature_buffer = LandmarkFeatureBuffer(window_size=round(detector_config.assumed_fps))
    ai_classifier.reset()
    capture = cv2.VideoCapture(str(video_path))
    frame_index = 0
    pose_frames = 0
    max_state = FallState.NORMAL
    first_positive_frame = -1
    max_ai_probability = 0.0

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break

            pose_estimate = estimator.estimate(frame)
            points = pose_estimate.points
            if points is None:
                feature_buffer.reset()
                detector.reset()
                frame_index += 1
                continue

            pose_frames += 1
            features = feature_buffer.append(points)
            ai_prediction = ai_classifier.predict(features)
            max_ai_probability = max(max_ai_probability, ai_prediction.probability)
            result = detector.update(points)
            result = fuse_detection_with_ai(result, ai_prediction, ai_config)

            if _state_rank(result.state) > _state_rank(max_state):
                max_state = result.state
            if result.state in positive_states and first_positive_frame < 0:
                first_positive_frame = frame_index
            frame_index += 1
    finally:
        capture.release()

    truth = 1 if label.lower() in FALL_LABELS else 0
    predicted = 1 if first_positive_frame >= 0 else 0
    return {
        "video": str(video_path),
        "label": label,
        "truth": truth,
        "predicted": predicted,
        "max_state": max_state.value,
        "first_positive_frame": first_positive_frame,
        "frames": frame_index,
        "pose_frames": pose_frames,
        "pose_coverage": 0.0 if frame_index == 0 else pose_frames / frame_index,
        "max_ai_probability": max_ai_probability,
    }


def _write_rows(output: Path, rows: list[dict[str, str | int | float]]) -> None:
    fieldnames = [
        "video",
        "label",
        "truth",
        "predicted",
        "max_state",
        "first_positive_frame",
        "frames",
        "pose_frames",
        "pose_coverage",
        "max_ai_probability",
    ]
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved per-video results to {output}")


def _print_summary(rows: list[dict[str, str | int | float]]) -> None:
    tp = sum(1 for row in rows if row["truth"] == 1 and row["predicted"] == 1)
    tn = sum(1 for row in rows if row["truth"] == 0 and row["predicted"] == 0)
    fp = sum(1 for row in rows if row["truth"] == 0 and row["predicted"] == 1)
    fn = sum(1 for row in rows if row["truth"] == 1 and row["predicted"] == 0)
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    accuracy = _safe_div(tp + tn, len(rows))

    print("\nSummary:")
    print(f"- videos: {len(rows)}")
    print(f"- TP={tp} FP={fp} TN={tn} FN={fn}")
    print(f"- accuracy={accuracy:.3f} precision={precision:.3f} recall={recall:.3f} f1={f1:.3f}")


def _safe_div(numerator: float, denominator: float) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def _state_rank(state: FallState) -> int:
    return {
        FallState.NORMAL: 0,
        FallState.LYING: 1,
        FallState.WARNING: 2,
        FallState.POSSIBLE_FALL: 3,
        FallState.FALLEN: 4,
        FallState.ALERT: 5,
    }[state]


if __name__ == "__main__":
    main()
