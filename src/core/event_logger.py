from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from src.detection.fall_detector import DetectionResult


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

    def write(self, result: DetectionResult, event_id: str | None = None) -> None:
        timestamp_str = datetime.now().isoformat(timespec="seconds")
        
        # Write to CSV
        with self.path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    timestamp_str,
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
            
        # Write to Turso / SQLite Database
        try:
            from src.core.database import log_event
            db_id = event_id or f"EV-{int(datetime.now().timestamp())}"
            confidence = 18
            if result.state.value in {"fallen", "alert"}:
                confidence = min(99, int(70 + result.torso_angle_deg / 2))
            elif result.state.value in {"warning", "possible_fall", "lying"}:
                confidence = 81
                
            level = "Cảnh báo"
            if result.state.value in {"alert", "fallen"}:
                level = "Khẩn cấp"
                
            event_data = {
                "id": db_id,
                "timestamp": timestamp_str,
                "state": result.state.value,
                "torso_angle_deg": result.torso_angle_deg,
                "head_hip_delta": result.head_hip_delta,
                "hip_velocity": result.hip_velocity,
                "angle_velocity_deg": result.angle_velocity_deg,
                "abnormal_frames": result.abnormal_frames,
                "lying_seconds": result.lying_seconds,
                "profile": result.profile,
                "fall_like_transition": int(result.fall_like_transition),
                "camera_id": "CAM-LOCAL",
                "person_id": "BN-LOCAL",
                "confidence": confidence,
                "status": "Chưa xử lý",
                "level": level,
                "image_url": None,
                "video_url": None
            }
            log_event(event_data)
        except Exception as e:
            print(f"[EventLogger Error] Could not write event to database: {e}")

