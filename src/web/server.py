"""FastAPI server: dashboard web + API tích hợp fall detection."""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.web.backend.auth import login as auth_login
from src.web.backend.auth import logout as auth_logout
from src.web.backend.auth import verify_token
from src.web.backend.pipeline import FallDetectionPipeline

WEB_ROOT = Path(__file__).resolve().parent
pipeline = FallDetectionPipeline()


class LoginRequest(BaseModel):
    username: str
    password: str


class ControlRequest(BaseModel):
    source: str = "0"


class TestNotifRequest(BaseModel):
    channel: str


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.query_params.get("token")


def require_user(request: Request) -> str:
    token = _extract_token(request)
    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Chua dang nhap hoac token het han.")
    return user


app = FastAPI(title="FallGuard AI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "pipeline_running": pipeline.is_running()}


@app.post("/api/auth/login")
def api_login(body: LoginRequest) -> dict[str, str]:
    try:
        token = auth_login(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"token": token, "username": body.username.strip().lower()}


@app.post("/api/auth/logout")
def api_logout(request: Request, user: str = Depends(require_user)) -> dict[str, bool]:
    auth_logout(_extract_token(request))
    return {"ok": True}


@app.post("/api/control/start")
def control_start(body: ControlRequest, user: str = Depends(require_user)) -> dict[str, Any]:
    try:
        pipeline.start(body.source)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Khong khoi dong camera: {exc}") from exc
    return {"ok": True, "source": body.source, "status": pipeline.status.to_dict()}


@app.post("/api/control/stop")
def control_stop(user: str = Depends(require_user)) -> dict[str, bool]:
    pipeline.stop()
    return {"ok": True}


@app.get("/api/detection/status")
def detection_status(user: str = Depends(require_user)) -> dict[str, Any]:
    status = pipeline.status.to_dict()
    confidence = 18
    if status["pose_detected"]:
        if status["state"] in {"fallen", "alert"}:
            confidence = min(99, int(70 + status["torso_angle_deg"] / 2))
        elif status["state"] in {"warning", "possible_fall", "lying"}:
            confidence = 81
    return {
        **status,
        "confidence": confidence,
        "pipeline": [
            ["Nhận diện người", "Đang chạy" if status["pose_detected"] else "Chờ pose", "Person detected" if status["pose_detected"] else "No pose"],
            ["Theo dõi người", "Đang chạy" if status["running"] else "Dừng", "Tracking realtime"],
            ["Phân tích hành vi", "Đang chạy" if status["running"] else "Dừng", status["state"]],
            ["Độ tin cậy", f"{confidence}%", "Fall Detected" if status["state"] in {"fallen", "alert"} else "Monitoring"],
            ["Kiểm tra nằm lâu", f"Nằm {status['lying_seconds']:.1f}s", "Tăng mức cảnh báo" if status["lying_seconds"] >= 10 else "Binh thuong"],
        ],
    }


@app.get("/api/alerts")
def list_alerts(user: str = Depends(require_user)) -> dict[str, Any]:
    return {"alerts": pipeline.recent_alerts()}


@app.get("/api/events")
def list_events(user: str = Depends(require_user)) -> dict[str, Any]:
    try:
        from src.core.database import get_events
        return {"events": get_events(limit=100)}
    except Exception as e:
        print(f"[Server Error] Failed to get events from database: {e}. Falling back to CSV.")
        log_path = Path("data/events.csv")
        if not log_path.exists():
            return {"events": []}
        events = []
        with log_path.open(encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                events.append(row)
        events.reverse()
        return {"events": events[:100]}


def _mjpeg_generator():
    placeholder = _placeholder_frame()
    while True:
        frame = pipeline.get_jpeg_frame() or placeholder
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
        )
        time.sleep(0.04)


def _placeholder_frame() -> bytes:
    import cv2
    import numpy as np

    img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(img, "FallGuard AI", (170, 220), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
    cv2.putText(img, "Nhan Mo camera de bat dau", (120, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180, 180, 180), 1)
    ok, jpeg = cv2.imencode(".jpg", img)
    return jpeg.tobytes() if ok else b""


@app.get("/api/camera/stream.mjpg")
def camera_stream(request: Request):
    if not verify_token(_extract_token(request)):
        raise HTTPException(status_code=401, detail="Token khong hop le.")
    return StreamingResponse(_mjpeg_generator(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/camera/snapshot")
def camera_snapshot(request: Request):
    if not verify_token(_extract_token(request)):
        raise HTTPException(status_code=401, detail="Token khong hop le.")
    placeholder = _placeholder_frame()
    frame = pipeline.get_jpeg_frame() or placeholder
    from fastapi.responses import Response
    return Response(content=frame, media_type="image/jpeg")


@app.post("/api/telegram/connect")
def telegram_connect(user: str = Depends(require_user)) -> dict[str, Any]:
    from src.web.backend.notifications import load_notif_config, CONFIG_PATH
    import urllib.request
    import urllib.parse
    import json
    
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


@app.post("/api/notifications/test")
def test_notification(body: TestNotifRequest, user: str = Depends(require_user)) -> dict[str, Any]:
    from src.web.backend.notifications import send_telegram_alert, send_sms_alert, load_notif_config
    
    channel = body.channel.lower()
    msg = "🚨 CẢNH BÁO TÉ NGÃ: Đây là tin nhắn kiểm tra hệ thống từ FallGuard AI!"
    
    if "telegram" in channel:
        config = load_notif_config().get("telegram", {})
        if not config.get("enabled"):
            raise HTTPException(status_code=400, detail="Vui lòng bật nút kích hoạt Telegram Bot trên giao diện trước.")
        try:
            # Send message bypassing status because user explicitly requested it
            # But the send_telegram_alert checks config['enabled'] which is True
            send_telegram_alert(msg)
            return {"ok": True, "detail": "Đã gửi tin nhắn cảnh báo thử nghiệm tới Telegram!"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi gửi Telegram: {e}")
            
    elif "sms" in channel:
        config = load_notif_config().get("sms", {})
        if not config.get("enabled"):
            raise HTTPException(status_code=400, detail="Vui lòng bật nút kích hoạt SMS trên giao diện trước.")
        try:
            send_sms_alert(msg)
            return {"ok": True, "detail": "Đã gửi tin nhắn test SMS!"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi gửi SMS: {e}")
            
    return {"ok": False, "detail": f"Kênh '{body.channel}' không hỗ trợ gửi thử thực tế."}


@app.get("/api/data/store")
def get_dashboard_store(user: str = Depends(require_user)) -> dict[str, Any]:
    from src.core.database import get_kv, save_kv, get_db_connection
    cameras = get_kv("fg_cameras")
    people = get_kv("fg_people")
    users_list = get_kv("fg_users")
    if users_list is None:
        users_list = []
    api_keys = get_kv("fg_api_keys")
    settings = get_kv("fg_settings")
    
    # Đồng bộ 2 chiều giữa kv_store và bảng SQL users
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username, password, role FROM users")
        db_rows = cursor.fetchall()
        
        # Tạo map lưu thông tin từ database SQL
        db_users = {}
        for row in db_rows:
            if hasattr(row, "keys"):
                r_dict = dict(row)
                uname = r_dict["username"]
                db_users[uname] = r_dict
            elif isinstance(row, dict):
                uname = row["username"]
                db_users[uname] = row
            else:
                uname = row[0]
                db_users[uname] = {"username": row[0], "password": row[1], "role": row[2]}
                
        # Cập nhật danh sách từ Frontend bằng dữ liệu từ SQL
        frontend_usernames = set()
        users_list_changed = False
        
        for u in users_list:
            email = u.get("email", "").strip().lower()
            if not email:
                continue
            username = email.split("@", 1)[0] if "@" in email else email
            frontend_usernames.add(username)
            
            if username in db_users:
                # Cập nhật password và role từ SQL vào frontend list nếu khác nhau
                db_pwd = db_users[username].get("password")
                if u.get("password") != db_pwd:
                    u["password"] = db_pwd
                    users_list_changed = True
                
                role_map = {
                    "Admin": "Admin",
                    "Quản lý": "Quản lý",
                    "Điều dưỡng": "Nhân viên y tế",
                    "Nhân viên y tế": "Nhân viên y tế",
                    "Người nhà": "Người thân",
                    "Người thân": "Người thân",
                    "Khách": "Khách xem báo cáo",
                    "Khách xem báo cáo": "Khách xem báo cáo"
                }
                db_role = db_users[username].get("role")
                mapped_role = role_map.get(db_role, db_role)
                if u.get("role") != mapped_role:
                    u["role"] = mapped_role
                    users_list_changed = True
            else:
                # Nếu có trên frontend nhưng chưa có trong SQL, thêm vào SQL
                pwd = u.get("password") or "nckh2025"
                role = u.get("role", "User")
                cursor.execute(
                    "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                    (username, pwd, role)
                )
                conn.commit()
                db_users[username] = {"username": username, "password": pwd, "role": role}
                
        # Nếu có trong SQL nhưng chưa có trong frontend list, thêm vào frontend list
        for username, db_u in db_users.items():
            if username not in frontend_usernames and username:
                role_map = {
                    "Admin": "Admin",
                    "Quản lý": "Quản lý",
                    "Điều dưỡng": "Nhân viên y tế",
                    "Nhân viên y tế": "Nhân viên y tế",
                    "Người nhà": "Người thân",
                    "Người thân": "Người thân",
                    "Khách": "Khách xem báo cáo",
                    "Khách xem báo cáo": "Khách xem báo cáo"
                }
                fe_role = role_map.get(db_u.get("role"), "Khách xem báo cáo")
                
                new_fe_user = {
                    "email": f"{username}@nckh.vn",
                    "name": username.capitalize(),
                    "role": fe_role,
                    "status": "Đang hoạt động",
                    "password": db_u.get("password") or "nckh2025",
                    "assignedCameras": []
                }
                users_list.append(new_fe_user)
                users_list_changed = True
                
        if users_list_changed:
            save_kv("fg_users", users_list)
            print("[Sync Users Startup] Đã đồng bộ tài khoản giữa SQL và kv_store.")
            
    except Exception as e:
        print(f"[Sync Users Startup Error] {e}")
            
    return {
        "cameras": cameras,
        "people": people,
        "users": users_list,
        "apiKeys": api_keys,
        "settings": settings,
    }


@app.post("/api/data/store")
def save_dashboard_store(body: dict[str, Any], user: str = Depends(require_user)) -> dict[str, bool]:
    from src.core.database import save_kv, get_db_connection
    if "cameras" in body:
        save_kv("fg_cameras", body["cameras"])
    if "people" in body:
        save_kv("fg_people", body["people"])
    if "users" in body:
        save_kv("fg_users", body["users"])
        
        # Đồng bộ danh sách tài khoản sang bảng users trong SQL database để có thể Đăng nhập
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Lấy các username hiện tại trong SQL
            cursor.execute("SELECT username FROM users")
            db_usernames = {row[0] if isinstance(row, tuple) else row["username"] for row in cursor.fetchall()}
            
            frontend_usernames = set()
            for u in body["users"]:
                email = u.get("email", "").strip().lower()
                if not email:
                    continue
                # Chuyển email sang username giống auth.py
                username = email.split("@", 1)[0] if "@" in email else email
                frontend_usernames.add(username)
                
                # Nếu chưa có trong SQL, thêm mới với mật khẩu từ Frontend
                pwd = u.get("password") or "nckh2025"
                role = u.get("role", "User")
                if username not in db_usernames:
                    cursor.execute(
                        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                        (username, pwd, role)
                    )
                else:
                    # Cập nhật mật khẩu và vai trò nếu thay đổi
                    cursor.execute(
                        "UPDATE users SET password = ?, role = ? WHERE username = ?",
                        (pwd, role, username)
                    )
            
            # Xóa các username trong SQL không còn nằm trong danh sách của Frontend (trừ tài khoản admin chính)
            for db_user in db_usernames:
                if db_user not in frontend_usernames and db_user not in {"admin"}:
                    cursor.execute("DELETE FROM users WHERE username = ?", (db_user,))
                    
            conn.commit()
            print(f"[Sync Users] Đã đồng bộ tài khoản SQL với danh sách Web. Usernames: {frontend_usernames}")
        except Exception as e:
            print(f"[Sync Users Error] Không thể đồng bộ bảng users: {e}")
            
    if "apiKeys" in body:
        save_kv("fg_api_keys", body["apiKeys"])
    if "settings" in body:
        save_kv("fg_settings", body["settings"])
    return {"ok": True}



PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEDIA_DIR = PROJECT_ROOT / "data" / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")
app.mount("/", StaticFiles(directory=str(WEB_ROOT), html=True), name="static")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FallGuard dashboard + AI API server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--config", default="configs/default.yaml")
    return parser.parse_args()


def main() -> None:
    import uvicorn

    args = parse_args()
    pipeline.config_path = args.config
    print(f"FallGuard: http://{args.host}:{args.port}/")
    print("Dang nhap: admin / nckh2025")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
