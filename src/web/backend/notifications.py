"""Module hỗ trợ gửi cảnh báo thực tế qua Telegram, Email SMTP và SMS."""

from __future__ import annotations

import json
import os
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
import urllib.request
import urllib.parse

CONFIG_PATH = Path("configs/notifications.json")


def load_notif_config() -> dict:
    if not CONFIG_PATH.exists():
        default_config = {
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
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        return default_config
    try:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def send_telegram_alert(message: str, image_path: str | None = None, video_path: str | None = None) -> None:
    config = load_notif_config().get("telegram", {})
    if not config.get("enabled"):
        return

    bot_token = config.get("bot_token")
    chat_id = config.get("chat_id")

    if bot_token == "YOUR_TELEGRAM_BOT_TOKEN" or chat_id == "YOUR_TELEGRAM_CHAT_ID":
        print("[Notification] Telegram config is default. Please update configs/notifications.json")
        return

    try:
        # 1. Send Text message
        text_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode("utf-8")
        req = urllib.request.Request(text_url, data=data)
        urllib.request.urlopen(req)
        print("[Notification] Telegram text sent successfully!")

        # 2. Send Video or Photo if present
        if video_path and os.path.exists(video_path):
            # Send video using multipart form
            _send_media_telegram(bot_token, chat_id, video_path, "video")
        elif image_path and os.path.exists(image_path):
            _send_media_telegram(bot_token, chat_id, image_path, "photo")
    except Exception as e:
        print(f"[Notification] Lỗi gửi Telegram: {e}")


def _send_media_telegram(token: str, chat_id: str, file_path: str, media_type: str) -> None:
    import uuid
    boundary = f"Boundary-{uuid.uuid4().hex}"
    
    url = f"https://api.telegram.org/bot{token}/sendVideo" if media_type == "video" else f"https://api.telegram.org/bot{token}/sendPhoto"
    
    filename = os.path.basename(file_path)
    mime_type = "video/mp4" if media_type == "video" else "image/jpeg"
    field_name = "video" if media_type == "video" else "photo"

    with open(file_path, "rb") as f:
        file_content = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
        f"{chat_id}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8") + file_content + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(url, data=body)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        urllib.request.urlopen(req)
        print(f"[Notification] Telegram {media_type} file sent successfully!")
    except Exception as e:
        print(f"[Notification] Lỗi tải file lên Telegram ({media_type}): {e}")


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


def send_all_alerts(
    alert_id: str,
    image_path: str | None = None,
    video_path: str | None = None,
    cloud_img_url: str | None = None,
    cloud_video_url: str | None = None
) -> None:
    msg = f"🚨 CẢNH BÁO TÉ NGÃ: Phát hiện sự cố té ngã tại hệ thống FallGuard! Mã cảnh báo: {alert_id}."
    
    if cloud_img_url or cloud_video_url:
        msg += "\n☁️ Link Cloud Backup:\n"
        if cloud_img_url:
            msg += f"- Ảnh: {cloud_img_url}\n"
        if cloud_video_url:
            msg += f"- Video: {cloud_video_url}\n"
            
    send_telegram_alert(msg, image_path, video_path)
    send_email_alert(f"[FallGuard Alert] Phát hiện té ngã {alert_id}", msg, image_path)
    send_sms_alert(msg)
