"""Repository layer for admin domain (Users, Cameras, Logs)."""

from __future__ import annotations

import json
from typing import Any
from src.web.shared.db import get_db_client


def get_all_users_db() -> list[dict[str, Any]]:
    users_list = []
    with get_db_client() as client:
        res = client.execute("SELECT email, name, role, status, assigned_cameras, phone, password, age, gender, address FROM users")
        for r in res.rows:
            assigned = []
            if r[4]:
                try:
                    assigned = json.loads(r[4])
                except Exception:
                    assigned = []
            users_list.append({
                "email": r[0],
                "name": r[1],
                "role": r[2],
                "status": r[3],
                "assignedCameras": assigned,
                "phone": r[5] if len(r) > 5 else None,
                "password": r[6] if len(r) > 6 else None,
                "age": r[7] if len(r) > 7 else None,
                "gender": r[8] if len(r) > 8 else None,
                "address": r[9] if len(r) > 9 else None
            })
    return users_list


def create_user_db(email: str, password: str | None, name: str, role: str, status: str, assigned_cameras_json: str, phone: str | None, age: int | None = None, gender: str | None = None, address: str | None = None) -> None:
    with get_db_client() as client:
        client.execute(
            "INSERT INTO users (email, password, name, role, status, assigned_cameras, phone, age, gender, address) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [email, password or "nckh2025", name, role, status, assigned_cameras_json, phone, age, gender, address]
        )


def check_user_exists_db(email: str) -> bool:
    with get_db_client() as client:
        res = client.execute("SELECT 1 FROM users WHERE email = ?", [email])
        return len(res.rows) > 0


def update_user_db(email: str, password: str | None, name: str, role: str, status: str, assigned_cameras_json: str, phone: str | None, old_email: str, age: int | None = None, gender: str | None = None, address: str | None = None) -> None:
    with get_db_client() as client:
        if password:
            client.execute(
                "UPDATE users SET email = ?, name = ?, role = ?, status = ?, assigned_cameras = ?, password = ?, phone = ?, age = ?, gender = ?, address = ? WHERE email = ?",
                [email, name, role, status, assigned_cameras_json, password, phone, age, gender, address, old_email]
            )
        else:
            client.execute(
                "UPDATE users SET email = ?, name = ?, role = ?, status = ?, assigned_cameras = ?, phone = ?, age = ?, gender = ?, address = ? WHERE email = ?",
                [email, name, role, status, assigned_cameras_json, phone, age, gender, address, old_email]
            )


def delete_user_db(email: str) -> None:
    with get_db_client() as client:
        client.execute("DELETE FROM users WHERE email = ?", [email])


def get_all_cameras_db() -> list[dict[str, Any]]:
    cams = []
    with get_db_client() as client:
        res = client.execute("SELECT id, name, ip, rtsp, area, target, state, status, fps, resolution, threshold FROM cameras")
        for r in res.rows:
            cams.append({
                "id": r[0],
                "name": r[1],
                "ip": r[2],
                "rtsp": r[3],
                "area": r[4],
                "target": r[5],
                "state": r[6],
                "status": r[7],
                "fps": r[8],
                "resolution": r[9],
                "threshold": r[10]
            })
    return cams


def create_camera_db(id: str, name: str, ip: str, rtsp: str, area: str, target: str, state: str, status: str, fps: int, resolution: str, threshold: int) -> None:
    with get_db_client() as client:
        client.execute(
            "INSERT INTO cameras (id, name, ip, rtsp, area, target, state, status, fps, resolution, threshold) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [id, name, ip, rtsp, area, target, state, status, fps, resolution, threshold]
        )


def check_camera_exists_db(id: str) -> bool:
    with get_db_client() as client:
        res = client.execute("SELECT 1 FROM cameras WHERE id = ?", [id])
        return len(res.rows) > 0


def update_camera_db(id: str, name: str, ip: str, rtsp: str, area: str, target: str, state: str, status: str, fps: int, resolution: str, threshold: int, old_id: str) -> None:
    with get_db_client() as client:
        client.execute(
            "UPDATE cameras SET id = ?, name = ?, ip = ?, rtsp = ?, area = ?, target = ?, state = ?, status = ?, fps = ?, resolution = ?, threshold = ? WHERE id = ?",
            [id, name, ip, rtsp, area, target, state, status, fps, resolution, threshold, old_id]
        )


def delete_camera_db(id: str) -> None:
    with get_db_client() as client:
        client.execute("DELETE FROM cameras WHERE id = ?", [id])


def get_logs_db() -> list[list[str]]:
    with get_db_client() as client:
        client.execute("""
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT,
                type TEXT,
                user TEXT,
                content TEXT
            )
        """)
        res = client.execute("SELECT time, type, user, content FROM system_logs ORDER BY id DESC LIMIT 50")
        return [[r[0], r[1], r[2], r[3]] for r in res.rows]
