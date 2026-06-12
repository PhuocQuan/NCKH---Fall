"""Tao tai khoan admin trong Supabase. Can file .env voi DATABASE_URL."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DEFAULT_USER = "admin"
DEFAULT_PASS = "nckh2025"
DEFAULT_NAME = "Quản trị viên NCKH"


def main() -> int:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        print("Thieu DATABASE_URL trong .env")
        return 1

    try:
        import bcrypt
    except ImportError:
        print("Chay: pip install bcrypt python-dotenv sqlalchemy psycopg2-binary")
        return 1

    username = os.environ.get("ADMIN_USERNAME", DEFAULT_USER).strip()
    password = os.environ.get("ADMIN_PASSWORD", DEFAULT_PASS)
    full_name = os.environ.get("ADMIN_FULL_NAME", DEFAULT_NAME).strip()
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    engine = create_engine(url)
    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM users WHERE username = :u"),
            {"u": username},
        ).first()
        if exists:
            conn.execute(
                text(
                    """
                    UPDATE users
                    SET password_hash = :h, full_name = :n, role = 'admin',
                        is_admin = TRUE, enabled = TRUE
                    WHERE username = :u
                    """
                ),
                {"h": password_hash, "n": full_name, "u": username},
            )
            print(f"Da cap nhat admin: {username}")
        else:
            conn.execute(
                text(
                    """
                    INSERT INTO users (username, password_hash, full_name, role, is_admin, enabled)
                    VALUES (:u, :h, :n, 'admin', TRUE, TRUE)
                    """
                ),
                {"u": username, "h": password_hash, "n": full_name},
            )
            print(f"Da tao admin: {username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
