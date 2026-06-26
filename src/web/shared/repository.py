"""Repository layer for shared domain (Alerts, AppState, UserRoles)."""

from __future__ import annotations

import json
from typing import Any
from src.web.shared.db import get_db_client


def get_user_role_db(email: str) -> str:
    try:
        with get_db_client() as client:
            res = client.execute("SELECT role FROM users WHERE email = ?", [email])
            if res.rows:
                return res.rows[0][0]
    except Exception as e:
        print(f"[Database Error] Khong the doc user role: {e}")
    return "Khachhang"


def get_alerts_db() -> list[dict[str, Any]]:
    alerts_list = []
    with get_db_client() as client:
        res = client.execute(
            "SELECT id, time, camera, person, confidence, status, level, media, state, "
            "cloud_img_url, cloud_video_url, deleted_by_users FROM alerts ORDER BY id DESC LIMIT 100"
        )
        for r in res.rows:
            alerts_list.append({
                "id": r[0],
                "time": r[1],
                "camera": r[2],
                "person": r[3],
                "confidence": r[4],
                "status": r[5],
                "level": r[6],
                "media": r[7],
                "state": r[8],
                "cloud_img_url": r[9],
                "cloud_video_url": r[10],
                "deleted_by_users": r[11]
            })
    return alerts_list


def get_alert_by_id_db(alert_id: str) -> dict[str, Any] | None:
    with get_db_client() as client:
        res = client.execute(
            "SELECT id, cloud_img_url, cloud_video_url, deleted_by_users FROM alerts WHERE id = ?",
            [alert_id]
        )
        if res.rows:
            r = res.rows[0]
            return {
                "id": r[0],
                "cloud_img_url": r[1],
                "cloud_video_url": r[2],
                "deleted_by_users": r[3]
            }
    return None


def soft_delete_alert_db(alert_id: str, deleted_by_users_json: str) -> None:
    with get_db_client() as client:
        client.execute(
            "UPDATE alerts SET deleted_by_users = ? WHERE id = ?",
            [deleted_by_users_json, alert_id]
        )


def hard_delete_alert_db(alert_id: str) -> None:
    with get_db_client() as client:
        client.execute("DELETE FROM alerts WHERE id = ?", [alert_id])


def solve_alert_db(alert_id: str) -> None:
    with get_db_client() as client:
        client.execute("UPDATE alerts SET status = 'Đã xử lý' WHERE id = ?", [alert_id])


def get_app_state_db(email: str = "global") -> dict[str, str]:
    with get_db_client() as client:
        client.execute("""
            CREATE TABLE IF NOT EXISTS app_state (
                id TEXT PRIMARY KEY,
                api_keys_json TEXT NOT NULL DEFAULT '[]',
                settings_json TEXT NOT NULL DEFAULT '{}',
                monitored_profile_json TEXT NOT NULL DEFAULT '{}',
                emergency_contacts_json TEXT NOT NULL DEFAULT '[]',
                user_notifications_json TEXT NOT NULL DEFAULT '[]'
            )
        """)
        res = client.execute(
            "SELECT api_keys_json, settings_json, monitored_profile_json, emergency_contacts_json, "
            "user_notifications_json FROM app_state WHERE id = ?",
            [email]
        )
        if not res.rows:
            client.execute("INSERT INTO app_state (id) VALUES (?)", [email])
            return {
                "api_keys_json": "[]",
                "settings_json": "{}",
                "monitored_profile_json": "{}",
                "emergency_contacts_json": "[]",
                "user_notifications_json": "[]"
            }
        r = res.rows[0]
        return {
            "api_keys_json": r[0],
            "settings_json": r[1],
            "monitored_profile_json": r[2],
            "emergency_contacts_json": r[3],
            "user_notifications_json": r[4]
        }


def update_app_state_db(updates: list[str], params: list[Any]) -> None:
    with get_db_client() as client:
        query = f"UPDATE app_state SET {', '.join(updates)} WHERE id = ?"
        client.execute(query, params)


def get_user_assigned_cameras_db(email: str) -> list[str]:
    with get_db_client() as client:
        res = client.execute("SELECT assigned_cameras FROM users WHERE email = ?", [email])
        if res.rows and res.rows[0][0]:
            try:
                return json.loads(res.rows[0][0])
            except Exception:
                pass
    return []


def get_all_alert_ids_db() -> list[str]:
    with get_db_client() as client:
        res = client.execute("SELECT id FROM alerts")
        return [r[0] for r in res.rows]


def get_alert_ids_by_cameras_db(cameras: list[str]) -> list[str]:
    if not cameras:
        return []
    with get_db_client() as client:
        placeholders = ", ".join("?" for _ in cameras)
        res = client.execute(f"SELECT id FROM alerts WHERE camera IN ({placeholders})", cameras)
        return [r[0] for r in res.rows]
