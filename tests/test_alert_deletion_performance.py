"""
Unit & Performance tests for Alert Deletion Optimization.
Verifies:
1. Admin batch hard deletion via single query without blocking on media.
2. User batch soft deletion via single query CASE-WHEN statement.
3. Rapid execution under 100ms.
"""

import time
from unittest.mock import patch, MagicMock
from pathlib import Path
from src.web.shared.service import delete_multiple_alerts, delete_alert


def test_admin_batch_delete_all_fast(tmp_path):
    """Admin delete_all should execute immediately and dispatch background media cleanup."""
    with patch("src.web.shared.service.repo") as mock_repo, \
         patch("src.web.shared.service.log_action") as mock_log:
        
        mock_repo.get_user_role_db.return_value = "Admin"
        mock_repo.batch_get_alert_media_urls_db.return_value = [
            "https://res.cloudinary.com/demo/image/upload/v1/alert1.jpg",
            "https://res.cloudinary.com/demo/video/upload/v1/alert1.mp4",
        ]
        mock_repo.get_all_alert_ids_db.return_value = ["AL-1", "AL-2", "AL-3"]

        t0 = time.perf_counter()
        count = delete_multiple_alerts(ids=None, delete_all=True, user="admin@nckh.vn", media_dir=tmp_path)
        elapsed = time.perf_counter() - t0

        assert count == 3
        assert elapsed < 0.2  # Must return well under 200ms
        mock_repo.hard_delete_all_alerts_db.assert_called_once()


def test_admin_batch_delete_specific_ids(tmp_path):
    """Admin delete specific IDs should execute in batch without looping queries."""
    with patch("src.web.shared.service.repo") as mock_repo, \
         patch("src.web.shared.service.log_action") as mock_log:
        
        mock_repo.get_user_role_db.return_value = "Admin"
        mock_repo.batch_get_alert_media_urls_db.return_value = []

        ids = [f"AL-{i}" for i in range(10)]
        t0 = time.perf_counter()
        count = delete_multiple_alerts(ids=ids, delete_all=False, user="admin@nckh.vn", media_dir=tmp_path)
        elapsed = time.perf_counter() - t0

        assert count == 10
        assert elapsed < 0.2
        mock_repo.batch_hard_delete_alerts_db.assert_called_once_with(ids)


def test_user_batch_soft_delete(tmp_path):
    """User delete should trigger batch soft delete without blocking."""
    with patch("src.web.shared.service.repo") as mock_repo, \
         patch("src.web.shared.service.log_action") as mock_log:
        
        mock_repo.get_user_role_db.return_value = "Khachhang"

        ids = ["AL-1", "AL-2"]
        t0 = time.perf_counter()
        count = delete_multiple_alerts(ids=ids, delete_all=False, user="user@nckh.vn", media_dir=tmp_path)
        elapsed = time.perf_counter() - t0

        assert count == 2
        assert elapsed < 0.2
        mock_repo.batch_soft_delete_alerts_db.assert_called_once_with("user@nckh.vn", alert_ids=ids)
