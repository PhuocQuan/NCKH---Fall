from __future__ import annotations

import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_AUTH_PATH = Path("configs/auth.yaml")
TOKEN_TTL_SECONDS = 24 * 60 * 60
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "nckh2025"

_tokens: dict[str, float] = {}
_token_owners: dict[str, str] = {}


@dataclass(frozen=True)
class AuthUser:
    username: str
    password: str
    role: str = "caregiver"
    full_name: str = ""
    enabled: bool = True

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "role": self.role,
            "full_name": self.full_name or self.username,
            "enabled": self.enabled,
        }


@dataclass(frozen=True)
class AuthConfig:
    admin: AuthUser
    users: tuple[AuthUser, ...]

    def all_users(self) -> tuple[AuthUser, ...]:
        return (self.admin,) + self.users


def load_auth_config(path: str | Path = DEFAULT_AUTH_PATH) -> AuthConfig:
    auth_path = Path(path)
    if auth_path.exists():
        import yaml

        data = yaml.safe_load(auth_path.read_text(encoding="utf-8")) or {}
        if isinstance(data, dict):
            admin = AuthUser(
                username=str(data.get("username", DEFAULT_USERNAME)).strip(),
                password=str(data.get("password", DEFAULT_PASSWORD)),
                role="admin",
                full_name=str(data.get("admin_name", "Quản trị viên")).strip(),
                enabled=True,
            )
            users: list[AuthUser] = []
            for raw in data.get("users", []) or []:
                if not isinstance(raw, dict):
                    continue
                users.append(
                    AuthUser(
                        username=str(raw.get("username", "")).strip(),
                        password=str(raw.get("password", "")),
                        role=str(raw.get("role", "caregiver")).strip() or "caregiver",
                        full_name=str(raw.get("full_name", "")).strip(),
                        enabled=bool(raw.get("enabled", True)),
                    )
                )
            return AuthConfig(admin=admin, users=tuple(u for u in users if u.username))
    return AuthConfig(
        admin=AuthUser(
            username=os.environ.get("NCKH_AUTH_USER", DEFAULT_USERNAME).strip(),
            password=os.environ.get("NCKH_AUTH_PASS", DEFAULT_PASSWORD),
            role="admin",
            full_name="Quản trị viên",
            enabled=True,
        ),
        users=(),
    )


def load_credentials(path: str | Path = DEFAULT_AUTH_PATH) -> AuthUser:
    return load_auth_config(path).admin


def find_user(username: str, config: AuthConfig | None = None) -> AuthUser | None:
    cfg = config or load_auth_config()
    target = username.strip()
    for user in cfg.all_users():
        if secrets.compare_digest(target, user.username):
            return user
    return None


def verify_login(username: str, password: str, config: AuthConfig | None = None) -> AuthUser | None:
    user = find_user(username, config)
    if user is None or not user.enabled:
        return None
    if secrets.compare_digest(password, user.password):
        return user
    return None


def is_admin_username(username: str | None) -> bool:
    if not username:
        return False
    admin = load_auth_config().admin
    return secrets.compare_digest(username.strip(), admin.username)


def create_token(username: str) -> str:
    token = secrets.token_urlsafe(32)
    _tokens[token] = time.monotonic() + TOKEN_TTL_SECONDS
    _token_owners[token] = username.strip()
    return token


def verify_token(token: str | None) -> bool:
    if not token:
        return False
    expiry = _tokens.get(token)
    if expiry is None:
        return False
    if time.monotonic() > expiry:
        _tokens.pop(token, None)
        _token_owners.pop(token, None)
        return False
    return True


def get_token_username(token: str | None) -> str | None:
    if not verify_token(token):
        return None
    return _token_owners.get(token or "")


def revoke_token(token: str | None) -> None:
    if token:
        _tokens.pop(token, None)
        _token_owners.pop(token, None)


def clear_tokens_for_tests() -> None:
    _tokens.clear()
    _token_owners.clear()
