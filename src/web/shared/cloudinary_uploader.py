"""Module to handle Cloudinary cloud uploads using credentials from configs/configs/db.json.

File: src/web/shared/cloudinary_uploader.py
Chức năng chính: Tải hình ảnh/video lên dịch vụ Cloudinary để lưu trữ đám mây.
Dùng để lưu ảnh avatar hoặc video bằng chứng té ngã.
"""
from __future__ import annotations

import json
from pathlib import Path

DB_CONFIG_PATH = Path("configs/db.json")
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_cloudinary_config() -> dict:
    possible_paths = [
        DB_CONFIG_PATH,
        PROJECT_ROOT / "configs" / "db.json"
    ]
    for p in possible_paths:
        if p.exists():
            try:
                with p.open(encoding="utf-8") as f:
                    data = json.load(f)
                    cfg = data.get("cloudinary", {})
                    if cfg and cfg.get("cloud_name"):
                        return cfg
            except Exception:
                pass
    return {}


def upload_to_cloudinary(file_path: str) -> str | None:
    config = load_cloudinary_config()
    cloud_name = config.get("cloud_name")
    api_key = config.get("api_key")
    api_secret = config.get("api_secret")

    if not cloud_name or cloud_name == "YOUR_CLOUD_NAME":
        return None

    try:
        import cloudinary
        import cloudinary.uploader
        
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True
        )
        
        resource_type = "video" if file_path.lower().endswith((".mp4", ".avi", ".mov", ".mkv")) else "image"

        print(f"[Cloudinary] Uploading {file_path} (resource_type={resource_type})...")
        if resource_type == "video":
            # Tự động transcode video sang chuẩn HTML5 H.264 để xem được trên tất cả trình duyệt web
            res = cloudinary.uploader.upload(
                file_path,
                resource_type="video",
                video_codec="h264",
            )
        else:
            res = cloudinary.uploader.upload(file_path, resource_type="image")

        secure_url = res.get("secure_url")
        print(f"[Cloudinary] Upload success: {secure_url}")
        return secure_url
    except Exception as e:
        print(f"[Cloudinary] Lỗi upload: {e}")
        return None



def delete_from_cloudinary(url: str) -> bool:
    if not url:
        return False
    config = load_cloudinary_config()
    cloud_name = config.get("cloud_name")
    api_key = config.get("api_key")
    api_secret = config.get("api_secret")

    if not cloud_name or cloud_name == "YOUR_CLOUD_NAME":
        return False

    try:
        import cloudinary
        import cloudinary.uploader
        
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True
        )
        
        parts = url.split('/')
        if "upload" in parts:
            idx = parts.index("upload")
            remaining = parts[idx+2:]  # skip upload and version (e.g. v1781660150)
            public_id_with_ext = "/".join(remaining)
            public_id = public_id_with_ext.rsplit('.', 1)[0]
            
            resource_type = "video" if url.lower().endswith((".mp4", ".avi", ".mov", ".mkv")) else "image"
            
            print(f"[Cloudinary] Deleting resource {public_id} ({resource_type})...")
            res = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
            print(f"[Cloudinary] Delete result: {res}")
            return res.get("result") == "ok"
    except Exception as e:
        print(f"[Cloudinary] Lỗi xóa: {e}")
    return False

