import numpy as np

from src.snapshot import save_alert_snapshot


def test_save_alert_snapshot_writes_file(tmp_path):
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    path = save_alert_snapshot(frame, output_dir=tmp_path)

    assert path.exists()
    assert path.suffix == ".jpg"
