from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from src.fall_detector import DetectionResult


EVENT_COLUMNS = [
    "timestamp",
    "source",
    "state",
    "torso_angle_deg",
    "head_hip_delta",
    "hip_velocity",
    "angle_velocity_deg",
    "abnormal_frames",
    "lying_seconds",
    "fps",
    "profile",
    "fall_like_transition",
]


class EventLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            with self.path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(EVENT_COLUMNS)
        self.columns = self._read_columns()
        if not self.columns:
            self._write_header()
            self.columns = EVENT_COLUMNS.copy()

    def write(
        self,
        result: DetectionResult,
        source: int | str | None = None,
        fps: float | None = None,
    ) -> None:
        with self.path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=self.columns, extrasaction="ignore")
            writer.writerow(
                {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "source": "" if source is None else source,
                    "state": result.state.value,
                    "torso_angle_deg": f"{result.torso_angle_deg:.2f}",
                    "head_hip_delta": f"{result.head_hip_delta:.4f}",
                    "hip_velocity": f"{result.hip_velocity:.4f}",
                    "angle_velocity_deg": f"{result.angle_velocity_deg:.2f}",
                    "abnormal_frames": result.abnormal_frames,
                    "lying_seconds": f"{result.lying_seconds:.2f}",
                    "fps": "" if fps is None else f"{fps:.2f}",
                    "profile": result.profile,
                    "fall_like_transition": int(result.fall_like_transition),
                }
            )

    def _read_columns(self) -> list[str]:
        with self.path.open("r", newline="", encoding="utf-8") as file:
            reader = csv.reader(file)
            try:
                columns = next(reader)
            except StopIteration:
                return []
        return columns

    def _write_header(self) -> None:
        with self.path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(EVENT_COLUMNS)
