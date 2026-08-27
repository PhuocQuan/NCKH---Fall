"""
File: src/web/admin/router.py
Chức năng chính: Chứa các API dành riêng cho Quản trị viên (Admin) trên Dashboard.
Chịu trách nhiệm nhận HTTP Requests (GET, POST, PUT, DELETE) cho việc:
- Quản lý danh sách Người dùng (Users).
- Quản lý danh sách Camera.
- Quản lý Lịch sử (Logs) cảnh báo.
- Kiểm tra tính năng Gửi thông báo (Telegram/Zalo).

File liên kết (Ảnh hưởng / Bị ảnh hưởng):
- Gọi tới: src.web.admin.service.py (để xử lý logic dữ liệu).
- Middleware: Bắt buộc gọi `Depends(require_user)` từ src.web.shared.router.py để kiểm tra phân quyền.
"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.web.shared.router import require_user
import src.web.admin.service as service

router = APIRouter()


class UserDB(BaseModel):
    """Khuôn mẫu (Schema) quy định dữ liệu của một Người dùng khi truyền qua API."""
    email: str
    password: str | None = None
    name: str
    role: str
    status: str
    assignedCameras: list[str]
    phone: str | None = None
    age: int | None = None
    gender: str | None = None
    address: str | None = None


class CameraDB(BaseModel):
    """Khuôn mẫu (Schema) quy định dữ liệu của một Camera khi truyền qua API."""
    id: str
    name: str
    ip: str
    rtsp: str
    area: str
    target: str
    state: str
    status: str
    fps: int
    resolution: str
    threshold: int


class TestNotifRequest(BaseModel):
    channel: str


@router.get("/api/users")
def get_users(user: str = Depends(require_user)) -> list[dict[str, Any]]:
    return service.get_users()


@router.post("/api/users")
def create_user(body: UserDB, user: str = Depends(require_user)) -> dict[str, Any]:
    """API: Tạo người dùng mới. Chuyển thông tin từ request body sang service."""
    service.create_user(body.model_dump())
    return {"ok": True}


@router.put("/api/users/{email}")
def update_user(email: str, body: UserDB, user: str = Depends(require_user)) -> dict[str, Any]:
    """API: Cập nhật thông tin người dùng theo email."""
    service.update_user(email, body.model_dump())
    return {"ok": True}


@router.delete("/api/users/{email}")
def delete_user(email: str, user: str = Depends(require_user)) -> dict[str, Any]:
    """API: Xoá người dùng theo email."""
    service.delete_user(email)
    return {"ok": True}


@router.get("/api/cameras")
def get_cameras(user: str = Depends(require_user)) -> list[dict[str, Any]]:
    return service.get_cameras()


@router.post("/api/cameras")
def create_camera(body: CameraDB, user: str = Depends(require_user)) -> dict[str, Any]:
    """API: Thêm mới một camera vào hệ thống."""
    service.create_camera(body.model_dump(), user)
    return {"ok": True}


@router.put("/api/cameras/{id}")
def update_camera(id: str, body: CameraDB, user: str = Depends(require_user)) -> dict[str, Any]:
    """API: Cập nhật thông tin camera (Tên, IP, Luồng RTSP...)."""
    service.update_camera(id, body.model_dump(), user)
    return {"ok": True}


@router.delete("/api/cameras/{id}")
def delete_camera(id: str, user: str = Depends(require_user)) -> dict[str, Any]:
    """API: Xoá camera ra khỏi hệ thống."""
    service.delete_camera(id, user)
    return {"ok": True}


@router.get("/api/logs")
def list_logs(user: str = Depends(require_user)) -> dict[str, Any]:
    """API: Lấy lịch sử cảnh báo té ngã từ file sự kiện và SQLite."""
    try:
        logs_list = service.get_system_logs()
        return {"logs": logs_list}
    except Exception as e:
        print(f"[Database Error] Khong the doc logs tu Turso: {e}")
        return {"logs": []}


@router.get("/api/events")
def list_events(user: str = Depends(require_user)) -> dict[str, Any]:
    events = service.get_events()
    return {"events": events}


@router.post("/api/telegram/connect")
def telegram_connect(user: str = Depends(require_user)) -> dict[str, Any]:
    return service.connect_telegram()


@router.post("/api/notifications/test")
def test_notification(body: TestNotifRequest, user: str = Depends(require_user)) -> dict[str, Any]:
    try:
        service.test_notification(body.channel)
        return {"ok": True, "detail": f"Đã gửi tin nhắn cảnh báo thử nghiệm tới {body.channel}!"}
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err)) from val_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi gửi tin nhắn test: {e}") from e
