"""Service layer for shared domain (Auth, Alerts, AppState, Camera Control)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from src.web.shared.auth import login as auth_login
from src.web.shared.auth import logout as auth_logout
from src.web.shared.db import log_action
from src.web.shared.pipeline import pipeline
from src.web.shared.cloudinary_uploader import delete_from_cloudinary
import src.web.shared.repository as repo


def login_user(username: str, password: str) -> dict[str, str]:
    try:
        token = auth_login(username, password)
        log_action("Đăng nhập", username.strip().lower(), "Thành công")
        return {"token": token, "username": username.strip().lower()}
    except ValueError as exc:
        log_action("Đăng nhập", username.strip().lower(), f"Thất bại: {exc}")
        raise exc


def logout_user(token: str | None, user: str) -> None:
    auth_logout(token)
    log_action("Đăng xuất", user, "Thành công")


def get_alerts(user: str) -> list[dict[str, Any]]:
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
    repo.solve_alert_db(alert_id)
    with pipeline._lock:
        for alert in pipeline._recent_alerts:
            if alert["id"] == alert_id:
                alert["status"] = "Đã xử lý"
                break
    log_action("Xử lý cảnh báo", user, f"Đã giải quyết cảnh báo: {alert_id}")


def delete_alert(alert_id: str, user: str, media_dir: Path) -> None:
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
    cloud_img = None
    cloud_video = None
    if alert_info:
        cloud_img = alert_info.get("cloud_img_url")
        cloud_video = alert_info.get("cloud_video_url")
        
    # Delete from DB
    repo.hard_delete_alert_db(alert_id)
    
    # Delete from pipeline cache
    with pipeline._lock:
        pipeline._recent_alerts = [a for a in pipeline._recent_alerts if a["id"] != alert_id]
        
    # Delete local files
    try:
        img_path = media_dir / f"{alert_id}.jpg"
        if img_path.exists():
            img_path.unlink()
        video_path = media_dir / f"{alert_id}.mp4"
        if video_path.exists():
            video_path.unlink()
    except Exception as e:
        print(f"[File Error] Khong the xoa media file: {e}")
        
    # Delete Cloudinary resources
    if cloud_img:
        delete_from_cloudinary(cloud_img)
    if cloud_video:
        delete_from_cloudinary(cloud_video)
        
    log_action("Xóa cảnh báo", user, f"Đã xóa cảnh báo hoàn toàn: {alert_id}")


def delete_multiple_alerts(ids: list[str] | None, delete_all: bool, user: str, media_dir: Path) -> int:
    role = repo.get_user_role_db(user)
    
    # Determine which alerts to process
    ids_to_process = []
    if delete_all:
        if role == "Admin":
            ids_to_process = repo.get_all_alert_ids_db()
        else:
            assigned_cams = repo.get_user_assigned_cameras_db(user)
            if assigned_cams:
                ids_to_process = repo.get_alert_ids_by_cameras_db(assigned_cams)
    else:
        if ids:
            ids_to_process = ids

    if not ids_to_process:
        return 0

    if role != "Admin":
        # Soft delete batch
        for aid in ids_to_process:
            alert_info = repo.get_alert_by_id_db(aid)
            if alert_info:
                deleted_by = alert_info.get("deleted_by_users")
                try:
                    deleted_list = json.loads(deleted_by) if deleted_by else []
                except Exception:
                    deleted_list = []
                if user not in deleted_list:
                    deleted_list.append(user)
                repo.soft_delete_alert_db(aid, json.dumps(deleted_list))
        log_action("Xóa nhiều cảnh báo", user, f"Đã ẩn {len(ids_to_process)} cảnh báo.")
        return len(ids_to_process)
        
    # Admin hard delete batch
    for aid in ids_to_process:
        alert_info = repo.get_alert_by_id_db(aid)
        cloud_img = None
        cloud_video = None
        if alert_info:
            cloud_img = alert_info.get("cloud_img_url")
            cloud_video = alert_info.get("cloud_video_url")
            
        repo.hard_delete_alert_db(aid)
        
        with pipeline._lock:
            pipeline._recent_alerts = [a for a in pipeline._recent_alerts if a["id"] != aid]
            
        try:
            img_path = media_dir / f"{aid}.jpg"
            if img_path.exists():
                img_path.unlink()
            video_path = media_dir / f"{aid}.mp4"
            if video_path.exists():
                video_path.unlink()
        except Exception as e:
            print(f"[File Error] Khong the xoa file cho {aid}: {e}")
            
        if cloud_img:
            delete_from_cloudinary(cloud_img)
        if cloud_video:
            delete_from_cloudinary(cloud_video)
            
    log_action("Xóa nhiều cảnh báo", user, f"Đã xóa hoàn toàn {len(ids_to_process)} cảnh báo.")
    return len(ids_to_process)


def get_app_state(user: str) -> dict[str, str]:
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
