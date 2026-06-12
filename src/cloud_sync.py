from __future__ import annotations

from typing import Any

from src.cloud_db import get_engine, use_cloud_storage

EVENT_COLUMNS = [
    "timestamp",
    "source",
    "state",
    "torso_angle_deg",
    "head_hip_delta",
    "hip_velocity",
    "angle_velocity_deg",
    "abnormal_frames",
    "lying_seconds",
    "fps",
    "profile",
    "fall_like_transition",
]


def _float_or_none(value: str | float | int | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _int_or_none(value: str | int | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def sync_fall_event(row: dict[str, Any]) -> None:
    if not use_cloud_storage():
        return
    from sqlalchemy import text

    with get_engine().begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO fall_events (
                    timestamp, source, state, torso_angle_deg, head_hip_delta,
                    hip_velocity, angle_velocity_deg, abnormal_frames, lying_seconds,
                    fps, profile, fall_like_transition
                ) VALUES (
                    :timestamp, :source, :state, :torso_angle_deg, :head_hip_delta,
                    :hip_velocity, :angle_velocity_deg, :abnormal_frames, :lying_seconds,
                    :fps, :profile, :fall_like_transition
                )
                """
            ),
            {
                "timestamp": row.get("timestamp"),
                "source": str(row.get("source", "")) or None,
                "state": row.get("state"),
                "torso_angle_deg": _float_or_none(row.get("torso_angle_deg")),
                "head_hip_delta": _float_or_none(row.get("head_hip_delta")),
                "hip_velocity": _float_or_none(row.get("hip_velocity")),
                "angle_velocity_deg": _float_or_none(row.get("angle_velocity_deg")),
                "abnormal_frames": _int_or_none(row.get("abnormal_frames")),
                "lying_seconds": _float_or_none(row.get("lying_seconds")),
                "fps": _float_or_none(row.get("fps")),
                "profile": row.get("profile") or None,
                "fall_like_transition": bool(int(row.get("fall_like_transition") or 0)),
            },
        )


def read_fall_events_recent(limit: int = 20) -> list[dict[str, str]]:
    if not use_cloud_storage():
        return []
    from sqlalchemy import text

    safe_limit = max(1, min(limit, 100))
    with get_engine().connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT timestamp, source, state, torso_angle_deg, head_hip_delta,
                       hip_velocity, angle_velocity_deg, abnormal_frames, lying_seconds,
                       fps, profile, fall_like_transition
                FROM fall_events
                ORDER BY timestamp DESC
                LIMIT :limit
                """
            ),
            {"limit": safe_limit},
        ).mappings().all()

    events: list[dict[str, str]] = []
    for row in rows:
        events.append(
            {
                "timestamp": str(row["timestamp"]),
                "source": str(row["source"] or ""),
                "state": str(row["state"]),
                "torso_angle_deg": f"{float(row['torso_angle_deg'] or 0):.2f}",
                "head_hip_delta": f"{float(row['head_hip_delta'] or 0):.4f}",
                "hip_velocity": f"{float(row['hip_velocity'] or 0):.4f}",
                "angle_velocity_deg": f"{float(row['angle_velocity_deg'] or 0):.2f}",
                "abnormal_frames": str(row["abnormal_frames"] or 0),
                "lying_seconds": f"{float(row['lying_seconds'] or 0):.2f}",
                "fps": "" if row["fps"] is None else f"{float(row['fps']):.2f}",
                "profile": str(row["profile"] or ""),
                "fall_like_transition": str(int(bool(row["fall_like_transition"]))),
            }
        )
    return list(reversed(events))


def list_access_requests_cloud(*, status: str | None = None) -> list[dict[str, Any]]:
    from sqlalchemy import text

    query = """
        SELECT id::text, full_name, email, phone, role, message, status,
               created_at, reviewed_at, review_note
        FROM access_requests
    """
    params: dict[str, Any] = {}
    if status:
        query += " WHERE status = :status"
        params["status"] = status.strip().lower()
    query += " ORDER BY created_at DESC"

    with get_engine().connect() as conn:
        rows = conn.execute(text(query), params).mappings().all()
    return [dict(row) for row in rows]


def create_access_request_cloud(
    *,
    full_name: str,
    email: str,
    phone: str,
    role: str,
    message: str,
) -> dict[str, Any]:
    from sqlalchemy import text

    with get_engine().begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO access_requests (full_name, email, phone, role, message, status)
                VALUES (:full_name, :email, :phone, :role, :message, 'pending')
                RETURNING id::text, full_name, email, phone, role, message, status,
                          created_at, reviewed_at, review_note
                """
            ),
            {
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "role": role,
                "message": message,
            },
        ).mappings().one()
    return dict(row)


def sync_camera_assignments(camera_id: str, usernames: list[str]) -> None:
    if not use_cloud_storage():
        return
    from sqlalchemy import text

    with get_engine().begin() as conn:
        conn.execute(
            text("DELETE FROM camera_assignments WHERE camera_id = :camera_id"),
            {"camera_id": camera_id},
        )
        for username in usernames:
            name = username.strip()
            if not name:
                continue
            conn.execute(
                text(
                    """
                    INSERT INTO camera_assignments (camera_id, username)
                    VALUES (:camera_id, :username)
                    ON CONFLICT (camera_id, username) DO NOTHING
                    """
                ),
                {"camera_id": camera_id, "username": name},
            )


def delete_camera_assignments(camera_id: str) -> None:
    if not use_cloud_storage():
        return
    from sqlalchemy import text

    with get_engine().begin() as conn:
        conn.execute(
            text("DELETE FROM camera_assignments WHERE camera_id = :camera_id"),
            {"camera_id": camera_id},
        )


def update_access_request_cloud(
    request_id: str,
    *,
    status: str,
    review_note: str = "",
) -> dict[str, Any]:
    from sqlalchemy import text

    with get_engine().begin() as conn:
        row = conn.execute(
            text(
                """
                UPDATE access_requests
                SET status = :status,
                    reviewed_at = NOW(),
                    review_note = :review_note
                WHERE id::text = :request_id
                RETURNING id::text, full_name, email, phone, role, message, status,
                          created_at, reviewed_at, review_note
                """
            ),
            {
                "request_id": request_id,
                "status": status,
                "review_note": review_note or None,
            },
        ).mappings().first()
    if row is None:
        raise ValueError("Khong tim thay yeu cau.")
    return dict(row)
