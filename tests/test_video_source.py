from src.video_source import SourceInfo, format_camera_label


def test_format_camera_label():
    info = SourceInfo(source=0, width=1280, height=720, fps=30.0)
    assert format_camera_label(info) == "0 (1280x720 @ 30fps)"
