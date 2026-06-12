from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.camera_registry import list_cameras_payload
from src.cloud_db import use_cloud_storage

DEFAULT_PATIENT_PROFILES_PATH = Path("data/patient_profiles.json")
PROFILE_FIELDS = (
    "full_name",
    "age_label",
    "room_label",
    "date_of_birth",
    "blood_type",
    "medical_conditions",
    "emergency_contact",
)

FALL_ALERT_STATES = frozenset({"alert", "fallen"})
WARNING_STATES = frozenset({"warning", "possible_fall"})


def _initials(full_name: str) -> str:
    parts = [part for part in full_name.replace("-", " ").split() if part]
    if not parts:
        return "HS"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[-1][0]}".upper()


def _account_full_name(username: str | None) -> str:
    if not username:
        return ""
    try:
        from src.auth import find_user

        user = find_user(username)
    except Exception:
        return username.strip()
    if user is None:
        return username.strip()
    return (user.full_name or user.username).strip()


def _default_patient(profile_key: str, username: str | None = None) -> dict[str, Any]:
    full_name = _account_full_name(username) or "Người được giám sát"
    return {
        "profile_key": profile_key,
        "full_name": full_name,
        "initials": _initials(full_name),
        "age_label": "Chưa nhập",
        "room_label": "Chưa nhập",
        "date_of_birth": "Chưa nhập",
        "blood_type": "Chưa nhập",
        "medical_conditions": "Chưa nhập",
        "emergency_contact": "Chưa nhập",
    }


def _normalize_patient(raw: dict[str, Any] | None, *, profile_key: str, username: str | None) -> dict[str, Any]:
    profile = _default_patient(profile_key, username)
    if raw:
        for field in PROFILE_FIELDS:
            value = str(raw.get(field, "") or "").strip()
            if value:
                profile[field] = value
        initials = str(raw.get("initials", "") or "").strip()
        profile["initials"] = initials or _initials(profile["full_name"])
    return profile


def _profile_path(path: Path | None = None) -> Path:
    return path if path is not None else DEFAULT_PATIENT_PROFILES_PATH


def _load_local_profiles(path: Path | None = None) -> dict[str, Any]:
    profile_path = _profile_path(path)
    if not profile_path.exists():
        return {"users": {}}
    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"users": {}}
    return data if isinstance(data, dict) else {"users": {}}


def _load_patient_from_local(
    username: str,
    *,
    profile_key: str,
    path: Path | None = None,
) -> dict[str, Any] | None:
    data = _load_local_profiles(path)
    users = data.get("users", {})
    if not isinstance(users, dict):
        return None
    raw = users.get(username.strip())
    return _normalize_patient(raw, profile_key=profile_key, username=username) if isinstance(raw, dict) else None


def _save_patient_to_local(
    username: str,
    profile: dict[str, Any],
    *,
    path: Path | None = None,
) -> None:
    profile_path = _profile_path(path)
    data = _load_local_profiles(profile_path)
    users = data.setdefault("users", {})
    if not isinstance(users, dict):
        users = {}
        data["users"] = users
    users[username.strip()] = {field: profile.get(field, "") for field in PROFILE_FIELDS}
    users[username.strip()]["initials"] = profile.get("initials", "")
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = profile_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(profile_path)


def _ensure_cloud_profile_table(conn: Any) -> None:
    from sqlalchemy import text

    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS user_patient_profiles (
              username            VARCHAR(64) PRIMARY KEY,
              full_name           VARCHAR(128) NOT NULL,
              initials            VARCHAR(8),
              age_label           VARCHAR(32),
              room_label          VARCHAR(64),
              date_of_birth       VARCHAR(32),
              blood_type          VARCHAR(16),
              medical_conditions  TEXT,
              emergency_contact   VARCHAR(128),
              updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    )


def _load_patient_from_cloud(
    username: str,
    *,
    profile_key: str,
) -> dict[str, Any] | None:
    from sqlalchemy import text

    from src.cloud_db import get_engine

    with get_engine().begin() as conn:
        _ensure_cloud_profile_table(conn)
        row = conn.execute(
            text(
                """
                SELECT full_name, initials, age_label, room_label,
                       date_of_birth, blood_type, medical_conditions, emergency_contact
                FROM user_patient_profiles
                WHERE username = :username
                """
            ),
            {"username": username.strip()},
        ).mappings().first()
    return _normalize_patient(dict(row), profile_key=profile_key, username=username) if row else None


def _save_patient_to_cloud(username: str, profile: dict[str, Any]) -> None:
    from sqlalchemy import text

    from src.cloud_db import get_engine

    values = {field: profile.get(field, "") for field in PROFILE_FIELDS}
    values["initials"] = profile.get("initials", "")
    values["username"] = username.strip()
    with get_engine().begin() as conn:
        _ensure_cloud_profile_table(conn)
        conn.execute(
            text(
                """
                INSERT INTO user_patient_profiles (
                  username, full_name, initials, age_label, room_label,
                  date_of_birth, blood_type, medical_conditions, emergency_contact
                ) VALUES (
                  :username, :full_name, :initials, :age_label, :room_label,
                  :date_of_birth, :blood_type, :medical_conditions, :emergency_contact
                )
                ON CONFLICT (username) DO UPDATE SET
                  full_name = EXCLUDED.full_name,
                  initials = EXCLUDED.initials,
                  age_label = EXCLUDED.age_label,
                  room_label = EXCLUDED.room_label,
                  date_of_birth = EXCLUDED.date_of_birth,
                  blood_type = EXCLUDED.blood_type,
                  medical_conditions = EXCLUDED.medical_conditions,
                  emergency_contact = EXCLUDED.emergency_contact,
                  updated_at = NOW()
                """
            ),
            values,
        )


def get_patient_profile(profile_key: str = "default", *, username: str | None = None) -> dict[str, Any]:
    if not username:
        return _default_patient(profile_key)

    if use_cloud_storage():
        cloud_patient = _load_patient_from_cloud(username, profile_key=profile_key)
        if cloud_patient:
            return cloud_patient
    else:
        local_patient = _load_patient_from_local(username, profile_key=profile_key)
        if local_patient:
            return local_patient

    return _default_patient(profile_key, username)


def update_patient_profile(
    username: str,
    updates: dict[str, Any],
    *,
    profile_key: str = "default",
) -> dict[str, Any]:
    target = username.strip()
    if not target:
        raise ValueError("Chua dang nhap.")

    current = get_patient_profile(profile_key, username=target)
    merged = dict(current)
    for field in PROFILE_FIELDS:
        if field in updates:
            merged[field] = str(updates.get(field, "") or "").strip()
    merged = _normalize_patient(merged, profile_key=profile_key, username=target)

    if use_cloud_storage():
        _save_patient_to_cloud(target, merged)
    else:
        _save_patient_to_local(target, merged)
    return merged


def _fetch_events_for_stats(profile_key: str, days: int = 30) -> list[dict[str, Any]]:
    if not use_cloud_storage():
        return []
    from sqlalchemy import text

    from src.cloud_db import get_engine

    since = datetime.now(timezone.utc) - timedelta(days=days)
    with get_engine().connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT state, timestamp
                FROM fall_events
                WHERE timestamp >= :since
                  AND (profile = :profile OR profile IS NULL OR profile = '')
                ORDER BY timestamp DESC
                """
            ),
            {"since": since, "profile": profile_key},
        ).mappings().all()
    return [dict(row) for row in rows]


def _compute_stats(events: list[dict[str, Any]]) -> dict[str, Any]:
    falls_30 = sum(1 for event in events if str(event.get("state", "")).lower() in FALL_ALERT_STATES)
    warnings = sum(1 for event in events if str(event.get("state", "")).lower() in WARNING_STATES)
    normal_count = sum(1 for event in events if str(event.get("state", "")).lower() == "normal")

    if not events:
        mobility_score = 85
        active_hours_avg = 6.2
    else:
        mobility_score = max(40, min(100, 100 - falls_30 * 25 - warnings * 5))
        active_hours_avg = round(max(0.5, (normal_count * 2.0) / 30.0), 1)

    return {
        "falls_30_days": falls_30,
        "mobility_score": mobility_score,
        "active_hours_avg": active_hours_avg,
        "events_tracked": len(events),
    }


def get_patient_profile_dashboard(
    profile_key: str = "default",
    *,
    username: str | None = None,
    is_admin: bool = False,
) -> dict[str, Any]:
    profile = get_patient_profile(profile_key, username=username)
    storage = "database" if use_cloud_storage() else "yaml"
    events = _fetch_events_for_stats(profile_key)
    stats = _compute_stats(events)
    cameras = list_cameras_payload(username=username, is_admin=is_admin)

    return {
        "profile": profile,
        "stats": stats,
        "cameras": cameras,
        "storage": storage,
    }
