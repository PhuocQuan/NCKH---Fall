"""Xác thực đơn giản cho dashboard NCKH."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

VALID_USERS = {
    "admin": "nckh2025",
    "manager": "nckh2025",
    "nurse": "nckh2025",
    "family": "nckh2025",
    "guest": "nckh2025",
}

TOKEN_TTL_SECONDS = 60 * 60 * 12


@dataclass
class Session:
    username: str
    expires_at: float


_sessions: dict[str, Session] = {}


def login(username: str, password: str) -> str:
    user = username.strip().lower()
    email = user
    if "@" not in email:
        email = f"{email}@nckh.vn"
        
    try:
        from src.web.backend.db import get_db_client
        with get_db_client() as client:
            result = client.execute("SELECT password FROM users WHERE email = ? AND status = 'Đang hoạt động'", [email])
        
        if not result.rows:
            raise ValueError("Sai tài khoản hoặc mật khẩu, hoặc tài khoản đã bị khóa.")
            
        db_pwd = result.rows[0][0]
        if db_pwd != password:
            raise ValueError("Sai tài khoản hoặc mật khẩu.")
            
        logged_in_user = email
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise exc
        print(f"[Auth Error] Database check failed, falling back to local auth: {exc}")
        prefix = user.split("@", 1)[0] if "@" in user else user
        if VALID_USERS.get(prefix) != password:
            raise ValueError("Sai tai khoan hoac mat khau.")
        logged_in_user = f"{prefix}@nckh.vn"

    token = secrets.token_urlsafe(32)
    _sessions[token] = Session(username=logged_in_user, expires_at=time.time() + TOKEN_TTL_SECONDS)
    return token


def verify_token(token: str | None) -> str | None:
    if not token:
        return None
    session = _sessions.get(token)
    if not session:
        return None
    if session.expires_at < time.time():
        _sessions.pop(token, None)
        return None
    return session.username


def logout(token: str | None) -> None:
    if token:
        _sessions.pop(token, None)
