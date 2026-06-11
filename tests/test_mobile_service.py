from pathlib import Path

from src.mobile_service import (
    MonitorStatus,
    _latest_snapshot,
    _status_key,
)
from src.pipeline import PipelineResult
from src.fall_detector import DetectionResult, FallState


def _detection(state: FallState) -> DetectionResult:
    return DetectionResult(
        state=state,
        torso_angle_deg=10.0,
        head_hip_delta=0.1,
        hip_velocity=0.01,
        angle_velocity_deg=1.0,
        abnormal_frames=0,
        lying_seconds=2.5,
        profile="default",
        fall_like_transition=False,
    )


def test_status_key_with_pose():
    result = PipelineResult(
        has_pose=True,
        fps=25.0,
        pose_ms=12.0,
        detection=_detection(FallState.NORMAL),
        ai_prediction=None,
        pose_results=None,
        event_logged=False,
        pose_lost_grace=False,
    )
    assert _status_key(result, waiting_first_pose=False) == "NORMAL"


def test_status_key_waiting_pose():
    result = PipelineResult(
        has_pose=False,
        fps=0.0,
        pose_ms=0.0,
        detection=None,
        ai_prediction=None,
        pose_results=None,
        event_logged=False,
        pose_lost_grace=False,
    )
    assert _status_key(result, waiting_first_pose=True) == "CHO POSE"


def test_monitor_status_to_dict():
    payload = MonitorStatus(status="ALERT", status_label="CANH BAO").to_dict()
    assert payload["status"] == "ALERT"
    assert payload["status_label"] == "CANH BAO"


def test_latest_snapshot_empty(tmp_path: Path):
    assert _latest_snapshot(tmp_path) is None


def test_latest_jpeg_empty_when_idle():
    from src.mobile_service import MobileMonitorService

    service = MobileMonitorService()
    assert service.get_latest_jpeg() is None
