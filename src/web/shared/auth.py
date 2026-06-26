"""Xác thực đơn giản cho dashboard NCKH sử dụng JWT."""

from __future__ import annotations

import time
import jwt

VALID_USERS = {
    "admin": "nckh2025",
    "manager": "nckh2025",
    "nurse": "nckh2025",
    "family": "nckh2025",
    "guest": "nckh2025",
}

TOKEN_TTL_SECONDS = 60 * 60 * 12
JWT_SECRET_KEY = "nckh-fallguard-secret-key-2026"
JWT_ALGORITHM = "HS256"


def login(username: str, password: str) -> str:
    user = username.strip().lower()
    email = user
    if "@" not in email:
        email = f"{email}@nckh.vn"
        
    try:
        from src.web.shared.db import get_db_client
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

    # Tạo JWT token thay vì session lưu trên RAM
    payload = {
        "sub": logged_in_user,
        "exp": int(time.time() + TOKEN_TTL_SECONDS)
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def verify_token(token: str | None) -> str | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        print("[Auth] JWT Token đã hết hạn.")
        return None
    except jwt.InvalidTokenError:
        print("[Auth] JWT Token không hợp lệ.")
        return None


def logout(token: str | None) -> None:
    # JWT là Stateless nên logout phía Server không cần thao tác gì
    pass
