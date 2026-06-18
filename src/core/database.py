"""Database manager module: integrates Turso (libSQL) and Cloudflare R2 (S3-compatible) with SQLite/local fallbacks."""

from __future__ import annotations

import os
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Default config paths
DB_CONFIG_PATH = Path("configs/db.json")
LOCAL_DB_PATH = Path("data/fallguard.db")
LOCAL_MEDIA_DIR = Path("data/media")

# Globals to store connections
_db_conn = None

def load_db_config() -> dict[str, Any]:
    """Loads Turso database and Cloudinary configuration from configs/db.json or environment variables."""
    config = {
        "turso": {"url": "", "auth_token": ""},
        "cloudinary": {"cloud_name": "", "api_key": "", "api_secret": ""}
    }
    
    # 1. Load from file if exists
    if DB_CONFIG_PATH.exists():
        try:
            with DB_CONFIG_PATH.open(encoding="utf-8") as f:
                file_config = json.load(f)
                if "turso" in file_config:
                    config["turso"].update(file_config["turso"])
                if "cloudinary" in file_config:
                    config["cloudinary"].update(file_config["cloudinary"])
        except Exception as e:
            print(f"[Database] Error reading configs/db.json: {e}")
            
    # 2. Override with environment variables if present
    # Turso env
    turso_url = os.getenv("TURSO_DATABASE_URL") or os.getenv("TURSO_URL")
    turso_token = os.getenv("TURSO_AUTH_TOKEN") or os.getenv("TURSO_TOKEN")
    if turso_url:
        config["turso"]["url"] = turso_url
    if turso_token:
        config["turso"]["auth_token"] = turso_token
        
    # Cloudinary env
    c_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    c_key = os.getenv("CLOUDINARY_API_KEY")
    c_secret = os.getenv("CLOUDINARY_API_SECRET")
    if c_name:
        config["cloudinary"]["cloud_name"] = c_name
    if c_key:
        config["cloudinary"]["api_key"] = c_key
    if c_secret:
        config["cloudinary"]["api_secret"] = c_secret
        
    return config

def get_db_connection():
    """Initializes and returns a database connection (Turso or local SQLite)."""
    global _db_conn
    if _db_conn is not None:
        return _db_conn
        
    config = load_db_config()
    turso_url = config["turso"].get("url", "").strip()
    turso_token = config["turso"].get("auth_token", "").strip()
    
    # Check if we should use Turso or local SQLite
    if turso_url and (turso_url.startswith("libsql://") or turso_url.startswith("https://")):
        try:
            import libsql
            print(f"[Database] Connecting to Turso database: {turso_url}")
            _db_conn = libsql.connect(turso_url, auth_token=turso_token)
            print("[Database] Successfully connected to Turso cloud database.")
        except Exception as e:
            print(f"[Database Error] Could not connect to Turso: {e}. Falling back to local SQLite.")
            _db_conn = None
            
    if _db_conn is None:
        # Local SQLite fallback
        LOCAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        print(f"[Database] Connecting to local SQLite database: {LOCAL_DB_PATH}")
        # Use sqlite3.connect. Note: libsql also provides sqlite3-like interface
        _db_conn = sqlite3.connect(str(LOCAL_DB_PATH), check_same_thread=False)
        # Enable row factory for dict-like rows
        _db_conn.row_factory = sqlite3.Row
        print("[Database] Local SQLite database connected.")
        
    init_db_schema(_db_conn)
    return _db_conn

def init_db_schema(conn):
    """Creates the tables if they do not exist."""
    cursor = conn.cursor()
    
    # 1. users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'User'
    )
    """)
    
    # Seed default users if empty
    cursor.execute("SELECT COUNT(*) as count FROM users")
    row = cursor.fetchone()
    count = row[0] if row else 0
    if count == 0:
        default_users = [
            ("admin", "nckh2025", "Admin"),
            ("manager", "nckh2025", "Quản lý"),
            ("nurse", "nckh2025", "Điều dưỡng"),
            ("family", "nckh2025", "Người nhà"),
            ("guest", "nckh2025", "Khách")
        ]
        for username, password, role in default_users:
            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, password, role)
            )
        conn.commit()
        print("[Database] Seeded default users.")
        
    # 2. sessions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        username TEXT NOT NULL,
        expires_at REAL NOT NULL
    )
    """)
    
    # 3. events (alerts) table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        state TEXT NOT NULL,
        torso_angle_deg REAL,
        head_hip_delta REAL,
        hip_velocity REAL,
        angle_velocity_deg REAL,
        abnormal_frames INTEGER,
        lying_seconds REAL,
        profile TEXT,
        fall_like_transition INTEGER,
        camera_id TEXT,
        person_id TEXT,
        confidence INTEGER,
        status TEXT,
        level TEXT,
        image_url TEXT,
        video_url TEXT
    )
    """)
    
    # 4. kv_store table for frontend dashboard persistence
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS kv_store (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)
    
    conn.commit()

def save_kv(key: str, value: Any) -> None:
    """Saves a key-value pair as JSON in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    json_str = json.dumps(value, ensure_ascii=False)
    cursor.execute(
        "INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
        (key, json_str)
    )
    conn.commit()

def get_kv(key: str, default: Any = None) -> Any:
    """Retrieves and parses a key-value JSON string from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM kv_store WHERE key = ?", (key,))
    row = cursor.fetchone()
    if row:
        val_str = row[0] if isinstance(row, tuple) else row["value"]
        try:
            return json.loads(val_str)
        except Exception:
            return default
    return default


# --- Database User & Session Operations ---

def verify_user(username: str, password_plain: str) -> bool:
    """Verifies a user's password."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE username = ?", (username.strip().lower(),))
    row = cursor.fetchone()
    if row:
        # Simple plain password comparison to match original behavior
        db_pwd = row[0] if isinstance(row, tuple) else row["password"]
        return db_pwd == password_plain
    return False

def create_session(username: str, ttl_seconds: int = 12 * 60 * 60) -> str:
    """Creates a login session token."""
    import secrets
    token = secrets.token_urlsafe(32)
    expires_at = time.time() + ttl_seconds
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sessions (token, username, expires_at) VALUES (?, ?, ?)",
        (token, username, expires_at)
    )
    conn.commit()
    return token

def verify_session_token(token: str | None) -> str | None:
    """Verifies a session token, returning the username if valid."""
    if not token:
        return None
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, expires_at FROM sessions WHERE token = ?", (token,))
    row = cursor.fetchone()
    if not row:
        return None
        
    username = row[0] if isinstance(row, tuple) else row["username"]
    expires_at = row[1] if isinstance(row, tuple) else row["expires_at"]
    
    if expires_at < time.time():
        # Session expired, clean up
        cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        return None
        
    return username

def delete_session(token: str | None) -> None:
    """Deletes a session token (logout)."""
    if not token:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()

# --- Database Event Logging Operations ---

def log_event(e: dict[str, Any]) -> None:
    """Logs an event into the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Standard schema mapping
    cursor.execute(
        """
        INSERT OR REPLACE INTO events (
            id, timestamp, state, torso_angle_deg, head_hip_delta,
            hip_velocity, angle_velocity_deg, abnormal_frames, lying_seconds,
            profile, fall_like_transition, camera_id, person_id, confidence,
            status, level, image_url, video_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            e.get("id"),
            e.get("timestamp"),
            e.get("state"),
            e.get("torso_angle_deg"),
            e.get("head_hip_delta"),
            e.get("hip_velocity"),
            e.get("angle_velocity_deg"),
            e.get("abnormal_frames"),
            e.get("lying_seconds"),
            e.get("profile"),
            e.get("fall_like_transition"),
            e.get("camera_id", "CAM-LOCAL"),
            e.get("person_id", "BN-LOCAL"),
            e.get("confidence", 18),
            e.get("status", "Chưa xử lý"),
            e.get("level", "Cảnh báo"),
            e.get("image_url"),
            e.get("video_url")
        )
    )
    conn.commit()

def update_event_media(event_id: str, image_url: str | None = None, video_url: str | None = None) -> None:
    """Updates media URLs for a specific event."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if image_url and video_url:
        cursor.execute("UPDATE events SET image_url = ?, video_url = ? WHERE id = ?", (image_url, video_url, event_id))
    elif image_url:
        cursor.execute("UPDATE events SET image_url = ? WHERE id = ?", (image_url, event_id))
    elif video_url:
        cursor.execute("UPDATE events SET video_url = ? WHERE id = ?", (video_url, event_id))
        
    conn.commit()

def get_events(limit: int = 100) -> list[dict[str, Any]]:
    """Retrieves all logged events from database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    
    events = []
    for row in rows:
        # Handle tuple vs row object (libsql client returns custom rows, sqlite3 returns Row/tuples)
        if hasattr(row, "keys"):
            events.append(dict(row))
        elif isinstance(row, dict):
            events.append(row)
        else:
            # Fallback for raw tuple parsing
            desc = cursor.description
            col_names = [d[0] for d in desc]
            events.append(dict(zip(col_names, row)))
            
    return events

def get_recent_alerts(limit: int = 50) -> list[dict[str, Any]]:
    """Retrieves only alert/fallen events formatted for dashboard consumption."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Fetch events in 'alert' or 'fallen' states
    cursor.execute(
        "SELECT * FROM events WHERE state IN ('alert', 'fallen') ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    
    alerts = []
    for row in rows:
        d = {}
        if hasattr(row, "keys"):
            d = dict(row)
        elif isinstance(row, dict):
            d = row
        else:
            desc = cursor.description
            col_names = [d[0] for d in desc]
            d = dict(zip(col_names, row))
            
        # Reformat to match the frontend expected structure:
        # {
        #   "id": "AL-1718451234",
        #   "time": "15/06/2026 22:30",
        #   "camera": "CAM-LOCAL",
        #   "person": "BN-LOCAL",
        #   "confidence": 85,
        #   "status": "Chưa xử lý",
        #   "level": "Khẩn cấp",
        #   "media": "AL-1718451234",
        #   "state": "fallen",
        #   "image_url": "...",
        #   "video_url": "..."
        # }
        try:
            dt = datetime.fromisoformat(d["timestamp"])
            time_str = dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            time_str = d["timestamp"]
            
        alerts.append({
            "id": d["id"],
            "time": time_str,
            "camera": d["camera_id"] or "CAM-LOCAL",
            "person": d["person_id"] or "BN-LOCAL",
            "confidence": d["confidence"] or 18,
            "status": d["status"] or "Chưa xử lý",
            "level": d["level"] or "Khẩn cấp",
            "media": d["id"], # used by UI to construct local path if no url
            "state": d["state"],
            "image_url": d["image_url"],
            "video_url": d["video_url"]
        })
        
    return alerts

# --- Backblaze B2 / S3 Upload Operations ---

# --- Local Media Upload Fallback ---

def upload_media(local_file_path: str | Path, file_name: str, content_type: str = "image/jpeg") -> str:
    """Uploads the local file to Cloudinary if configured; otherwise falls back to local storage URL."""
    config = load_db_config()
    c_cfg = config.get("cloudinary", {})
    c_name = c_cfg.get("cloud_name", "").strip()
    c_key = c_cfg.get("api_key", "").strip()
    c_secret = c_cfg.get("api_secret", "").strip()
    
    local_fallback_url = f"/media/{file_name}"
    
    if not (c_name and c_key and c_secret):
        print("[Database] Cloudinary is not configured. Using local filesystem fallback.")
        return local_fallback_url
        
    try:
        import cloudinary
        import cloudinary.uploader
        
        # Configure Cloudinary
        cloudinary.config(
            cloud_name=c_name,
            api_key=c_key,
            api_secret=c_secret,
            secure=True
        )
        
        # Determine resource type (image or video)
        resource_type = "image"
        if content_type.startswith("video/") or file_name.endswith(".mp4"):
            resource_type = "video"
            
        print(f"[Database] Uploading {file_name} to Cloudinary (resource_type={resource_type})...")
        
        # Upload using Cloudinary SDK
        public_id = Path(file_name).stem
        
        res = cloudinary.uploader.upload(
            str(local_file_path),
            public_id=public_id,
            resource_type=resource_type,
            folder="fallguard"
        )
        
        secure_url = res.get("secure_url")
        if secure_url:
            print(f"[Database] Successfully uploaded to Cloudinary: {secure_url}")
            return secure_url
        else:
            print("[Database Warning] Cloudinary upload completed but secure_url was not found in response. Falling back to local URL.")
            return local_fallback_url
            
    except Exception as e:
        print(f"[Database Error] Cloudinary upload failed: {e}. Falling back to local URL.")
        return local_fallback_url


