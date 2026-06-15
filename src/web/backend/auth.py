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
    if VALID_USERS.get(user) != password:
        raise ValueError("Sai tai khoan hoac mat khau.")
    token = secrets.token_urlsafe(32)
    _sessions[token] = Session(username=user, expires_at=time.time() + TOKEN_TTL_SECONDS)
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
