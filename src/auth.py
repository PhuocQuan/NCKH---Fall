from __future__ import annotations

import os
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_auth_lock = threading.Lock()
PROVISIONED_ROLES = frozenset({"caregiver", "family", "staff"})

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


def load_auth_config(path: str | Path | None = None) -> AuthConfig:
    auth_path = _resolve_auth_path(path)
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


def _resolve_auth_path(path: str | Path | None) -> Path:
    return Path(path) if path is not None else DEFAULT_AUTH_PATH


def load_credentials(path: str | Path | None = None) -> AuthUser:
    return load_auth_config(path).admin


def _config_to_yaml_dict(config: AuthConfig) -> dict[str, Any]:
    return {
        "username": config.admin.username,
        "password": config.admin.password,
        "admin_name": config.admin.full_name,
        "users": [
            {
                "username": user.username,
                "password": user.password,
                "full_name": user.full_name,
                "role": user.role,
                "enabled": user.enabled,
            }
            for user in config.users
        ],
    }


def save_auth_config(config: AuthConfig, path: str | Path | None = None) -> Path:
    import yaml

    auth_path = _resolve_auth_path(path)
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(_config_to_yaml_dict(config), sort_keys=False, allow_unicode=True)
    tmp_path = auth_path.with_suffix(".yaml.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(auth_path)
    return auth_path


def list_users_public(path: str | Path | None = None) -> list[dict[str, Any]]:
    config = load_auth_config(path)
    admin = config.admin
    return [
        {**admin.to_public_dict(), "is_admin": True},
        *[{**user.to_public_dict(), "is_admin": False} for user in config.users],
    ]


def _validate_provisioned_role(role: str) -> str:
    role_key = role.strip().lower()
    if role_key not in PROVISIONED_ROLES:
        raise ValueError("Vai tro khong hop le (caregiver, family, staff).")
    return role_key


def create_provisioned_user(
    *,
    username: str,
    password: str,
    full_name: str = "",
    role: str = "caregiver",
    enabled: bool = True,
    path: str | Path | None = None,
) -> AuthUser:
    name = username.strip()
    if not name:
        raise ValueError("Thieu ten dang nhap.")
    if not password:
        raise ValueError("Thieu mat khau.")
    if is_admin_username(name):
        raise ValueError("Khong the tao tai khoan trung ten admin.")
    role_key = _validate_provisioned_role(role)
    with _auth_lock:
        config = load_auth_config(path)
        if find_user(name, config) is not None:
            raise ValueError(f"Ten dang nhap da ton tai: {name}")
        user = AuthUser(
            username=name,
            password=password,
            role=role_key,
            full_name=full_name.strip() or name,
            enabled=enabled,
        )
        save_auth_config(AuthConfig(admin=config.admin, users=config.users + (user,)), path)
        return user


def update_provisioned_user(
    username: str,
    *,
    password: str | None = None,
    full_name: str | None = None,
    role: str | None = None,
    enabled: bool | None = None,
    path: str | Path | None = None,
) -> AuthUser:
    target = username.strip()
    with _auth_lock:
        config = load_auth_config(path)
        if is_admin_username(target):
            admin = config.admin
            updated_admin = AuthUser(
                username=admin.username,
                password=password if password else admin.password,
                role="admin",
                full_name=(full_name.strip() if full_name is not None else admin.full_name) or admin.username,
                enabled=True,
            )
            save_auth_config(AuthConfig(admin=updated_admin, users=config.users), path)
            return updated_admin

        updated_users: list[AuthUser] = []
        found: AuthUser | None = None
        for user in config.users:
            if user.username != target:
                updated_users.append(user)
                continue
            found = AuthUser(
                username=user.username,
                password=password if password else user.password,
                role=_validate_provisioned_role(role) if role is not None else user.role,
                full_name=(full_name.strip() if full_name is not None else user.full_name) or user.username,
                enabled=user.enabled if enabled is None else enabled,
            )
            updated_users.append(found)
        if found is None:
            raise ValueError(f"Khong tim thay nguoi dung: {target}")
        save_auth_config(AuthConfig(admin=config.admin, users=tuple(updated_users)), path)
        return found


def delete_provisioned_user(username: str, path: str | Path | None = None) -> None:
    target = username.strip()
    if is_admin_username(target):
        raise ValueError("Khong the xoa tai khoan admin.")
    with _auth_lock:
        config = load_auth_config(path)
        remaining = tuple(user for user in config.users if user.username != target)
        if len(remaining) == len(config.users):
            raise ValueError(f"Khong tim thay nguoi dung: {target}")
        save_auth_config(AuthConfig(admin=config.admin, users=remaining), path)


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
