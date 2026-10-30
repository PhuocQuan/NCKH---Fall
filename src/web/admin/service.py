"""Service layer for admin domain (Users, Cameras, Notifications, Logs)."""

from __future__ import annotations

import csv
import json
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Any

from datetime import datetime

from src.web.shared.db import log_action
import src.web.admin.repository as repo
from src.web.shared.notifications import (
    load_notif_config,
    save_telegram_config,
    CONFIG_PATH,
    send_telegram_alert,
    send_sms_alert,
)



def get_users() -> list[dict[str, Any]]:
    """Gọi repository để lấy danh sách Users từ CSDL Turso."""
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
    """Xóa người dùng khỏi hệ thống thông qua repository."""
    repo.delete_user_db(email)


def get_cameras() -> list[dict[str, Any]]:
    """Lấy danh sách toàn bộ camera từ DB."""
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


def get_cameras_status() -> list[dict[str, Any]]:
    """Lấy danh sách camera kèm trạng thái kết nối và latency thời gian thực."""
    from src.camera.multi_camera_manager import multi_camera_manager
    return multi_camera_manager.get_all_cameras_status()


def test_camera(camera_id: str) -> dict[str, Any]:
    """Kiểm tra kết nối và đo ping latency cho một camera cụ thể."""
    from src.camera.multi_camera_manager import multi_camera_manager
    cams = repo.get_all_cameras_db()
    target = next((c for c in cams if c.get("id") == camera_id), None)
    if not target:
        raise ValueError(f"Không tìm thấy camera có mã {camera_id}")

    rtsp = str(target.get("rtsp") or target.get("ip") or "0").strip()
    res = multi_camera_manager.test_connection(rtsp)

    # Cập nhật trạng thái online/offline vào database
    new_status = "online" if res.get("connected") else "offline"
    try:
        from src.web.shared.db import get_db_client
        with get_db_client() as client:
            client.execute("UPDATE cameras SET status = ? WHERE id = ?", [new_status, camera_id])
    except Exception:
        pass

    res["camera_id"] = camera_id
    res["name"] = target.get("name", camera_id)
    return res


def test_camera_connection_arbitrary(rtsp_or_source: str) -> dict[str, Any]:
    """Kiểm tra đường dẫn RTSP hoặc Webcam bất kỳ trước khi lưu vào CSDL."""
    from src.camera.multi_camera_manager import multi_camera_manager
    return multi_camera_manager.test_connection(rtsp_or_source)


def set_primary_camera(camera_id: str, user: str) -> dict[str, Any]:
    """Chuyển đổi camera giám sát."""
    from src.camera.multi_camera_manager import multi_camera_manager
    result = multi_camera_manager.set_primary_camera(camera_id)
    log_action("Quản lý camera", user, f"Chuyển camera giám sát sang: {camera_id} ({result.get('name')})")
    return result


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


def get_telegram_config() -> dict[str, Any]:
    """Lấy thông tin cấu hình Telegram hiện tại."""
    cfg = load_notif_config().get("telegram", {})
    return {
        "ok": True,
        "bot_token": str(cfg.get("bot_token", "")),
        "chat_id": str(cfg.get("chat_id", "")),
        "enabled": bool(cfg.get("enabled", False)),
    }


def update_telegram_config(bot_token: str, chat_id: str, enabled: bool) -> dict[str, Any]:
    """Cập nhật cấu hình Telegram và lưu vào file cấu hình."""
    saved = save_telegram_config(bot_token=bot_token, chat_id=chat_id, enabled=enabled)
    return {
        "ok": True,
        "bot_token": saved.get("bot_token", ""),
        "chat_id": str(saved.get("chat_id", "")),
        "enabled": bool(saved.get("enabled", False)),
        "detail": "Đã lưu cấu hình Telegram thành công!"
    }


def connect_telegram(bot_token: str | None = None) -> dict[str, Any]:
    """
    Tự động dò tìm Chat ID từ các tin nhắn tương tác gần nhất với Bot qua Telegram getUpdates.
    Sử dụng bot_token được cung cấp hoặc lấy từ file cấu hình (không hardcode).
    """
    config = load_notif_config()
    telegram_cfg = config.get("telegram", {})
    
    token = (bot_token or telegram_cfg.get("bot_token", "")).strip()
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN":
        return {
            "ok": False,
            "detail": "Vui lòng nhập Bot Token từ @BotFather trước khi tự động lấy Chat ID!"
        }
        
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            
        results = res_data.get("result", [])
        if not results:
            return {
                "ok": False,
                "detail": "Chưa tìm thấy tin nhắn nào. Bạn hãy mở Bot trên Telegram và bấm 'Start' hoặc gửi 1 tin nhắn bất kỳ cho Bot, sau đó bấm nút này lại nhé!"
            }
            
        latest_chat = None
        for update in reversed(results):
            chat_obj = None
            if "message" in update and "chat" in update["message"]:
                chat_obj = update["message"]["chat"]
            elif "channel_post" in update and "chat" in update["channel_post"]:
                chat_obj = update["channel_post"]["chat"]
            elif "my_chat_member" in update and "chat" in update["my_chat_member"]:
                chat_obj = update["my_chat_member"]["chat"]
            elif "callback_query" in update and "message" in update["callback_query"]:
                chat_obj = update["callback_query"]["message"].get("chat")

            if chat_obj and chat_obj.get("id"):
                latest_chat = chat_obj
                break
                
        if not latest_chat:
            return {
                "ok": False,
                "detail": "Chưa tìm thấy tin nhắn nào. Bạn hãy mở Bot trên Telegram và bấm 'Start' hoặc gửi 1 tin nhắn bất kỳ cho Bot, sau đó bấm nút này lại nhé!"
            }
            
        chat_id = str(latest_chat.get("id"))
        username = latest_chat.get("title") or latest_chat.get("username") or latest_chat.get("first_name", "User")
        
        save_telegram_config(bot_token=token, chat_id=chat_id, enabled=True)
            
        welcome_msg = (
            "🎉 <b>KẾT NỐI THÀNH CÔNG!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"Hệ thống FallGuard AI đã được liên kết với tài khoản Telegram của bạn (<b>{username}</b>).\n"
            "Bạn sẽ nhận được các thông báo cảnh báo té ngã tại đây."
        )
        send_telegram_alert(welcome_msg)
        
        return {
            "ok": True,
            "chat_id": chat_id,
            "username": username,
            "detail": f"Đã kết nối thành công với Telegram của {username}!"
        }
            
    except urllib.error.HTTPError as http_err:
        if http_err.code == 401:
            return {"ok": False, "detail": "Bot Token không hợp lệ. Vui lòng kiểm tra lại token từ @BotFather!"}
        return {"ok": False, "detail": f"Lỗi Telegram API ({http_err.code}): {http_err.reason}"}
    except Exception as e:
        return {"ok": False, "detail": f"Lỗi kết nối API Telegram: {e}"}


def test_telegram() -> dict[str, Any]:
    """Gửi một cảnh báo kiểm tra tức thì tới Telegram với định dạng HTML chuyên nghiệp."""
    config = load_notif_config().get("telegram", {})
    if not config.get("enabled"):
        raise ValueError("Vui lòng bật nút kích hoạt Telegram Bot trên giao diện trước khi gửi thử.")
        
    bot_token = config.get("bot_token", "").strip()
    chat_id = str(config.get("chat_id", "")).strip()
    if not bot_token or bot_token == "YOUR_TELEGRAM_BOT_TOKEN":
        raise ValueError("Bot Token chưa được thiết lập. Vui lòng cấu hình Bot Token từ @BotFather!")
    if not chat_id or chat_id == "YOUR_TELEGRAM_CHAT_ID":
        raise ValueError("Chat ID chưa được thiết lập. Vui lòng nhập Chat ID hoặc bấm 'Tự động lấy Chat ID'!")

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    msg = (
        "🧪 <b>KIỂM TRA HỆ THỐNG THÔNG BÁO FALLGUARD AI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ <b>Trạng thái:</b> Kết nối Telegram hoạt động bình thường!\n"
        f"⏰ <b>Thời gian:</b> {now_str}\n"
        "🔔 <b>Kênh nhận:</b> Telegram Bot Alert\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Đây là tin nhắn kiểm tra. Hệ thống đã sẵn sàng gửi cảnh báo khẩn cấp khi phát hiện té ngã!</i>"
    )
    result = send_telegram_alert(msg)
    if not result.get("ok"):
        raise RuntimeError(result.get("detail", "Không thể gửi tin nhắn thử nghiệm tới Telegram."))
    return {"ok": True, "detail": "Đã gửi tin nhắn cảnh báo thử nghiệm tới Telegram!"}


def test_notification(channel: str) -> dict[str, Any]:
    channel = channel.lower()
    if "telegram" in channel:
        return test_telegram()
    elif "sms" in channel:
        config = load_notif_config().get("sms", {})
        if not config.get("enabled"):
            raise ValueError("Vui lòng bật nút kích hoạt SMS trên giao diện trước.")
        msg = "🚨 CẢNH BÁO TÉ NGÃ: Đây là tin nhắn kiểm tra hệ thống từ FallGuard AI!"
        send_sms_alert(msg)
        return {"ok": True, "detail": "Đã gửi tin nhắn cảnh báo thử nghiệm tới SMS!"}
    else:
        raise ValueError(f"Kênh '{channel}' không hỗ trợ gửi thử thực tế.")



def auto_bind_camera(camera_id: str, new_ip: str, safety_code: str, user: str, name: str | None = None, mode: str = "update") -> dict[str, Any]:
    """Cập nhật IP mới của Camera khi quét thấy trên mạng Wi-Fi và tái kết nối pipeline AI."""
    import time
    from src.camera.camera_discovery import build_imou_rtsp, probe_dahua_rpc
    from src.web.shared.pipeline import pipeline
    
    # Ngăn chặn việc liên kết nhầm Router / Gateway mạng (.1 hoặc .2) thay vì Camera thật
    parts = new_ip.split(".")
    if len(parts) == 4 and parts[3] in ("1", "2"):
        if not probe_dahua_rpc(new_ip, port=37777, timeout=0.35):
            raise ValueError(f"Địa chỉ {new_ip} là Router Wi-Fi / Thiết bị mạng gia đình, không phải Camera RTSP. Vui lòng chọn đúng IP của Camera (ví dụ: 192.168.1.18)!")

    new_rtsp = build_imou_rtsp(new_ip, safety_code)
    actual_cam_id = repo.update_camera_network_db(camera_id, new_ip, new_rtsp, name=name, mode=mode)
    log_action("Tự động kết nối camera", user, f"Camera {actual_cam_id} liên kết sang IP mới: {new_ip}")
    
    # Khởi động lại luồng pipeline nếu chưa chạy đúng nguồn mới
    try:
        current_source = str(getattr(pipeline.status, "source", ""))
        if not (pipeline.is_running() and current_source == new_rtsp):
            pipeline.start(source=new_rtsp, camera_id=actual_cam_id)
            print(f"[Auto-Bind] ✅ Đã chuyển luồng Camera {actual_cam_id} sang IP mới {new_ip}!")
        else:
            pipeline.camera_id = actual_cam_id
            print(f"[Auto-Bind] ✅ Camera {actual_cam_id} đang hoạt động ổn định trên IP {new_ip}.")
    except Exception as e:
        print(f"[Auto-Bind Warning] Không thể khởi động lại pipeline ngay: {e}")

    return {
        "ok": True,
        "camera_id": actual_cam_id,
        "new_ip": new_ip,
        "new_rtsp": new_rtsp,
        "message": f"Đã kết nối thành công Camera {actual_cam_id} tại IP {new_ip}!"
    }
