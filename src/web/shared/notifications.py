"""
File: src/web/shared/notifications.py
Chức năng chính: Gửi tin nhắn cảnh báo qua Telegram (thông qua Bot).
Khi có sự kiện té ngã hoặc người lạ, hệ thống gọi file này để báo về điện thoại.
"""
from __future__ import annotations

import html
import json
import os
import smtplib
import uuid
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

CONFIG_PATH = Path("configs/notifications.json")


def load_notif_config() -> dict[str, Any]:
    """Tải cấu hình thông báo từ configs/notifications.json hoặc tạo mới cấu hình mặc định."""
    default_config: dict[str, Any] = {
        "telegram": {
            "enabled": False,
            "bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
            "chat_id": "YOUR_TELEGRAM_CHAT_ID"
        },
        "email": {
            "enabled": False,
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "sender_email": "your_email@gmail.com",
            "sender_password": "your_app_password",
            "receiver_email": "receiver_email@gmail.com"
        },
        "sms": {
            "enabled": False,
            "twilio_sid": "YOUR_TWILIO_ACCOUNT_SID",
            "twilio_token": "YOUR_TWILIO_AUTH_TOKEN",
            "from_number": "+1234567890",
            "to_number": "+84901234567"
        }
    }
    if not CONFIG_PATH.exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        return default_config
    try:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return default_config
            # Đảm bảo có nhánh telegram
            if "telegram" not in data or not isinstance(data["telegram"], dict):
                data["telegram"] = default_config["telegram"]
            return data
    except Exception:
        return default_config


def save_telegram_config(bot_token: str, chat_id: str, enabled: bool) -> dict[str, Any]:
    """Lưu cấu hình Telegram vào configs/notifications.json và trả về dict cấu hình telegram."""
    cfg = load_notif_config()
    cfg.setdefault("telegram", {})
    cfg["telegram"]["bot_token"] = str(bot_token).strip()
    cfg["telegram"]["chat_id"] = str(chat_id).strip()
    cfg["telegram"]["enabled"] = bool(enabled)

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    return cfg["telegram"]


def send_telegram_alert(
    message: str,
    image_path: str | None = None,
    video_path: str | None = None,
    parse_mode: str = "HTML"
) -> dict[str, Any]:
    """
    Gửi tin nhắn cảnh báo tới Telegram Bot:
    - Nếu có ảnh/video: Gửi một tin duy nhất đính kèm caption HTML (không tách rời 2 tin).
    - Nếu chỉ có text: Gửi qua sendMessage với parse_mode="HTML".
    - Trả về dict kết quả {ok: bool, detail: str, ...}.
    """
    config = load_notif_config().get("telegram", {})
    if not config.get("enabled"):
        msg = "Telegram alert bị tắt trong cấu hình (enabled = false)."
        print(f"[Notification] {msg}")
        return {"ok": False, "detail": msg}

    bot_token = config.get("bot_token", "").strip()
    chat_id = str(config.get("chat_id", "")).strip()

    if not bot_token or bot_token == "YOUR_TELEGRAM_BOT_TOKEN":
        msg = "Bot Token chưa được cấu hình. Vui lòng cập nhật token từ @BotFather."
        print(f"[Notification] {msg}")
        return {"ok": False, "detail": msg}

    if not chat_id or chat_id == "YOUR_TELEGRAM_CHAT_ID":
        msg = "Chat ID chưa được cấu hình. Vui lòng nhập Chat ID hoặc bấm 'Tự động lấy Chat ID'."
        print(f"[Notification] {msg}")
        return {"ok": False, "detail": msg}

    # 1. Ưu tiên gửi ảnh kèm caption nếu có file ảnh tồn tại
    if image_path and os.path.exists(image_path) and os.path.getsize(image_path) > 0:
        media_res = _send_media_telegram(
            token=bot_token,
            chat_id=chat_id,
            file_path=image_path,
            media_type="photo",
            caption=message,
            parse_mode=parse_mode,
        )
        if media_res.get("ok"):
            # Nếu có thêm video clip, gửi video bổ sung không kèm caption trùng lặp
            if video_path and os.path.exists(video_path) and os.path.getsize(video_path) > 0:
                _send_media_telegram(
                    token=bot_token,
                    chat_id=chat_id,
                    file_path=video_path,
                    media_type="video",
                    caption=None,
                )
            return media_res
        print(f"[Notification] Gửi ảnh thất bại ({media_res.get('detail')}), chuyển sang gửi tin nhắn văn bản dự phòng...")

    # 2. Hoặc gửi video kèm caption nếu có file video tồn tại
    elif video_path and os.path.exists(video_path) and os.path.getsize(video_path) > 0:
        media_res = _send_media_telegram(
            token=bot_token,
            chat_id=chat_id,
            file_path=video_path,
            media_type="video",
            caption=message,
            parse_mode=parse_mode,
        )
        if media_res.get("ok"):
            return media_res
        print(f"[Notification] Gửi video thất bại ({media_res.get('detail')}), chuyển sang gửi tin nhắn văn bản dự phòng...")

    # 3. Gửi tin nhắn văn bản thuần túy (hoặc fallback khi gửi media lỗi)
    return _send_text_telegram(bot_token, chat_id, message, parse_mode=parse_mode)


def _send_text_telegram(token: str, chat_id: str, message: str, parse_mode: str = "HTML") -> dict[str, Any]:
    text_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(text_url, data=data)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            print("[Notification] Telegram text sent successfully!")
            return {"ok": True, "detail": "Tin nhắn Telegram gửi thành công!", "result": resp_data.get("result")}
    except urllib.error.HTTPError as http_err:
        err_desc = _extract_telegram_error(http_err)
        error_msg = f"Lỗi Telegram ({http_err.code}): {err_desc}"
        print(f"[Notification] {error_msg}")
        return {"ok": False, "detail": error_msg, "status_code": http_err.code}
    except urllib.error.URLError as url_err:
        error_msg = f"Lỗi kết nối máy chủ Telegram: {url_err.reason}"
        print(f"[Notification] {error_msg}")
        return {"ok": False, "detail": error_msg}
    except Exception as ex:
        error_msg = f"Lỗi không xác định khi gửi tin nhắn Telegram: {ex}"
        print(f"[Notification] {error_msg}")
        return {"ok": False, "detail": error_msg}


def _send_media_telegram(
    token: str,
    chat_id: str,
    file_path: str,
    media_type: str,
    caption: str | None = None,
    parse_mode: str = "HTML"
) -> dict[str, Any]:
    boundary = f"Boundary-{uuid.uuid4().hex}"
    url = f"https://api.telegram.org/bot{token}/sendVideo" if media_type == "video" else f"https://api.telegram.org/bot{token}/sendPhoto"
    
    filename = os.path.basename(file_path)
    mime_type = "video/mp4" if media_type == "video" else "image/jpeg"
    field_name = "video" if media_type == "video" else "photo"

    try:
        with open(file_path, "rb") as f:
            file_content = f.read()
    except Exception as read_err:
        error_msg = f"Không thể đọc file media {file_path}: {read_err}"
        print(f"[Notification] {error_msg}")
        return {"ok": False, "detail": error_msg}

    body_parts: list[bytes] = []
    
    # Field: chat_id
    body_parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
        f"{chat_id}\r\n".encode("utf-8")
    )
    
    # Field: caption & parse_mode
    if caption:
        # Telegram caption tối đa 1024 ký tự
        safe_caption = caption if len(caption) <= 1024 else caption[:1020] + "..."
        body_parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="caption"\r\n\r\n'
            f"{safe_caption}\r\n".encode("utf-8")
        )
        if parse_mode:
            body_parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="parse_mode"\r\n\r\n'
                f"{parse_mode}\r\n".encode("utf-8")
            )
            
    # Field: photo / video file
    body_parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8")
        + file_content
        + b"\r\n"
    )
    body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(body_parts)

    req = urllib.request.Request(url, data=body)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            print(f"[Notification] Telegram {media_type} file sent successfully!")
            return {"ok": True, "detail": f"File {media_type} gửi thành công!", "result": resp_data.get("result")}
    except urllib.error.HTTPError as http_err:
        err_desc = _extract_telegram_error(http_err)
        error_msg = f"Lỗi Telegram ({http_err.code}) khi gửi {media_type}: {err_desc}"
        print(f"[Notification] {error_msg}")
        return {"ok": False, "detail": error_msg, "status_code": http_err.code}
    except urllib.error.URLError as url_err:
        error_msg = f"Lỗi mạng khi tải file lên Telegram: {url_err.reason}"
        print(f"[Notification] {error_msg}")
        return {"ok": False, "detail": error_msg}
    except Exception as ex:
        error_msg = f"Lỗi không xác định khi tải file lên Telegram ({media_type}): {ex}"
        print(f"[Notification] {error_msg}")
        return {"ok": False, "detail": error_msg}


def _extract_telegram_error(http_err: urllib.error.HTTPError) -> str:
    """Trích xuất mô tả lỗi cụ thể từ phản hồi JSON của Telegram API."""
    try:
        raw_body = http_err.read().decode("utf-8")
        parsed = json.loads(raw_body)
        if isinstance(parsed, dict) and "description" in parsed:
            return str(parsed["description"])
    except Exception:
        pass
    if http_err.code == 401:
        return "Unauthorized (Bot Token không hợp lệ)."
    elif http_err.code == 400:
        return "Bad Request (Chat ID không tồn tại hoặc bot chưa được kích hoạt trong nhóm/chat)."
    elif http_err.code == 403:
        return "Forbidden (Bot bị chặn hoặc chưa bấm /start)."
    return http_err.reason or f"HTTP {http_err.code}"


def send_email_alert(subject: str, message: str, image_path: str | None = None) -> None:
    config = load_notif_config().get("email", {})
    if not config.get("enabled"):
        return

    smtp_server = config.get("smtp_server")
    smtp_port = config.get("smtp_port", 587)
    sender = config.get("sender_email")
    password = config.get("sender_password")
    receiver = config.get("receiver_email")

    if sender == "your_email@gmail.com" or password == "your_app_password":
        print("[Notification] Email config is default. Please update configs/notifications.json")
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = receiver
        msg["Subject"] = subject

        msg.attach(MIMEText(message, "plain"))

        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as f:
                img_data = f.read()
            image = MIMEImage(img_data, name=os.path.basename(image_path))
            msg.attach(image)

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())
        server.close()
        print("[Notification] Email sent successfully!")
    except Exception as e:
        print(f"[Notification] Lỗi gửi Email: {e}")


def send_sms_alert(message: str) -> None:
    config = load_notif_config().get("sms", {})
    if not config.get("enabled"):
        return

    sid = config.get("twilio_sid")
    token = config.get("twilio_token")
    from_num = config.get("from_number")
    to_num = config.get("to_number")

    if sid == "YOUR_TWILIO_ACCOUNT_SID":
        print(f"[Notification SMS Mock]: {message}")
        return

    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        auth_handler = urllib.request.HTTPBasicAuthHandler()
        auth_handler.add_password(realm="Twilio API", uri=url, user=sid, passwd=token)
        opener = urllib.request.build_opener(auth_handler)
        
        data = urllib.parse.urlencode({
            "From": from_num,
            "To": to_num,
            "Body": message
        }).encode("utf-8")
        
        req = urllib.request.Request(url, data=data)
        opener.open(req)
        print("[Notification] SMS Twilio sent successfully!")
    except Exception as e:
        print(f"[Notification] Lỗi gửi SMS Twilio: {e}")


def format_alert_html(
    alert_type: str,
    alert_id: str,
    camera_name: str | None = None,
    camera_id: str | None = None,
    person_name: str | None = None,
    timestamp: str | None = None,
    cloud_img_url: str | None = None,
    cloud_video_url: str | None = None,
) -> str:
    """Format rich HTML message for Telegram alerts with emojis and structure."""
    is_stranger = (alert_type == "stranger") or (isinstance(alert_id, str) and alert_id.upper().startswith("STRANGER"))

    c_id = camera_id or "CAM-01"
    c_name = camera_name or f"Camera {c_id}"
    cam_display = f"{html.escape(c_name)} ({html.escape(c_id)})" if c_name != c_id else html.escape(c_name)

    time_str = timestamp or datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    safe_time = html.escape(time_str)
    safe_id = html.escape(alert_id)

    if is_stranger:
        safe_person = html.escape(person_name or "Người chưa đăng ký")
        lines = [
            "⚠️ <b>CẢNH BÁO NGƯỜI LẠ XÂM NHẬP</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            f"📍 <b>Camera:</b> {cam_display}",
            f"👤 <b>Nhận diện:</b> {safe_person}",
            f"⏰ <b>Thời gian:</b> {safe_time}",
            f"⚠️ <b>Mã sự cố:</b> <code>{safe_id}</code>",
            "━━━━━━━━━━━━━━━━━━━━",
            "📸 <i>Hình ảnh đối tượng đính kèm bên dưới</i>",
        ]
    else:
        safe_person = html.escape(person_name or "Người cần theo dõi")
        lines = [
            "🚨 <b>CẢNH BÁO TÉ NGÃ KHẨN CẤP!</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            f"📍 <b>Camera:</b> {cam_display}",
            f"👤 <b>Đối tượng:</b> {safe_person}",
            f"⏰ <b>Thời gian:</b> {safe_time}",
            f"⚠️ <b>Mã sự cố:</b> <code>{safe_id}</code>",
            "━━━━━━━━━━━━━━━━━━━━",
            "🔔 <i>Vui lòng kiểm tra người thân ngay lập tức!</i>",
        ]

    if cloud_img_url or cloud_video_url:
        lines.append("")
        lines.append("☁️ <b>Cloud Backup:</b>")
        if cloud_img_url:
            lines.append(f'• <a href="{cloud_img_url}">Ảnh sự cố</a>')
        if cloud_video_url:
            lines.append(f'• <a href="{cloud_video_url}">Video clip</a>')

    return "\n".join(lines)


def send_all_alerts(
    alert_id: str,
    image_path: str | None = None,
    video_path: str | None = None,
    cloud_img_url: str | None = None,
    cloud_video_url: str | None = None,
    alert_type: str | None = None,
    camera_name: str | None = None,
    camera_id: str | None = None,
    person_name: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Tập trung gửi thông báo tới các kênh (Telegram, v.v.) với định dạng HTML chuẩn."""
    is_stranger = (alert_type == "stranger") or (isinstance(alert_id, str) and alert_id.upper().startswith("STRANGER"))

    # Truy vấn metadata bổ sung từ DB nếu chưa truyền vào
    if not camera_id or not person_name or not timestamp:
        try:
            from src.web.shared.db import get_db_client
            with get_db_client() as client:
                res = client.execute("SELECT camera, person, time FROM alerts WHERE id = ?", [alert_id])
                rows = res.fetchall() if hasattr(res, "fetchall") else getattr(res, "rows", [])
                if rows:
                    r = rows[0]
                    cam_val = r[0] if isinstance(r, (list, tuple)) else r.get("camera")
                    per_val = r[1] if isinstance(r, (list, tuple)) else r.get("person")
                    time_val = r[2] if isinstance(r, (list, tuple)) else r.get("time")
                    if not camera_id and cam_val:
                        camera_id = str(cam_val)
                    if not person_name and per_val:
                        person_name = str(per_val)
                    if not timestamp and time_val:
                        timestamp = str(time_val)
        except Exception:
            pass

    if camera_id and not camera_name:
        try:
            from src.web.admin.repository import get_all_cameras_db
            cams = get_all_cameras_db()
            for c in cams:
                if c.get("id") == camera_id:
                    camera_name = c.get("name")
                    break
        except Exception:
            pass

    msg = format_alert_html(
        alert_type="stranger" if is_stranger else "fall",
        alert_id=alert_id,
        camera_name=camera_name,
        camera_id=camera_id,
        person_name=person_name,
        timestamp=timestamp,
        cloud_img_url=cloud_img_url,
        cloud_video_url=cloud_video_url,
    )
            
    return send_telegram_alert(
        message=msg,
        image_path=image_path,
        video_path=video_path,
        parse_mode="HTML"
    )
