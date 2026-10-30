"""Repository layer for admin domain (Users, Cameras, Logs)."""

from __future__ import annotations

import json
from typing import Any
from src.web.shared.db import get_db_client


def get_all_users_db() -> list[dict[str, Any]]:
    """Truy vấn SQL để lấy danh sách người dùng. Giải mã (parse) chuỗi JSON nếu có."""
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
    """SQL DELETE: Xóa user."""
    with get_db_client() as client:
        client.execute("DELETE FROM users WHERE email = ?", [email])


def get_all_cameras_db() -> list[dict[str, Any]]:
    """SQL SELECT: Lấy danh sách cameras."""
    cams = []
    try:
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
    except Exception as e:
        print(f"[Database Error] Khong the lay danh sach camera tu DB: {e}")
    return cams


def create_camera_db(id: str, name: str, ip: str, rtsp: str, area: str, target: str, state: str, status: str, fps: int, resolution: str, threshold: int) -> None:
    with get_db_client() as client:
        client.execute(
            """INSERT INTO cameras (id, name, ip, rtsp, area, target, state, status, fps, resolution, threshold)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   name = excluded.name,
                   ip = excluded.ip,
                   rtsp = excluded.rtsp,
                   area = excluded.area,
                   target = excluded.target,
                   state = excluded.state,
                   status = excluded.status,
                   fps = excluded.fps,
                   resolution = excluded.resolution,
                   threshold = excluded.threshold
            """,
            [id, name, ip, rtsp, area, target, state, status, fps, resolution, threshold]
        )


def upsert_camera_stream_db(
    id: str,
    name: str,
    ip: str,
    rtsp: str,
    area: str = "Phòng chính",
    target: str = "Nguy cơ cao",
    state: str = "normal",
    status: str = "online",
    fps: int = 25,
    resolution: str = "1920x1080",
    threshold: int = 80,
) -> str:
    """Upsert camera information (insert or update on conflict) in SQLite/Turso database."""
    create_camera_db(id, name, ip, rtsp, area, target, state, status, fps, resolution, threshold)
    return id


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


def update_camera_network_db(
    camera_id: str,
    new_ip: str,
    new_rtsp: str,
    name: str | None = None,
    mode: str = "update",
) -> str:
    """Cập nhật IP và RTSP mới cho camera, hoặc tạo mới nếu chưa tồn tại hoặc mode='new'."""
    with get_db_client() as client:
        cam_name = name or f"Camera Imou ({new_ip})"

        # 1. Trường hợp người dùng chọn 'Thêm mới thành Camera riêng biệt'
        if mode == "new":
            target_id = camera_id.strip() if camera_id else ""
            if not target_id:
                count_res = client.execute("SELECT count(*) FROM cameras")
                c_num = (count_res.rows[0][0] if count_res.rows else 0) + 1
                target_id = f"CAM-{c_num:03d}"

            res = client.execute("SELECT 1 FROM cameras WHERE id = ?", [target_id])
            if res.rows:
                client.execute(
                    "UPDATE cameras SET name = ?, ip = ?, rtsp = ?, status = 'online' WHERE id = ?",
                    [cam_name, new_ip, new_rtsp, target_id],
                )
            else:
                client.execute(
                    "INSERT INTO cameras (id, name, ip, rtsp, area, target, state, status, fps, resolution, threshold) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [target_id, cam_name, new_ip, new_rtsp, "Phòng chính", "Nguy cơ cao", "normal", "online", 25, "1920x1080", 80],
                )
            return target_id

        # 2. Trường hợp mode == 'update'
        if camera_id:
            res = client.execute("SELECT 1 FROM cameras WHERE id = ?", [camera_id])
            if res.rows:
                if name:
                    client.execute(
                        "UPDATE cameras SET name = ?, ip = ?, rtsp = ?, status = 'online' WHERE id = ?",
                        [cam_name, new_ip, new_rtsp, camera_id],
                    )
                else:
                    client.execute(
                        "UPDATE cameras SET ip = ?, rtsp = ?, status = 'online' WHERE id = ?",
                        [new_ip, new_rtsp, camera_id],
                    )
                return camera_id
            else:
                # Camera ID được chỉ định nhưng chưa tồn tại trong DB -> INSERT mới ngay để lưu vào cơ sở dữ liệu
                client.execute(
                    "INSERT INTO cameras (id, name, ip, rtsp, area, target, state, status, fps, resolution, threshold) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [camera_id, cam_name, new_ip, new_rtsp, "Phòng chính", "Nguy cơ cao", "normal", "online", 25, "1920x1080", 80],
                )
                return camera_id

        # 3. Fallback nếu không truyền camera_id: cập nhật camera đầu tiên nếu có
        res2 = client.execute("SELECT id FROM cameras ORDER BY id ASC LIMIT 1")
        if res2.rows:
            target_id = str(res2.rows[0][0])
            client.execute(
                "UPDATE cameras SET ip = ?, rtsp = ?, status = 'online' WHERE id = ?",
                [new_ip, new_rtsp, target_id],
            )
            return target_id

        # 4. Bảng cameras hoàn toàn trống
        target_id = "CAM-001"
        client.execute(
            "INSERT INTO cameras (id, name, ip, rtsp, area, target, state, status, fps, resolution, threshold) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [target_id, cam_name, new_ip, new_rtsp, "Phòng chính", "Nguy cơ cao", "normal", "online", 25, "1920x1080", 80],
        )
        return target_id


def delete_camera_db(id: str) -> None:
    """SQL DELETE: Xóa camera."""
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
