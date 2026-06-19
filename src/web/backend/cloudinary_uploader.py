"""Module to handle Cloudinary cloud uploads using credentials from configs/configs/db.json."""

from __future__ import annotations

import json
from pathlib import Path

DB_CONFIG_PATH = Path("configs/db.json")


def load_cloudinary_config() -> dict:
    if not DB_CONFIG_PATH.exists():
        return {}
    try:
        with DB_CONFIG_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
            return data.get("cloudinary", {})
    except Exception:
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
        
        print(f"[Cloudinary] Uploading {file_path}...")
        res = cloudinary.uploader.upload(file_path, resource_type=resource_type)
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

