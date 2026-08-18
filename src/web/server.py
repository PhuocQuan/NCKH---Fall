"""FastAPI server: entry point loading domain-based routers and static files."""

from __future__ import annotations

import argparse
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

app = FastAPI(title="FallGuard AI API", version="1.0.0")

# Database constraint exception handling
@app.exception_handler(LibsqlError)
def libsql_exception_handler(request: Request, exc: LibsqlError):
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


# CORS Configuration
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
    response = await call_next(request)
    if request.url.path.endswith((".html", ".js", ".css")) or request.url.path == "/":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# Include Routers
app.include_router(shared_router)
app.include_router(admin_router)
app.include_router(user_router)

# Mount Static Directories
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")
app.mount("/", StaticFiles(directory=str(WEB_ROOT), html=True), name="static")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FallGuard dashboard + AI API server.")
    parser.add_argument("--host", default="0.0.0.0")
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
