"""Service layer for admin domain (Users, Cameras, Notifications, Logs)."""

from __future__ import annotations

import csv
import json
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Any

from src.web.shared.db import log_action
import src.web.admin.repository as repo
from src.web.shared.notifications import (
    load_notif_config,
    CONFIG_PATH,
    send_telegram_alert,
    send_sms_alert,
)


def get_users() -> list[dict[str, Any]]:
    return repo.get_all_users_db()


def create_user(body_dict: dict[str, Any]) -> None:
    assigned_json = json.dumps(body_dict.get("assignedCameras", []))
    repo.create_user_db(
        email=body_dict["email"],
        password=body_dict.get("password"),
        name=body_dict["name"],
        role=body_dict["role"],
        status=body_dict["status"],
        assigned_cameras_json=assigned_json,
        phone=body_dict.get("phone"),
        age=body_dict.get("age"),
        gender=body_dict.get("gender"),
        address=body_dict.get("address")
    )


def update_user(email: str, body_dict: dict[str, Any]) -> None:
    assigned_json = json.dumps(body_dict.get("assignedCameras", []))
    exists = repo.check_user_exists_db(email)
    if not exists:
        repo.create_user_db(
            email=body_dict["email"],
            password=body_dict.get("password"),
            name=body_dict["name"],
            role=body_dict["role"],
            status=body_dict["status"],
            assigned_cameras_json=assigned_json,
            phone=body_dict.get("phone"),
            age=body_dict.get("age"),
            gender=body_dict.get("gender"),
            address=body_dict.get("address")
        )
    else:
        repo.update_user_db(
            email=body_dict["email"],
            password=body_dict.get("password"),
            name=body_dict["name"],
            role=body_dict["role"],
            status=body_dict["status"],
            assigned_cameras_json=assigned_json,
            phone=body_dict.get("phone"),
            old_email=email,
            age=body_dict.get("age"),
            gender=body_dict.get("gender"),
            address=body_dict.get("address")
        )


def delete_user(email: str) -> None:
    repo.delete_user_db(email)


def get_cameras() -> list[dict[str, Any]]:
    return repo.get_all_cameras_db()


def create_camera(body_dict: dict[str, Any], user: str) -> None:
    repo.create_camera_db(
        id=body_dict["id"],
        name=body_dict["name"],
        ip=body_dict["ip"],
        rtsp=body_dict["rtsp"],
        area=body_dict["area"],
        target=body_dict["target"],
        state=body_dict["state"],
        status=body_dict["status"],
        fps=body_dict["fps"],
        resolution=body_dict["resolution"],
        threshold=body_dict["threshold"]
    )
    log_action("Quản lý camera", user, f"Thêm camera: {body_dict['id']} ({body_dict['name']})")


def update_camera(id: str, body_dict: dict[str, Any], user: str) -> None:
    exists = repo.check_camera_exists_db(id)
    if not exists:
        repo.create_camera_db(
            id=body_dict["id"],
            name=body_dict["name"],
            ip=body_dict["ip"],
            rtsp=body_dict["rtsp"],
            area=body_dict["area"],
            target=body_dict["target"],
            state=body_dict["state"],
            status=body_dict["status"],
            fps=body_dict["fps"],
            resolution=body_dict["resolution"],
            threshold=body_dict["threshold"]
        )
    else:
        repo.update_camera_db(
            id=body_dict["id"],
            name=body_dict["name"],
            ip=body_dict["ip"],
            rtsp=body_dict["rtsp"],
            area=body_dict["area"],
            target=body_dict["target"],
            state=body_dict["state"],
            status=body_dict["status"],
            fps=body_dict["fps"],
            resolution=body_dict["resolution"],
            threshold=body_dict["threshold"],
            old_id=id
        )
    log_action("Quản lý camera", user, f"Cập nhật camera: {id} ({body_dict['name']})")


def delete_camera(id: str, user: str) -> None:
    repo.delete_camera_db(id)
    log_action("Quản lý camera", user, f"Xóa camera: {id}")


def get_system_logs() -> list[list[str]]:
    return repo.get_logs_db()


def get_events() -> list[dict[str, Any]]:
    log_path = Path("data/events.csv")
    if not log_path.exists():
        return []
    events = []
    with log_path.open(encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            events.append(row)
    events.reverse()
    return events[:100]


def connect_telegram() -> dict[str, Any]:
    config = load_notif_config()
    telegram_cfg = config.setdefault("telegram", {})
    bot_token = telegram_cfg.get("bot_token")
    
    if not bot_token or bot_token == "YOUR_TELEGRAM_BOT_TOKEN":
        bot_token = "8820249951:AAEndwjP7Bhnj1yUMomuZOXo3f_Ba5lA-6Q"
        telegram_cfg["bot_token"] = bot_token
        
    try:
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            
        results = res_data.get("result", [])
        if not results:
            return {
                "ok": False,
                "detail": "Không tìm thấy tương tác với Bot. Vui lòng bấm 'Start' (Bắt đầu) trên t.me/NCKHFall_bot trước rồi nhấn nút kết nối lại!"
            }
            
        latest_message = None
        for update in reversed(results):
            if "message" in update:
                latest_message = update["message"]
                break
                
        if not latest_message:
            return {
                "ok": False,
                "detail": "Không thấy tin nhắn mới với Bot. Vui lòng gửi tin nhắn bất kỳ cho Bot!"
            }
            
        chat = latest_message.get("chat", {})
        chat_id = chat.get("id")
        username = chat.get("username", chat.get("first_name", "User"))
        
        if chat_id:
            telegram_cfg["chat_id"] = str(chat_id)
            telegram_cfg["enabled"] = True
            
            with CONFIG_PATH.open("w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
                
            send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            send_msg = f"🎉 Kết nối thành công!\nHệ thống FallGuard AI đã được liên kết với tài khoản Telegram của bạn ({username}). Bạn sẽ nhận được các thông báo cảnh báo té ngã tại đây."
            data = urllib.parse.urlencode({"chat_id": chat_id, "text": send_msg}).encode("utf-8")
            send_req = urllib.request.Request(send_url, data=data)
            urllib.request.urlopen(send_req)
            
            return {
                "ok": True,
                "chat_id": chat_id,
                "username": username
            }
            
    except Exception as e:
        return {"ok": False, "detail": f"Lỗi kết nối API Telegram: {e}"}
        
    return {"ok": False, "detail": "Không tìm thấy thông tin trò chuyện."}


def test_notification(channel: str) -> None:
    channel = channel.lower()
    msg = "🚨 CẢNH BÁO TÉ NGÃ: Đây là tin nhắn kiểm tra hệ thống từ FallGuard AI!"
    
    if "telegram" in channel:
        config = load_notif_config().get("telegram", {})
        if not config.get("enabled"):
            raise ValueError("Vui lòng bật nút kích hoạt Telegram Bot trên giao diện trước.")
        send_telegram_alert(msg)
            
    elif "sms" in channel:
        config = load_notif_config().get("sms", {})
        if not config.get("enabled"):
            raise ValueError("Vui lòng bật nút kích hoạt SMS trên giao diện trước.")
        send_sms_alert(msg)
    else:
        raise ValueError(f"Kênh '{channel}' không hỗ trợ gửi thử thực tế.")
