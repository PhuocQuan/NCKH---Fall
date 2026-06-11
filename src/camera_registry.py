from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DEFAULT_CAMERAS_PATH = Path("configs/cameras.yaml")
_CAMERA_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")


@dataclass(frozen=True)
class CameraEntry:
    id: str
    name: str
    room: str
    source: str
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    return CameraEntry(
        id=camera_id,
        name=name,
        room=room,
        source=source,
        enabled=bool(raw.get("enabled", True)),
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
    settings_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
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


def list_cameras_payload(path: str | Path | None = None) -> dict[str, Any]:
    cameras = load_cameras(path)
    return {"cameras": [camera.to_dict() for camera in cameras]}


def create_camera(
    *,
    name: str,
    room: str,
    source: str,
    enabled: bool = True,
    camera_id: str | None = None,
    path: str | Path | None = None,
) -> CameraEntry:
    cameras = load_cameras(path)
    new_id = _normalize_id(camera_id) if camera_id else suggest_camera_id(cameras)
    if any(camera.id == new_id for camera in cameras):
        raise ValueError(f"Ma camera da ton tai: {new_id}")
    entry = _parse_entry(
        {"id": new_id, "name": name, "room": room, "source": source, "enabled": enabled}
    )
    cameras.append(entry)
    save_cameras(cameras, path)
    return entry


def update_camera(
    camera_id: str,
    *,
    name: str,
    room: str,
    source: str,
    enabled: bool,
    path: str | Path | None = None,
) -> CameraEntry:
    target = _normalize_id(camera_id)
    cameras = load_cameras(path)
    updated: list[CameraEntry] = []
    found: CameraEntry | None = None
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
            }
        )
        updated.append(found)
    if found is None:
        raise ValueError(f"Khong tim thay camera: {target}")
    save_cameras(updated, path)
    return found


def delete_camera(camera_id: str, path: str | Path | None = None) -> None:
    target = _normalize_id(camera_id)
    cameras = load_cameras(path)
    remaining = [camera for camera in cameras if camera.id != target]
    if len(remaining) == len(cameras):
        raise ValueError(f"Khong tim thay camera: {target}")
    save_cameras(remaining, path)


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
