-- Chay tren Supabase SQL Editor (neu da tao bang truoc do)
-- Moi dong la ho so ca nhan cua mot tai khoan dang nhap.
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

INSERT INTO user_patient_profiles (
  username, full_name, initials, age_label, room_label,
  date_of_birth, blood_type, medical_conditions, emergency_contact
) VALUES
  (
    'admin',
    'Người được giám sát',
    'HS',
    'Chưa nhập',
    'Chưa nhập',
    'Chưa nhập',
    'Chưa nhập',
    'Chưa nhập',
    'Chưa nhập'
  )
ON CONFLICT (username) DO UPDATE SET
  full_name = EXCLUDED.full_name,
  initials = EXCLUDED.initials,
  age_label = EXCLUDED.age_label,
  room_label = EXCLUDED.room_label,
  date_of_birth = EXCLUDED.date_of_birth,
  blood_type = EXCLUDED.blood_type,
  medical_conditions = EXCLUDED.medical_conditions,
  emergency_contact = EXCLUDED.emergency_contact;
