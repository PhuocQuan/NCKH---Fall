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
    if "@" in user:
        user = user.split("@", 1)[0]
        
    from src.core.database import verify_user, create_session
    
    if not verify_user(user, password):
        raise ValueError("Sai tai khoan hoac mat khau.")
        
    token = create_session(user, ttl_seconds=TOKEN_TTL_SECONDS)
    return token


def verify_token(token: str | None) -> str | None:
    if not token:
        return None
    from src.core.database import verify_session_token
    return verify_session_token(token)


def logout(token: str | None) -> None:
    if token:
        from src.core.database import delete_session
        delete_session(token)

