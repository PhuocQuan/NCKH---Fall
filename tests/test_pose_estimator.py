import numpy as np

from src.pose_estimator import prepare_pose_frame


def test_prepare_pose_frame_downscales_large_frame():
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    resized = prepare_pose_frame(frame, 640, 360)
    assert resized.shape[1] == 640
    assert resized.shape[0] == 360


def test_prepare_pose_frame_keeps_small_frame():
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    same = prepare_pose_frame(frame, 640, 360)
    assert same.shape == frame.shape


def test_prepare_pose_frame_disabled_when_size_zero():
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    same = prepare_pose_frame(frame, 0, 0)
    assert same.shape == frame.shape
