import os
import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.database import (
    get_db_connection,
    init_db_schema,
    verify_user,
    create_session,
    verify_session_token,
    delete_session,
    log_event,
    update_event_media,
    get_events,
    get_recent_alerts,
    upload_media,
    get_kv,
    save_kv
)

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    """Fixture to mock DB config and use a temporary database file for each test."""
    db_file = tmp_path / "test_fallguard.db"
    
    # Patch load_db_config to return empty configs so it falls back to local SQLite
    with patch("src.core.database.load_db_config") as mock_load_config, \
         patch("src.core.database.LOCAL_DB_PATH", db_file):
        
        mock_load_config.return_value = {
            "turso": {"url": "", "auth_token": ""}
        }
        
        # Reset the connection global
        import src.core.database
        src.core.database._db_conn = None
        
        yield db_file
        
        # Close connection and clean up
        if src.core.database._db_conn:
            src.core.database._db_conn.close()
            src.core.database._db_conn = None

def test_db_initialization(setup_test_db):
    """Test that schema is initialized and default users are seeded."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    assert "users" in tables
    assert "sessions" in tables
    assert "events" in tables
    
    # Check default seeded users
    cursor.execute("SELECT username, role FROM users")
    users = cursor.fetchall()
    user_map = {row[0]: row[1] for row in users}
    assert "admin" in user_map
    assert user_map["admin"] == "Admin"
    assert "guest" in user_map

def test_user_verification():
    """Test verification of seeded users."""
    assert verify_user("admin", "nckh2025") is True
    assert verify_user("manager", "nckh2025") is True
    assert verify_user("admin", "wrongpassword") is False
    assert verify_user("nonexistent", "nckh2025") is False

def test_session_lifecycle():
    """Test creating, verifying, and deleting sessions."""
    # Create session
    token = create_session("admin", ttl_seconds=5)
    assert token is not None
    assert len(token) > 20
    
    # Verify token
    username = verify_session_token(token)
    assert username == "admin"
    
    # Verify non-existent token
    assert verify_session_token("invalid_token") is None
    
    # Delete session
    delete_session(token)
    assert verify_session_token(token) is None

def test_expired_session():
    """Test verification fails for expired sessions."""
    # Create session with negative TTL so it's already expired
    token = create_session("admin", ttl_seconds=-10)
    
    # Should return None because it is expired
    assert verify_session_token(token) is None

def test_event_logging_and_retrieval():
    """Test logging events, retrieving them, and listing recent alerts."""
    event1 = {
        "id": "AL-11111",
        "timestamp": "2026-06-15T22:30:00",
        "state": "alert",
        "torso_angle_deg": 65.4,
        "head_hip_delta": 0.15,
        "hip_velocity": 0.04,
        "angle_velocity_deg": 20.0,
        "abnormal_frames": 8,
        "lying_seconds": 12.5,
        "profile": "default",
        "fall_like_transition": 1,
        "camera_id": "CAM-TEST",
        "person_id": "BN-TEST",
        "confidence": 85,
        "status": "Chưa xử lý",
        "level": "Khẩn cấp"
    }
    
    event2 = {
        "id": "EV-22222",
        "timestamp": "2026-06-15T22:35:00",
        "state": "normal",
        "torso_angle_deg": 10.2,
        "head_hip_delta": 0.45,
        "hip_velocity": 0.001,
        "angle_velocity_deg": 0.5,
        "abnormal_frames": 0,
        "lying_seconds": 0.0,
        "profile": "default",
        "fall_like_transition": 0,
        "camera_id": "CAM-TEST",
        "person_id": "BN-TEST",
        "confidence": 18,
        "status": "Chưa ghi nhận",
        "level": "Cảnh báo"
    }
    
    # Log events
    log_event(event1)
    log_event(event2)
    
    # Retrieve all events
    events = get_events(limit=10)
    assert len(events) == 2
    
    event_ids = [e["id"] for e in events]
    assert "AL-11111" in event_ids
    assert "EV-22222" in event_ids
    
    # Get recent alerts (only should return event1 which is state='alert')
    alerts = get_recent_alerts(limit=10)
    assert len(alerts) == 1
    assert alerts[0]["id"] == "AL-11111"
    assert alerts[0]["camera"] == "CAM-TEST"
    assert alerts[0]["state"] == "alert"

def test_update_event_media():
    """Test updating media URLs on logged events."""
    event = {
        "id": "AL-33333",
        "timestamp": "2026-06-15T22:40:00",
        "state": "fallen",
        "confidence": 75
    }
    log_event(event)
    
    # Verify initial URLs are null
    events = get_events()
    test_event = next(e for e in events if e["id"] == "AL-33333")
    assert test_event["image_url"] is None
    assert test_event["video_url"] is None
    
    # Update URLs
    update_event_media("AL-33333", "http://r2.com/img.jpg", "http://r2.com/vid.mp4")
    
    # Verify updated URLs
    events = get_events()
    test_event = next(e for e in events if e["id"] == "AL-33333")
    assert test_event["image_url"] == "http://r2.com/img.jpg"
    assert test_event["video_url"] == "http://r2.com/vid.mp4"

def test_upload_media_fallback(tmp_path):
    """Test media upload fallback when Cloudinary is not configured."""
    # Create a dummy file
    dummy_file = tmp_path / "dummy.jpg"
    dummy_file.write_text("dummy content")
    
    # upload_media should return local url fallback /media/dummy.jpg
    url = upload_media(dummy_file, "dummy.jpg", "image/jpeg")
    assert url == "/media/dummy.jpg"

def test_upload_media_cloudinary(tmp_path):
    """Test media upload using Cloudinary when configuration is present."""
    dummy_file = tmp_path / "dummy.jpg"
    dummy_file.write_text("dummy content")
    
    config = {
        "turso": {"url": "", "auth_token": ""},
        "cloudinary": {
            "cloud_name": "test_cloud",
            "api_key": "test_key",
            "api_secret": "test_secret"
        }
    }
    
    with patch("src.core.database.load_db_config", return_value=config), \
         patch("cloudinary.uploader.upload") as mock_upload, \
         patch("cloudinary.config") as mock_config:
         
        mock_upload.return_value = {"secure_url": "https://res.cloudinary.com/test_cloud/image/upload/dummy.jpg"}
        
        url = upload_media(dummy_file, "dummy.jpg", "image/jpeg")
        
        # Verify Cloudinary uploader was called correctly
        mock_config.assert_called_once_with(
            cloud_name="test_cloud",
            api_key="test_key",
            api_secret="test_secret",
            secure=True
        )
        mock_upload.assert_called_once_with(
            str(dummy_file),
            public_id="dummy",
            resource_type="image",
            folder="fallguard"
        )
        assert url == "https://res.cloudinary.com/test_cloud/image/upload/dummy.jpg"

def test_kv_store():
    """Test saving and retrieving values in the key-value store."""
    test_dict = {"cameras": [{"id": "CAM-001", "name": "Cam 1"}], "settings": {"fps": 30}}
    save_kv("test_store", test_dict)
    
    # Retrieve and verify
    retrieved = get_kv("test_store")
    assert retrieved == test_dict
    
    # Verify non-existent key returns default
    assert get_kv("nonexistent_key", default="default_val") == "default_val"

def test_custom_user_verification(setup_test_db):
    """Test verification of custom users."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("customuser", "custompwd", "User"))
    conn.commit()
    
    assert verify_user("customuser", "custompwd") is True
    assert verify_user("customuser", "wrongpwd") is False






