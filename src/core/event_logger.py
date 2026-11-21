"""
File: src/core/event_logger.py
Chức năng chính: Ghi lại lịch sử (log) các sự kiện té ngã vào file CSV.
Giúp Admin có thể xem lại thời gian, trạng thái và đối tượng bị ngã.

File liên kết:
- Được gọi bởi: src/core/app.py và src/web/shared/pipeline.py
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from src.detection.fall_detector import DetectionResult


class EventLogger:
    """Class quản lý việc ghi log sự kiện."""
    def __init__(self, path: str | Path) -> None:
        """Khởi tạo Logger, tạo file CSV nếu chưa tồn tại và ghi dòng tiêu đề (header)."""
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            with self.path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(
                    [
                        "timestamp",
                        "state",
                        "person_name",
                        "person_type",
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

    def write(
        self, result: DetectionResult, person_name: str = "Unknown", person_type: str = "N/A"
    ) -> None:
        """
        Ghi một dòng vào file CSV khi có sự kiện té ngã xảy ra.
        Lưu thời gian, trạng thái, và thông tin người bị ngã.
        """
#self, result: DetectionResult, person_name: str = "Unknown", person_type: str = "N/A") -> None:
        with self.path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    datetime.now().isoformat(timespec="seconds"),
                    result.state.value,
                    person_name,
                    person_type,
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

