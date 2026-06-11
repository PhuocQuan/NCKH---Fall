from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.access_requests import create_request, list_requests, update_request_status
from src.auth import (
    create_token,
    find_user,
    get_token_username,
    is_admin_username,
    load_auth_config,
    revoke_token,
    verify_login,
    verify_token,
)
from src.camera_registry import (
    create_camera,
    delete_camera,
    list_cameras_payload,
    resolve_start_source,
    suggest_camera_id,
    update_camera,
)
from src.mobile_service import MobileMonitorService
from src.ui_theme import ui_config_payload
from src.user_settings import UserSettings, load_user_settings, save_user_settings

MOBILE_WEB_DIR = Path(__file__).resolve().parent.parent / "mobile" / "web"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000

monitor = MobileMonitorService()
bearer_scheme = HTTPBearer(auto_error=False)
app = FastAPI(
    title="NCKH Fall Detection Mobile API",
    version="1.1.0",
    description="API + web mobile cho he thong phat hien te nga.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartRequest(BaseModel):
    source: str | int | None = None
    camera_id: str | None = None
    config: str = "configs/default.yaml"


class CameraRequest(BaseModel):
    id: str | None = None
    name: str
    room: str
    source: str
    enabled: bool = True


class ControlResponse(BaseModel):
    ok: bool = True
    status: dict[str, Any]


class SettingsRequest(BaseModel):
    profile: str = "default"
    alert_after_seconds: float = 10.0
    draw_landmarks: bool = True
    snapshot_on_alert: bool = True


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    ok: bool = True
    token: str
    username: str
    full_name: str = ""
    role: str = "caregiver"
    is_admin: bool = False
    expires_in_hours: int = 24


class AccessRequestCreate(BaseModel):
    full_name: str
    email: str = ""
    phone: str = ""
    role: str = "caregiver"
    message: str = ""


class AccessRequestReview(BaseModel):
    status: str
    review_note: str = ""


def _extract_token(
    credentials: HTTPAuthorizationCredentials | None,
    token_query: str | None,
) -> str | None:
    if credentials is not None:
        return credentials.credentials
    return token_query


def require_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    token_query: Annotated[str | None, Query(alias="token")] = None,
) -> str:
    token = _extract_token(credentials, token_query)
    if not verify_token(token):
        raise HTTPException(status_code=401, detail="Chua dang nhap hoac het han phien.")
    return token


def require_admin(token: Annotated[str, Depends(require_auth)]) -> str:
    username = get_token_username(token)
    if not is_admin_username(username):
        raise HTTPException(status_code=403, detail="Chi admin moi duoc phep.")
    return token


def _status_payload() -> dict[str, Any]:
    status = monitor.get_status()
    settings = load_user_settings()
    status["profile"] = settings.profile
    status["alert_after_seconds"] = settings.alert_after_seconds
    return status


@app.get("/api/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "NCKH Fall Detection",
        "version": app.version,
        "auth_mode": "admin_provisioned",
    }


@app.post("/api/access-requests")
def submit_access_request(body: AccessRequestCreate) -> dict[str, Any]:
    try:
        entry = create_request(
            full_name=body.full_name,
            email=body.email,
            phone=body.phone,
            role=body.role,
            message=body.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "ok": True,
        "request": entry.to_dict(),
        "message": "Da gui yeu cau. Admin se lien he khi duyet tai khoan.",
    }


@app.get("/api/access-requests")
def get_access_requests(
    _admin: Annotated[str, Depends(require_admin)],
    status: str | None = None,
) -> dict[str, Any]:
    requests = [item.to_dict() for item in list_requests(status=status)]
    return {"requests": requests, "pending_count": sum(1 for r in requests if r["status"] == "pending")}


@app.patch("/api/access-requests/{request_id}")
def review_access_request(
    request_id: str,
    body: AccessRequestReview,
    _admin: Annotated[str, Depends(require_admin)],
) -> dict[str, Any]:
    try:
        entry = update_request_status(
            request_id,
            status=body.status,
            review_note=body.review_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "request": entry.to_dict()}


@app.post("/api/auth/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    user = verify_login(body.username, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Sai tai khoan hoac mat khau.")
    username = user.username
    return LoginResponse(
        token=create_token(username),
        username=username,
        full_name=user.full_name or username,
        role=user.role,
        is_admin=is_admin_username(username),
    )


@app.get("/api/auth/me")
def auth_me(token: Annotated[str, Depends(require_auth)]) -> dict[str, Any]:
    username = get_token_username(token) or ""
    user = find_user(username)
    if user is None:
        raise HTTPException(status_code=401, detail="Phien khong hop le.")
    return {
        "username": user.username,
        "full_name": user.full_name or user.username,
        "role": user.role,
        "is_admin": is_admin_username(username),
        "status": "authenticated",
    }


@app.post("/api/auth/logout")
def logout(token: Annotated[str, Depends(require_auth)]) -> dict[str, bool]:
    revoke_token(token)
    return {"ok": True}


@app.get("/api/status")
def get_status(_token: Annotated[str, Depends(require_auth)]) -> dict[str, Any]:
    return _status_payload()


@app.get("/api/ui-config")
def get_ui_config(_token: Annotated[str, Depends(require_auth)]) -> dict[str, Any]:
    return ui_config_payload()


@app.get("/api/settings")
def get_settings(_token: Annotated[str, Depends(require_auth)]) -> dict[str, Any]:
    settings = load_user_settings()
    return {
        "profile": settings.profile,
        "alert_after_seconds": settings.alert_after_seconds,
        "draw_landmarks": settings.draw_landmarks,
        "snapshot_on_alert": settings.snapshot_on_alert,
    }


@app.put("/api/settings")
def put_settings(
    body: SettingsRequest,
    _token: Annotated[str, Depends(require_auth)],
) -> dict[str, Any]:
    settings = UserSettings(
        profile=body.profile,
        alert_after_seconds=max(1.0, float(body.alert_after_seconds)),
        draw_landmarks=body.draw_landmarks,
        snapshot_on_alert=body.snapshot_on_alert,
    )
    save_user_settings(settings)
    return {"ok": True, "settings": get_settings(_token)}


@app.get("/api/events")
def get_events(
    _token: Annotated[str, Depends(require_auth)],
    limit: int = 20,
) -> dict[str, Any]:
    safe_limit = max(1, min(limit, 100))
    return {"events": monitor.read_events(limit=safe_limit)}


@app.get("/api/events/csv")
def download_events_csv(_token: Annotated[str, Depends(require_auth)]) -> FileResponse:
    from src.config import load_config

    config = load_config("configs/default.yaml")
    path = Path(config.app.event_log_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Chua co file events.csv.")
    return FileResponse(path, media_type="text/csv", filename=path.name)


@app.get("/api/cameras")
def list_cameras(_token: Annotated[str, Depends(require_auth)]) -> dict[str, Any]:
    return list_cameras_payload()


@app.get("/api/cameras/suggest-id")
def suggest_id(_admin: Annotated[str, Depends(require_admin)]) -> dict[str, str]:
    return {"id": suggest_camera_id()}


@app.post("/api/cameras")
def add_camera(
    body: CameraRequest,
    _admin: Annotated[str, Depends(require_admin)],
) -> dict[str, Any]:
    try:
        camera = create_camera(
            camera_id=body.id,
            name=body.name.strip(),
            room=body.room.strip(),
            source=body.source.strip(),
            enabled=body.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "camera": camera.to_dict()}


@app.put("/api/cameras/{camera_id}")
def put_camera(
    camera_id: str,
    body: CameraRequest,
    _admin: Annotated[str, Depends(require_admin)],
) -> dict[str, Any]:
    try:
        camera = update_camera(
            camera_id,
            name=body.name.strip(),
            room=body.room.strip(),
            source=body.source.strip(),
            enabled=body.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "camera": camera.to_dict()}


@app.delete("/api/cameras/{camera_id}")
def remove_camera(
    camera_id: str,
    _admin: Annotated[str, Depends(require_admin)],
) -> dict[str, bool]:
    try:
        delete_camera(camera_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@app.post("/api/control/start", response_model=ControlResponse)
def start_monitor(
    body: StartRequest,
    _token: Annotated[str, Depends(require_auth)],
) -> ControlResponse:
    try:
        source, camera_id = resolve_start_source(
            camera_id=body.camera_id,
            source=body.source,
        )
        status = monitor.start(source, config_path=body.config, camera_id=camera_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ControlResponse(status=status)


@app.post("/api/control/stop", response_model=ControlResponse)
def stop_monitor(_token: Annotated[str, Depends(require_auth)]) -> ControlResponse:
    return ControlResponse(status=monitor.stop())


@app.post("/api/control/reset", response_model=ControlResponse)
def reset_monitor(_token: Annotated[str, Depends(require_auth)]) -> ControlResponse:
    if not monitor.is_running():
        raise HTTPException(status_code=409, detail="Monitor chua chay.")
    return ControlResponse(status=monitor.reset())


@app.get("/api/camera/frame.jpg")
def camera_frame(_token: Annotated[str, Depends(require_auth)]) -> Response:
    if not monitor.is_running():
        raise HTTPException(status_code=409, detail="Monitor chua chay.")
    jpeg = monitor.get_latest_jpeg()
    if jpeg is None:
        raise HTTPException(status_code=503, detail="Chua co khung hinh.")
    return Response(content=jpeg, media_type="image/jpeg")


@app.get("/api/camera/stream.mjpg")
def camera_stream(_token: Annotated[str, Depends(require_auth)]) -> StreamingResponse:
    if not monitor.is_running():
        raise HTTPException(status_code=409, detail="Monitor chua chay.")

    def generate():
        yield from monitor.iter_mjpeg()

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/snapshots/latest")
def latest_snapshot(_token: Annotated[str, Depends(require_auth)]) -> FileResponse:
    path = monitor.latest_snapshot_path()
    if path is None:
        raise HTTPException(status_code=404, detail="Chua co snapshot.")
    return FileResponse(path, media_type="image/jpeg", filename=path.name)


@app.get("/api/snapshots/{name}")
def get_snapshot(name: str, _token: Annotated[str, Depends(require_auth)]) -> FileResponse:
    try:
        path = monitor.snapshot_path(name)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, media_type="image/jpeg", filename=path.name)


@app.websocket("/ws/status")
async def status_socket(websocket: WebSocket, token: str | None = None) -> None:
    if not verify_token(token):
        await websocket.close(code=4401, reason="Chua dang nhap")
        return
    await websocket.accept()
    try:
        while True:
            await websocket.send_text(json.dumps(_status_payload(), ensure_ascii=False))
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return


if MOBILE_WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(MOBILE_WEB_DIR), html=True), name="mobile-web")


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Chay API + web mobile cho NCKH Fall Detection.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
