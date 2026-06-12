from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from src.camera_registry import (
    CameraEntry,
    create_camera,
    delete_camera,
    filter_cameras_for_user,
    load_cameras,
    resolve_start_source,
    save_cameras,
    suggest_camera_id,
    update_camera,
    user_can_access_camera,
)


@pytest.fixture
def cameras_path(tmp_path: Path) -> Path:
    return tmp_path / "cameras.yaml"


def test_load_empty_when_missing(cameras_path: Path) -> None:
    assert load_cameras(cameras_path) == []


def test_create_update_delete_roundtrip(cameras_path: Path) -> None:
    save_cameras(
        [CameraEntry(id="CAM-01", name="A", room="R1", source="0", enabled=True)],
        cameras_path,
    )
    created = create_camera(
        camera_id="CAM-99",
        name="Phòng tắm",
        room="Phòng 101",
        source="rtsp://192.168.1.50/stream",
        enabled=True,
        path=cameras_path,
    )
    assert created.id == "CAM-99"

    updated = update_camera(
        "CAM-99",
        name="Phòng tắm 2",
        room="Phòng 102",
        source="0",
        enabled=False,
        path=cameras_path,
    )
    assert updated.name == "Phòng tắm 2"
    assert updated.enabled is False

    delete_camera("CAM-99", path=cameras_path)
    assert all(camera.id != "CAM-99" for camera in load_cameras(cameras_path))

    delete_camera("CAM-01", path=cameras_path)
    assert load_cameras(cameras_path) == []


def test_resolve_start_source_prefers_camera_id(cameras_path: Path) -> None:
    save_cameras(
        [
            CameraEntry(id="CAM-01", name="A", room="R1", source="0", enabled=True),
            CameraEntry(id="CAM-02", name="B", room="R2", source="9", enabled=True),
        ],
        cameras_path,
    )
    source, camera_id = resolve_start_source(camera_id="CAM-02", path=cameras_path)
    assert source == "9"
    assert camera_id == "CAM-02"


def test_suggest_camera_id(cameras_path: Path) -> None:
    save_cameras(
        [CameraEntry(id="CAM-01", name="A", room="R", source="0", enabled=True)],
        cameras_path,
    )
    assert suggest_camera_id(load_cameras(cameras_path)) == "CAM-02"


def test_concurrent_create_assigns_unique_ids(cameras_path: Path) -> None:
    def add_camera(index: int) -> str:
        entry = create_camera(
            camera_id=f"CAM-{index:02d}",
            name=f"Phong {index}",
            room="Tang 1",
            source="0",
            enabled=True,
            path=cameras_path,
        )
        return entry.id

    with ThreadPoolExecutor(max_workers=5) as pool:
        ids = list(pool.map(add_camera, range(1, 6)))

    assert len(set(ids)) == 5
    assert len(load_cameras(cameras_path)) == 5


def test_filter_cameras_by_assigned_user(cameras_path: Path) -> None:
    create_camera(
        camera_id="CAM-01",
        name="Phong ngu",
        room="101",
        source="0",
        assigned_users=["caregiver.lan"],
        path=cameras_path,
    )
    create_camera(
        camera_id="CAM-02",
        name="Phong khach",
        room="102",
        source="1",
        assigned_users=["family.tuan"],
        path=cameras_path,
    )
    all_cameras = load_cameras(cameras_path)
    lan_cameras = filter_cameras_for_user(all_cameras, username="caregiver.lan", is_admin=False)
    assert [camera.id for camera in lan_cameras] == ["CAM-01"]
    assert user_can_access_camera("CAM-01", username="caregiver.lan", is_admin=False, path=cameras_path)
    assert not user_can_access_camera("CAM-02", username="caregiver.lan", is_admin=False, path=cameras_path)
    admin_cameras = filter_cameras_for_user(all_cameras, username="admin", is_admin=True)
    assert len(admin_cameras) == 2
