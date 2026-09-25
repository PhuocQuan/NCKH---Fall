"""Service layer for shared domain (Auth, Alerts, AppState, Camera Control)."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from src.web.shared.auth import login as auth_login
from src.web.shared.auth import logout as auth_logout
from src.web.shared.db import log_action
from src.web.shared.pipeline import pipeline
from src.web.shared.cloudinary_uploader import delete_from_cloudinary
import src.web.shared.repository as repo


def login_user(username: str, password: str, source: str = "web") -> dict[str, str]:
    """API Logic: Gọi hàm tạo Token và ghi lịch sử Đăng nhập."""
    try:
        token = auth_login(username, password, source)
        log_action("Đăng nhập", username.strip().lower(), "Thành công")
        return {"token": token, "username": username.strip().lower()}
    except ValueError as exc:
        log_action("Đăng nhập", username.strip().lower(), f"Thất bại: {exc}")
        raise exc


def logout_user(token: str | None, user: str) -> None:
    """API Logic: Xóa Token khỏi bộ nhớ để Đăng xuất."""
    auth_logout(token)
    log_action("Đăng xuất", user, "Thành công")


def get_alerts(user: str) -> list[dict[str, Any]]:
    """API Logic: Lấy danh sách cảnh báo. Nếu là Admin thì lấy hết, nếu là User chỉ lấy cảnh báo của Camera được phân quyền."""
    role = repo.get_user_role_db(user)
    all_alerts = repo.get_alerts_db()
    
    assigned_cams = []
    if role != "Admin":
        assigned_cams = repo.get_user_assigned_cameras_db(user)
        if not assigned_cams:
            return []
    
    filtered_alerts = []
    for a in all_alerts:
        deleted_by = a.pop("deleted_by_users")  # remove from response
        try:
            deleted_list = json.loads(deleted_by) if deleted_by else []
        except Exception:
            deleted_list = []
            
        if role != "Admin":
            if user in deleted_list:
                continue
            if a.get("camera") not in assigned_cams:
                continue
                
        filtered_alerts.append(a)
        
    return filtered_alerts


def solve_alert(alert_id: str, user: str) -> None:
    """API Logic: Đánh dấu cảnh báo đã được giải quyết (an toàn)."""
    repo.solve_alert_db(alert_id)
    with pipeline._lock:
        for alert in pipeline._recent_alerts:
            if alert["id"] == alert_id:
                alert["status"] = "Đã xử lý"
                break
    log_action("Xử lý cảnh báo", user, f"Đã giải quyết cảnh báo: {alert_id}")


def delete_alert(alert_id: str, user: str, media_dir: Path) -> None:
    """API Logic: Xóa 1 cảnh báo. Admin thì xóa thật (Database + Ảnh mây), User thì chỉ ẩn khỏi màn hình của họ."""
    role = repo.get_user_role_db(user)
    if role != "Admin":
        # Soft delete: append user email to deleted_by_users list of this alert
        alert_info = repo.get_alert_by_id_db(alert_id)
        if alert_info:
            deleted_by = alert_info.get("deleted_by_users")
            try:
                deleted_list = json.loads(deleted_by) if deleted_by else []
            except Exception:
                deleted_list = []
            if user not in deleted_list:
                deleted_list.append(user)
            repo.soft_delete_alert_db(alert_id, json.dumps(deleted_list))
        log_action("Xóa cảnh báo", user, f"Người dùng đã ẩn cảnh báo: {alert_id}")
        return

    # Admin: hard delete
    alert_info = repo.get_alert_by_id_db(alert_id)
    cloud_img = alert_info.get("cloud_img_url") if alert_info else None
    cloud_video = alert_info.get("cloud_video_url") if alert_info else None

    # Delete from DB
    repo.hard_delete_alert_db(alert_id)

    # Delete from pipeline cache
    with pipeline._lock:
        pipeline._recent_alerts = [a for a in pipeline._recent_alerts if a["id"] != alert_id]

    # Delete local files safely
    try:
        (media_dir / f"{alert_id}.jpg").unlink(missing_ok=True)
        (media_dir / f"{alert_id}.mp4").unlink(missing_ok=True)
    except Exception as e:
        print(f"[File Error] Khong the xoa media file: {e}")

    # Delete Cloudinary resources asynchronously in background
    if cloud_img or cloud_video:
        def _clean_single_bg():
            if cloud_img:
                delete_from_cloudinary(cloud_img)
            if cloud_video:
                delete_from_cloudinary(cloud_video)
        threading.Thread(target=_clean_single_bg, daemon=True).start()

    log_action("Xóa cảnh báo", user, f"Đã xóa cảnh báo hoàn toàn: {alert_id}")


def delete_multiple_alerts(ids: list[str] | None, delete_all: bool, user: str, media_dir: Path) -> int:
    """API Logic: Xóa nhiều cảnh báo cùng lúc (tối ưu hóa batch SQL siêu tốc, dọn dẹp media ngầm)."""
    role = repo.get_user_role_db(user)

    if role != "Admin":
        # Soft delete batch (User thường)
        if delete_all:
            assigned_cams = repo.get_user_assigned_cameras_db(user)
            if not assigned_cams:
                return 0
            repo.batch_soft_delete_alerts_db(user, cameras=assigned_cams)
            count = len(repo.get_alert_ids_by_cameras_db(assigned_cams))
        else:
            if not ids:
                return 0
            repo.batch_soft_delete_alerts_db(user, alert_ids=ids)
            count = len(ids)

        log_action("Xóa nhiều cảnh báo", user, f"Đã ẩn {count} cảnh báo.")
        return count

    # Admin hard delete batch
    if delete_all:
        # Lấy media URLs trước khi xóa toàn bộ
        media_urls = repo.batch_get_alert_media_urls_db()
        all_ids = repo.get_all_alert_ids_db()
        count = len(all_ids)

        # Xóa sạch bảng alerts trong 1 câu SQL duy nhất
        repo.hard_delete_all_alerts_db()

        # Dọn sạch RAM cache pipeline
        with pipeline._lock:
            pipeline._recent_alerts.clear()

        # Dọn dẹp media local và Cloudinary ngầm trong background (không chặn người dùng)
        def _cleanup_all_media_bg(urls: list[str], m_dir: Path):
            try:
                for f in m_dir.glob("*.jpg"):
                    try: f.unlink()
                    except Exception: pass
                for f in m_dir.glob("*.mp4"):
                    try: f.unlink()
                    except Exception: pass
            except Exception:
                pass
            for u in urls:
                if u:
                    try: delete_from_cloudinary(u)
                    except Exception: pass

        threading.Thread(target=_cleanup_all_media_bg, args=(media_urls, media_dir), daemon=True).start()
        log_action("Xóa nhiều cảnh báo", user, f"Đã xóa hoàn toàn {count} cảnh báo.")
        return count

    if not ids:
        return 0

    # Xóa theo danh sách IDs được chọn
    media_urls = repo.batch_get_alert_media_urls_db(ids)
    repo.batch_hard_delete_alerts_db(ids)

    with pipeline._lock:
        ids_set = set(ids)
        pipeline._recent_alerts = [a for a in pipeline._recent_alerts if a["id"] not in ids_set]

    def _cleanup_ids_media_bg(target_ids: list[str], urls: list[str], m_dir: Path):
        for aid in target_ids:
            try:
                (m_dir / f"{aid}.jpg").unlink(missing_ok=True)
                (m_dir / f"{aid}.mp4").unlink(missing_ok=True)
            except Exception:
                pass
        for u in urls:
            if u:
                try: delete_from_cloudinary(u)
                except Exception: pass

    threading.Thread(target=_cleanup_ids_media_bg, args=(ids, media_urls, media_dir), daemon=True).start()
    log_action("Xóa nhiều cảnh báo", user, f"Đã xóa hoàn toàn {len(ids)} cảnh báo.")
    return len(ids)


def get_app_state(user: str) -> dict[str, str]:
    """API Logic: Gộp cài đặt chung của Hệ thống (Admin) và cài đặt riêng của User."""
    global_state = repo.get_app_state_db()
    user_state = repo.get_user_app_state_db(user)
    return {
        "api_keys_json": global_state["api_keys_json"],
        "settings_json": global_state["settings_json"],
        "monitored_profile_json": user_state["monitored_profile_json"],
        "emergency_contacts_json": user_state["emergency_contacts_json"],
        "user_notifications_json": user_state["user_notifications_json"]
    }


def update_app_state(body_dict: dict[str, str | None], user: str) -> None:
    """API Logic: Lưu cấu hình. Phân tách key nào thuộc Admin, key nào thuộc User để update vào bảng tương ứng."""
    global_updates = []
    global_params = []
    user_updates = []
    user_params = []
    
    for key in ["api_keys_json", "settings_json"]:
        val = body_dict.get(key)
        if val is not None:
            global_updates.append(f"{key} = ?")
            global_params.append(val)
            
    for key in ["monitored_profile_json", "emergency_contacts_json", "user_notifications_json"]:
        val = body_dict.get(key)
        if val is not None:
            user_updates.append(f"{key} = ?")
            user_params.append(val)
            
    if global_updates:
        global_params.append("global")
        repo.update_app_state_db(global_updates, global_params)
        
    if user_updates:
        repo.update_user_app_state_db(user, user_updates, user_params)
        
    log_action("Cấu hình hệ thống", user, "Cập nhật cấu hình ứng dụng (app state)")
