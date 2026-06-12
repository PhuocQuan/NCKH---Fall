from __future__ import annotations

import re
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_registry_lock = threading.Lock()

DEFAULT_CAMERAS_PATH = Path("configs/cameras.yaml")
_CAMERA_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")


@dataclass(frozen=True)
class CameraEntry:
    id: str
    name: str
    room: str
    source: str
    enabled: bool = True
    assigned_users: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["assigned_users"] = list(self.assigned_users)
        return data


def _normalize_id(camera_id: str) -> str:
    text = str(camera_id).strip().upper()
    if not _CAMERA_ID_RE.match(text):
        raise ValueError("Ma camera chi gom chu, so, gach ngang (2-32 ky tu).")
    return text


def _parse_entry(raw: dict[str, Any]) -> CameraEntry:
    camera_id = _normalize_id(str(raw.get("id", "")).strip())
    name = str(raw.get("name", "")).strip()
    room = str(raw.get("room", "")).strip()
    source = str(raw.get("source", "0")).strip()
    if not name:
        raise ValueError(f"Camera {camera_id}: thieu ten vi tri.")
    if not room:
        raise ValueError(f"Camera {camera_id}: thieu phong/khu vuc.")
    if not source:
        raise ValueError(f"Camera {camera_id}: thieu nguon (source).")
    assigned_raw = raw.get("assigned_users", []) or []
    assigned_users = tuple(
        sorted(
            {
                str(username).strip()
                for username in assigned_raw
                if isinstance(username, str) and str(username).strip()
            }
        )
    )
    return CameraEntry(
        id=camera_id,
        name=name,
        room=room,
        source=source,
        enabled=bool(raw.get("enabled", True)),
        assigned_users=assigned_users,
    )


def _resolve_path(path: str | Path | None) -> Path:
    return Path(path) if path is not None else DEFAULT_CAMERAS_PATH


def load_cameras(path: str | Path | None = None) -> list[CameraEntry]:
    import yaml

    settings_path = _resolve_path(path)
    if not settings_path.exists():
        return []

    data = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}
    items = data.get("cameras", data) if isinstance(data, dict) else data
    if not isinstance(items, list) or not items:
        return []

    return [_parse_entry(item) for item in items if isinstance(item, dict)]


def save_cameras(cameras: list[CameraEntry], path: str | Path | None = None) -> Path:
    import yaml

    settings_path = _resolve_path(path)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"cameras": [camera.to_dict() for camera in cameras]}
    text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    tmp_path = settings_path.with_suffix(".yaml.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(settings_path)
    return settings_path


def get_camera(camera_id: str, path: str | Path | None = None) -> CameraEntry | None:
    target = _normalize_id(camera_id)
    for camera in load_cameras(path):
        if camera.id == target:
            return camera
    return None


def suggest_camera_id(cameras: list[CameraEntry] | None = None) -> str:
    existing = {camera.id for camera in (cameras or load_cameras())}
    index = 1
    while True:
        candidate = f"CAM-{index:02d}"
        if candidate not in existing:
            return candidate
        index += 1


def filter_cameras_for_user(
    cameras: list[CameraEntry],
    *,
    username: str | None,
    is_admin: bool,
) -> list[CameraEntry]:
    if is_admin or not username:
        return cameras
    target = username.strip()
    return [
        camera
        for camera in cameras
        if target in camera.assigned_users
    ]


def user_can_access_camera(
    camera_id: str,
    *,
    username: str | None,
    is_admin: bool,
    path: str | Path | None = None,
) -> bool:
    if is_admin:
        return True
    if not username:
        return False
    camera = get_camera(camera_id, path)
    if camera is None:
        return False
    return username.strip() in camera.assigned_users


def list_cameras_payload(
    path: str | Path | None = None,
    *,
    username: str | None = None,
    is_admin: bool = False,
) -> dict[str, Any]:
    cameras = filter_cameras_for_user(
        load_cameras(path),
        username=username,
        is_admin=is_admin,
    )
    return {"cameras": [camera.to_dict() for camera in cameras]}


def _normalize_assigned_users(assigned_users: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    if not assigned_users:
        return ()
    return tuple(
        sorted(
            {
                str(username).strip()
                for username in assigned_users
                if str(username).strip()
            }
        )
    )


def _sync_camera_assignments_cloud(camera_id: str, assigned_users: tuple[str, ...]) -> None:
    try:
        from src.cloud_sync import sync_camera_assignments

        sync_camera_assignments(camera_id, list(assigned_users))
    except Exception:
        pass


def create_camera(
    *,
    name: str,
    room: str,
    source: str,
    enabled: bool = True,
    camera_id: str | None = None,
    assigned_users: list[str] | tuple[str, ...] | None = None,
    path: str | Path | None = None,
) -> CameraEntry:
    with _registry_lock:
        cameras = load_cameras(path)
        new_id = _normalize_id(camera_id) if camera_id else suggest_camera_id(cameras)
        if any(camera.id == new_id for camera in cameras):
            raise ValueError(f"Ma camera da ton tai: {new_id}")
        users = _normalize_assigned_users(assigned_users)
        entry = _parse_entry(
            {
                "id": new_id,
                "name": name,
                "room": room,
                "source": source,
                "enabled": enabled,
                "assigned_users": list(users),
            }
        )
        cameras.append(entry)
        save_cameras(cameras, path)
        _sync_camera_assignments_cloud(entry.id, entry.assigned_users)
        return entry


def update_camera(
    camera_id: str,
    *,
    name: str,
    room: str,
    source: str,
    enabled: bool,
    assigned_users: list[str] | tuple[str, ...] | None = None,
    path: str | Path | None = None,
) -> CameraEntry:
    with _registry_lock:
        target = _normalize_id(camera_id)
        cameras = load_cameras(path)
        updated: list[CameraEntry] = []
        found: CameraEntry | None = None
        users = _normalize_assigned_users(assigned_users)
        for camera in cameras:
            if camera.id != target:
                updated.append(camera)
                continue
            found = _parse_entry(
                {
                    "id": target,
                    "name": name,
                    "room": room,
                    "source": source,
                    "enabled": enabled,
                    "assigned_users": list(users),
                }
            )
            updated.append(found)
        if found is None:
            raise ValueError(f"Khong tim thay camera: {target}")
        save_cameras(updated, path)
        _sync_camera_assignments_cloud(found.id, found.assigned_users)
        return found


def delete_camera(camera_id: str, path: str | Path | None = None) -> None:
    with _registry_lock:
        target = _normalize_id(camera_id)
        cameras = load_cameras(path)
        remaining = [camera for camera in cameras if camera.id != target]
        if len(remaining) == len(cameras):
            raise ValueError(f"Khong tim thay camera: {target}")
        save_cameras(remaining, path)
        try:
            from src.cloud_sync import delete_camera_assignments

            delete_camera_assignments(target)
        except Exception:
            pass


def resolve_start_source(
    *,
    camera_id: str | None = None,
    source: str | int | None = None,
    path: str | Path | None = None,
) -> tuple[str | int, str | None]:
    if camera_id:
        camera = get_camera(camera_id, path)
        if camera is None:
            raise ValueError(f"Khong tim thay camera: {camera_id}")
        if not camera.enabled:
            raise ValueError(f"Camera {camera.id} dang tat.")
        return camera.source, camera.id
    if source is not None and str(source).strip() != "":
        return source, None
    enabled = [camera for camera in load_cameras(path) if camera.enabled]
    if not enabled:
        raise ValueError("Khong co camera nao duoc bat.")
    first = enabled[0]
    return first.source, first.id
