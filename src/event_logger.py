from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from src.fall_detector import DetectionResult


class EventLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            with self.path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(
                    [
                        "timestamp",
                        "state",
                        "torso_angle_deg",
                        "head_hip_delta",
                        "hip_velocity",
                        "angle_velocity_deg",
                        "abnormal_frames",
                        "lying_seconds",
                        "profile",
                        "fall_like_transition",
                    ]
                )

    def write(self, result: DetectionResult) -> None:
        with self.path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    datetime.now().isoformat(timespec="seconds"),
                    result.state.value,
                    f"{result.torso_angle_deg:.2f}",
                    f"{result.head_hip_delta:.4f}",
                    f"{result.hip_velocity:.4f}",
                    f"{result.angle_velocity_deg:.2f}",
                    result.abnormal_frames,
                    f"{result.lying_seconds:.2f}",
                    result.profile,
                    int(result.fall_like_transition),
                ]
            )
