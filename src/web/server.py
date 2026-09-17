"""
File: src/web/server.py
Chức năng chính: Khởi động máy chủ Web API (Backend) bằng FastAPI.
File này cấu hình API, kết nối các luồng (routers), xử lý lỗi Database và phục vụ file tĩnh (HTML, CSS, JS).

File liên kết:
- Gọi bởi: Lệnh chạy trong terminal (`python -m src.web.server`).
- Chạy các route từ: src.web.shared.router, src.web.admin.router, src.web.user.router.
- Liên kết với Frontend: Phục vụ các file trong thư mục `src/web/` ra đường dẫn `/`.
"""

from __future__ import annotations

import argparse
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from libsql_client.client import LibsqlError

from src.web.shared.pipeline import pipeline
from src.web.shared.router import router as shared_router
from src.web.admin.router import router as admin_router
from src.web.user.router import router as user_router

WEB_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = WEB_ROOT.parents[1]
MEDIA_DIR = PROJECT_ROOT / "data" / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


_starting_lock = threading.Lock()


def _auto_start_monitoring() -> None:
    """Tự động khởi chạy AI giám sát ngầm 24/7 ngay khi server bật."""
    if not _starting_lock.acquire(blocking=False):
        return
    try:
        if pipeline.is_running():
            return
        time.sleep(1.0)
        from src.web.shared.db import get_db_client
        source = "0"
        camera_id = "CAM-LOCAL"
        try:
            with get_db_client() as client:
                res = client.execute("SELECT id, rtsp, status FROM cameras WHERE status = 'online' ORDER BY id ASC LIMIT 1")
                if res.rows:
                    camera_id = str(res.rows[0][0])
                    rtsp = res.rows[0][1]
                    if rtsp and str(rtsp).strip():
                        source = str(rtsp).strip()
                else:
                    res2 = client.execute("SELECT id, rtsp FROM cameras ORDER BY id ASC LIMIT 1")
                    if res2.rows:
                        camera_id = str(res2.rows[0][0])
                        rtsp = res2.rows[0][1]
                        if rtsp and str(rtsp).strip():
                            source = str(rtsp).strip()
        except Exception as db_err:
            print(f"[Auto-Start AI] Khong the truy van camera tu DB ({db_err}), dung mac dinh.")
        
        print(f"[Auto-Start AI] 🚀 Khoi dong giam sat AI ngam 24/7 cho Camera: {camera_id} (Nguon: {source})...")
        pipeline.start(source=source, camera_id=camera_id)
        print(f"[Auto-Start AI] ✅ He thong AI dang hoat dong ngam: tu dong phat hien nguoi la, te nga!")
    except Exception as exc:
        print(f"[Auto-Start AI Error] Loi khoi dong pipeline ngam: {exc}")
    finally:
        _starting_lock.release()


def _watchdog_loop() -> None:
    """Tự động kiểm tra và hồi sinh pipeline AI nếu bị dừng đột ngột."""
    time.sleep(25.0)
    while True:
        try:
            if not pipeline.is_running():
                print("[Watchdog AI] 🔄 Phat hien pipeline AI ngam bi dung, tu dong khoi dong lai...")
                _auto_start_monitoring()
        except Exception as e:
            print(f"[Watchdog AI Warning] {e}")
        time.sleep(15.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=_auto_start_monitoring, daemon=True).start()
    threading.Thread(target=_watchdog_loop, daemon=True).start()
    yield
    print("[Shutdown] Dung pipeline AI...")
    pipeline.stop()


app = FastAPI(title="FallGuard AI API", version="1.0.6", lifespan=lifespan)

# Database constraint exception handling
@app.exception_handler(LibsqlError)
def libsql_exception_handler(request: Request, exc: LibsqlError):
    """
    Bắt và xử lý các lỗi trả về từ cơ sở dữ liệu Turso (LibsqlError).
    Ví dụ: Nếu bị trùng Email hoặc trùng ID Camera, trả về thông báo lỗi 400 (Bad Request)
    bằng Tiếng Việt thân thiện để hiển thị cho người dùng/app thay vì văng lỗi server.
    """
    from fastapi.responses import JSONResponse
    msg = exc.explanation
    if "UNIQUE constraint failed: users.email" in msg:
        detail = "Địa chỉ email này đã tồn tại trên hệ thống."
    elif "UNIQUE constraint failed: cameras.id" in msg:
        detail = "Mã camera này đã tồn tại trên hệ thống."
    else:
        detail = f"Lỗi cơ sở dữ liệu online: {msg}"
    return JSONResponse(
        status_code=400,
        content={"detail": detail},
    )


# Cấu hình CORS (Cross-Origin Resource Sharing)
# Cho phép các ứng dụng từ domain khác (ví dụ: Flutter App, Web) được phép gọi tới API của Server này.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Cache-control middleware for HTML, CSS, JS
@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    """
    Middleware: Xóa bộ nhớ đệm (Cache) của trình duyệt.
    Mỗi khi có yêu cầu file giao diện (.html, .js, .css), ép trình duyệt phải tải file mới nhất
    từ server để tránh tình trạng hiển thị code cũ khi ta vừa cập nhật giao diện.
    """
    response = await call_next(request)
    if request.url.path.endswith((".html", ".js", ".css")) or request.url.path == "/":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# Tích hợp (Include) các nhóm API từ các file router con
# - shared_router: Các API dùng chung (trạng thái hệ thống, login, lấy luồng camera).
# - admin_router: Các API dành riêng cho Admin (quản lý users, cameras).
# - user_router: Các API dành riêng cho User (cập nhật thông tin cá nhân).
app.include_router(shared_router)
app.include_router(admin_router)
app.include_router(user_router)

# Phục vụ (Mount) các file tĩnh (Frontend Web)
# Trỏ đường dẫn "/" tới thư mục src/web/ để hiển thị index.html khi vào web.
# Trỏ "/media" tới thư mục data/media để lưu/phát lại các video ghi hình người ngã.
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")
app.mount("/", StaticFiles(directory=str(WEB_ROOT), html=True), name="static")


def parse_args() -> argparse.Namespace:
    """Đọc cấu hình khi chạy bằng terminal (host, port, file yaml)."""
    parser = argparse.ArgumentParser(description="FallGuard dashboard + AI API server.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--config", default="configs/default.yaml")
    return parser.parse_args()


def main() -> None:
    """
    Hàm khởi động Uvicorn server (Máy chủ web hiệu năng cao dùng cho FastAPI).
    Cổng (port) mặc định là 8000.
    """
    import uvicorn

    args = parse_args()
    pipeline.config_path = args.config
    print(f"FallGuard: http://{args.host}:{args.port}/")
    print("Dang nhap: admin / nckh2025")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
