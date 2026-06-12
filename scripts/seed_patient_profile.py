"""Tao bang user_patient_profiles va ho so mau tuy chon tren Supabase."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

SQL = """
CREATE TABLE IF NOT EXISTS user_patient_profiles (
  username            VARCHAR(64) PRIMARY KEY,
  full_name           VARCHAR(128) NOT NULL,
  initials            VARCHAR(8),
  age_label           VARCHAR(32),
  room_label          VARCHAR(64),
  date_of_birth       VARCHAR(32),
  blood_type          VARCHAR(16),
  medical_conditions  TEXT,
  emergency_contact   VARCHAR(128),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def main() -> int:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        print("Thieu DATABASE_URL trong .env")
        return 1
    engine = create_engine(url)
    username = os.environ.get("PROFILE_USERNAME", "admin").strip() or "admin"
    full_name = os.environ.get("PROFILE_FULL_NAME", "Người được giám sát").strip() or "Người được giám sát"
    with engine.begin() as conn:
        conn.execute(text(SQL))
        conn.execute(
            text(
                """
                INSERT INTO user_patient_profiles (
                  username, full_name, initials, age_label, room_label,
                  date_of_birth, blood_type, medical_conditions, emergency_contact
                ) VALUES
                  (:username, :full_name, 'HS', 'Chưa nhập', 'Chưa nhập',
                   'Chưa nhập', 'Chưa nhập', 'Chưa nhập', 'Chưa nhập')
                ON CONFLICT (username) DO UPDATE SET
                  full_name = EXCLUDED.full_name,
                  initials = EXCLUDED.initials,
                  age_label = EXCLUDED.age_label,
                  room_label = EXCLUDED.room_label,
                  date_of_birth = EXCLUDED.date_of_birth,
                  blood_type = EXCLUDED.blood_type,
                  medical_conditions = EXCLUDED.medical_conditions,
                  emergency_contact = EXCLUDED.emergency_contact
                """
            ),
            {"username": username, "full_name": full_name},
        )
    print(f"Da seed user_patient_profiles OK cho tai khoan {username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
