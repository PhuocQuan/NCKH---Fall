from __future__ import annotations

from typing import Any

import cv2

from src.ai_classifier import AIPrediction
from src.fall_detector import DetectionResult, FallState

STATE_COLORS = {
    FallState.NORMAL: (70, 200, 90),
    FallState.LYING: (180, 180, 180),
    FallState.WARNING: (0, 190, 255),
    FallState.POSSIBLE_FALL: (0, 140, 255),
    FallState.FALLEN: (40, 40, 230),
    FallState.ALERT: (0, 0, 255),
}

FALL_ALARM_STATES = frozenset(
    {FallState.POSSIBLE_FALL, FallState.FALLEN, FallState.ALERT}
)


def draw_text(
    frame: Any,
    text: str,
    origin: tuple[int, int],
    color: tuple[int, int, int],
    *,
    scale: float = 0.62,
) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(frame, text, origin, font, scale, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(frame, text, origin, font, scale, color, 1, cv2.LINE_AA)


def draw_status(
    frame: Any,
    result: DetectionResult,
    ai_prediction: AIPrediction | None,
    ai_decision_mode: str,
    fps: float,
    pose_ms: float = 0.0,
) -> None:
    color = STATE_COLORS[result.state]
    label = (
        f"{result.state.value.upper()} | angle={result.torso_angle_deg:.1f} "
        f"| lie={result.lying_seconds:.1f}s | fps={fps:.1f} | pose={pose_ms:.0f}ms"
    )
    draw_text(frame, label, (20, 40), color)
    if ai_prediction is not None and ai_prediction.enabled:
        ai_label = (
            f"AI: {ai_prediction.label} ({ai_prediction.probability:.2f}) "
            f"| mode={ai_decision_mode} | profile={result.profile}"
        )
        ai_color = (40, 40, 230) if ai_prediction.label == "fall" else (70, 200, 90)
        draw_text(frame, ai_label, (20, 80), ai_color)
    else:
        draw_text(
            frame,
            f"AI: disabled/no model | profile={result.profile}",
            (20, 80),
            (180, 180, 180),
        )
    if result.state in FALL_ALARM_STATES:
        draw_alarm_border(frame, color)


def draw_no_pose(
    frame: Any,
    fps: float,
    *,
    grace: bool = False,
    waiting_first_pose: bool = False,
    pose_ms: float = 0.0,
) -> None:
    if grace:
        message = "Tam mat pose - dang giu trang thai"
        color = (0, 200, 255)
    elif waiting_first_pose:
        message = "Camera OK - hay dung that ro co the trong khung hinh"
        color = (0, 220, 255)
    else:
        message = "Khong thay nguoi trong khung hinh"
        color = (180, 180, 180)
    draw_text(frame, message, (20, 40), color)
    draw_text(
        frame,
        f"Camera: ON | FPS: {fps:.1f} | Pose: {pose_ms:.0f}ms",
        (20, 80),
        (180, 180, 180),
    )
    if grace:
        height, width = frame.shape[:2]
        cv2.rectangle(frame, (0, 0), (width - 1, height - 1), (0, 200, 255), 4)


def draw_alarm_border(frame: Any, color: tuple[int, int, int]) -> None:
    height, width = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (width - 1, height - 1), color, 6)


def draw_controls(frame: Any) -> None:
    height, width = frame.shape[:2]
    text = "q/Esc: thoat | r: reset | Ctrl+C: dung trong terminal"
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.65
    thickness = 2
    (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    padding = 10
    x = 16
    y = height - 18
    box_right = min(width - 12, x + text_width + padding * 2)
    box_top = max(0, y - text_height - baseline - padding)

    overlay = frame.copy()
    cv2.rectangle(overlay, (x - padding, box_top), (box_right, height - 8), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
    cv2.putText(frame, text, (x, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
