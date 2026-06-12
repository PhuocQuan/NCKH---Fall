from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import cv2

DEFAULT_SNAPSHOT_DIR = Path("data/snapshots")


def save_alert_snapshot(
    frame_bgr: Any,
    output_dir: str | Path = DEFAULT_SNAPSHOT_DIR,
    *,
    prefix: str = "alert",
) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = directory / f"{prefix}_{timestamp}.jpg"
    if not cv2.imwrite(str(path), frame_bgr):
        raise RuntimeError(f"Khong luu duoc snapshot: {path}")
    return path
