from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

_engine = None


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        return


def auth_storage_mode() -> str:
    _load_env()
    forced = os.environ.get("AUTH_STORAGE", "auto").strip().lower()
    if forced == "yaml":
        return "yaml"
    if forced == "database":
        return "database"
    url = os.environ.get("DATABASE_URL", "").strip()
    return "database" if url else "yaml"


def use_cloud_storage() -> bool:
    return auth_storage_mode() == "database"


def get_engine():
    global _engine
    if _engine is None:
        from sqlalchemy import create_engine

        _load_env()
        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            raise RuntimeError("DATABASE_URL chua duoc cau hinh.")
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def reset_engine_for_tests() -> None:
    global _engine
    _engine = None


def cloud_health() -> dict[str, Any]:
    if not use_cloud_storage():
        return {"enabled": False, "status": "local"}
    try:
        from sqlalchemy import text

        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"enabled": True, "status": "ok"}
    except Exception as exc:
        return {"enabled": True, "status": "error", "detail": str(exc)}
