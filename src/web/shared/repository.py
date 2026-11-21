"""
File: src/web/shared/repository.py
Chức năng chính: Chứa các câu lệnh SQL dùng chung (Ví dụ: truy vấn Cảnh báo, Cài đặt).
"""


from __future__ import annotations

import json
from typing import Any
from src.web.shared.db import get_db_client


def get_user_role_db(email: str) -> str:
    """SQL SELECT: Trả về quyền (Role) của người dùng (Admin hoặc Khachhang)."""
    try:
        with get_db_client() as client:
            res = client.execute("SELECT role FROM users WHERE email = ?", [email])
            if res.rows:
                return res.rows[0][0]
    except Exception as e:
        print(f"[Database Error] Khong the doc user role: {e}")
    return "Khachhang"


def get_alerts_db() -> list[dict[str, Any]]:
    """SQL SELECT: Lấy danh sách sự kiện té ngã."""
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
    """SQL SELECT: Tìm thông tin chi tiết 1 cảnh báo theo ID."""
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


def batch_soft_delete_alerts_db(user: str, alert_ids: list[str] | None = None, cameras: list[str] | None = None) -> None:
    """SQL UPDATE BATCH: Ẩn hàng loạt cảnh báo đối với User trong 1 truy vấn duy nhất."""
    if not alert_ids and not cameras:
        return
    user_json = json.dumps([user])
    user_tag = f',"{user}"]'
    user_find = f'"{user}"'

    with get_db_client() as client:
        if alert_ids:
            chunk_size = 400
            for i in range(0, len(alert_ids), chunk_size):
                chunk = alert_ids[i:i + chunk_size]
                placeholders = ", ".join("?" for _ in chunk)
                sql = f"""
                    UPDATE alerts 
                    SET deleted_by_users = CASE 
                        WHEN deleted_by_users IS NULL OR deleted_by_users = '' OR deleted_by_users = '[]' THEN ?
                        WHEN INSTR(deleted_by_users, ?) = 0 THEN REPLACE(deleted_by_users, ']', ?)
                        ELSE deleted_by_users
                    END
                    WHERE id IN ({placeholders})
                """
                params = [user_json, user_find, user_tag] + chunk
                client.execute(sql, params)
        elif cameras:
            placeholders = ", ".join("?" for _ in cameras)
            sql = f"""
                UPDATE alerts 
                SET deleted_by_users = CASE 
                    WHEN deleted_by_users IS NULL OR deleted_by_users = '' OR deleted_by_users = '[]' THEN ?
                    WHEN INSTR(deleted_by_users, ?) = 0 THEN REPLACE(deleted_by_users, ']', ?)
                    ELSE deleted_by_users
                END
                WHERE camera IN ({placeholders})
            """
            params = [user_json, user_find, user_tag] + cameras
            client.execute(sql, params)


def hard_delete_alert_db(alert_id: str) -> None:
    """SQL DELETE: Xóa vĩnh viễn cảnh báo khỏi DB (Dành cho Admin)."""
    with get_db_client() as client:
        client.execute("DELETE FROM alerts WHERE id = ?", [alert_id])


def batch_hard_delete_alerts_db(alert_ids: list[str]) -> None:
    """SQL DELETE BATCH: Xóa hàng loạt cảnh báo trong 1 câu truy vấn."""
    if not alert_ids:
        return
    chunk_size = 400
    with get_db_client() as client:
        for i in range(0, len(alert_ids), chunk_size):
            chunk = alert_ids[i:i + chunk_size]
            placeholders = ", ".join("?" for _ in chunk)
            client.execute(f"DELETE FROM alerts WHERE id IN ({placeholders})", chunk)


def hard_delete_all_alerts_db() -> None:
    """SQL DELETE ALL: Xóa sạch toàn bộ cảnh báo trong DB (Admin)."""
    with get_db_client() as client:
        client.execute("DELETE FROM alerts")


def batch_get_alert_media_urls_db(alert_ids: list[str] | None = None) -> list[str]:
    """SQL SELECT: Lấy danh sách URL Cloudinary của các cảnh báo cần xóa."""
    urls = []
    with get_db_client() as client:
        if alert_ids is None:
            res = client.execute("SELECT cloud_img_url, cloud_video_url FROM alerts WHERE cloud_img_url IS NOT NULL OR cloud_video_url IS NOT NULL")
            for r in res.rows:
                if r[0]: urls.append(r[0])
                if r[1]: urls.append(r[1])
        elif alert_ids:
            chunk_size = 400
            for i in range(0, len(alert_ids), chunk_size):
                chunk = alert_ids[i:i + chunk_size]
                placeholders = ", ".join("?" for _ in chunk)
                res = client.execute(
                    f"SELECT cloud_img_url, cloud_video_url FROM alerts WHERE id IN ({placeholders})",
                    chunk
                )
                for r in res.rows:
                    if r[0]: urls.append(r[0])
                    if r[1]: urls.append(r[1])
    return urls


def solve_alert_db(alert_id: str) -> None:
    """SQL UPDATE: Đánh dấu trạng thái cảnh báo là "Đã xử lý"."""
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
    """SQL UPDATE: Cập nhật cài đặt hệ thống."""
    with get_db_client() as client:
        query = f"UPDATE app_state SET {', '.join(updates)} WHERE id = ?"
        client.execute(query, params)


def get_user_app_state_db(email: str) -> dict[str, str]:
    """SQL SELECT: Lấy cài đặt cá nhân của User."""
    with get_db_client() as client:
        res = client.execute(
            "SELECT monitored_profile_json, emergency_contacts_json, user_notifications_json "
            "FROM users WHERE email = ?", [email]
        )
        if res.rows:
            r = res.rows[0]
            return {
                "monitored_profile_json": r[0] or "{}",
                "emergency_contacts_json": r[1] or "[]",
                "user_notifications_json": r[2] or "[]"
            }
    return {
        "monitored_profile_json": "{}",
        "emergency_contacts_json": "[]",
        "user_notifications_json": "[]"
    }


def update_user_app_state_db(email: str, updates: list[str], params: list[Any]) -> None:
    """SQL UPDATE: Cập nhật cài đặt cá nhân của User."""
    with get_db_client() as client:
        query = f"UPDATE users SET {', '.join(updates)} WHERE email = ?"
        client.execute(query, params + [email])



def get_user_assigned_cameras_db(email: str) -> list[str]:
    """SQL SELECT: Trả về danh sách ID Camera mà user này được phép xem."""
    with get_db_client() as client:
        res = client.execute("SELECT assigned_cameras FROM users WHERE email = ?", [email])
        if res.rows and res.rows[0][0]:
            try:
                return json.loads(res.rows[0][0])
            except Exception:
                pass
    return []


def get_all_alert_ids_db() -> list[str]:
    """SQL SELECT: Lấy toàn bộ ID cảnh báo."""
    with get_db_client() as client:
        res = client.execute("SELECT id FROM alerts")
        return [r[0] for r in res.rows]


def get_alert_ids_by_cameras_db(cameras: list[str]) -> list[str]:
    """SQL SELECT: Lấy ID cảnh báo của những camera cụ thể."""
    if not cameras:
        return []
    with get_db_client() as client:
        placeholders = ", ".join("?" for _ in cameras)
        res = client.execute(f"SELECT id FROM alerts WHERE camera IN ({placeholders})", cameras)
        return [r[0] for r in res.rows]
