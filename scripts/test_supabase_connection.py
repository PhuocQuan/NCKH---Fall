"""Kiem tra ket noi Supabase va xem bang users."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()


def main() -> int:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        print("Thieu DATABASE_URL trong .env")
        print("Xem huong dan: docs/SUPABASE_SETUP.md")
        return 1

    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version()")).scalar()
            users = conn.execute(
                text("SELECT username, role, is_admin, enabled FROM users ORDER BY id")
            ).fetchall()
        print("Ket noi OK")
        print("PostgreSQL:", (version or "")[:60], "...")
        print("Users:", users if users else "(chua co — chay create_admin_user.py)")
        return 0
    except Exception as exc:
        print("Loi ket noi:", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
