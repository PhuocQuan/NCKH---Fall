"""Xác thực đơn giản cho dashboard NCKH sử dụng JWT."""

"""
File: src/web/shared/auth.py
Chức năng chính: Mã hóa và kiểm tra mã xác thực (JWT Token).
Giúp bảo mật API, đảm bảo chỉ người dùng đã đăng nhập mới gọi được API.
"""
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
JWT_SECRET_KEY = "nckh-fallguard-production-secret-key-secure-2026-v2-32byte-min-length"
JWT_ALGORITHM = "HS256"


def login(username: str, password: str, source: str = "web") -> str:
    user = username.strip().lower()
    email = user
    if "@" not in email:
        email = f"{email}@nckh.vn"
        
    try:
        from src.web.shared.db import get_db_client
        with get_db_client() as client:
            result = client.execute("SELECT password, status, role FROM users WHERE email = ?", [email])
        
        if not result.rows:
            raise ValueError("Sai tài khoản hoặc mật khẩu.")
            
        db_pwd = result.rows[0][0]
        db_status = result.rows[0][1]
        db_role = result.rows[0][2]
        
        if db_status != 'Đang hoạt động':
            raise ValueError("Tài khoản của bạn đã bị khóa.")
            
        if db_pwd != password:
            raise ValueError("Sai tài khoản hoặc mật khẩu.")
            
        if source == "app_fall" and db_role.lower() == "admin":
            raise ValueError("Tài khoản Admin không được hỗ trợ trên ứng dụng di động.")
            
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
    """Kiểm tra mã JWT có hợp lệ và chưa hết hạn không. Trả về email nếu đúng."""
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
