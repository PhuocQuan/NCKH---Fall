-- Chay trong Supabase: SQL Editor -> New query -> Run
-- Project: NCKHFall

-- 1. Nguoi dung (thay auth.yaml)
CREATE TABLE IF NOT EXISTS users (
  id            BIGSERIAL PRIMARY KEY,
  username      VARCHAR(64) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  full_name     VARCHAR(128),
  role          VARCHAR(32) NOT NULL DEFAULT 'caregiver',
  is_admin      BOOLEAN NOT NULL DEFAULT FALSE,
  enabled       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Su kien te nga (thay events.csv)
CREATE TABLE IF NOT EXISTS fall_events (
  id                   BIGSERIAL PRIMARY KEY,
  timestamp            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  source               VARCHAR(128),
  state                VARCHAR(32) NOT NULL,
  torso_angle_deg      DOUBLE PRECISION,
  head_hip_delta       DOUBLE PRECISION,
  hip_velocity         DOUBLE PRECISION,
  angle_velocity_deg   DOUBLE PRECISION,
  abnormal_frames      INTEGER,
  lying_seconds        DOUBLE PRECISION,
  fps                  DOUBLE PRECISION,
  profile              VARCHAR(64),
  fall_like_transition BOOLEAN DEFAULT FALSE,
  device_id            VARCHAR(64)
);

CREATE INDEX IF NOT EXISTS idx_fall_events_timestamp ON fall_events (timestamp DESC);

-- 3. Yeu cau truy cap (thay access_requests.json)
CREATE TABLE IF NOT EXISTS access_requests (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name    VARCHAR(128) NOT NULL,
  email        VARCHAR(128),
  phone        VARCHAR(32),
  role         VARCHAR(32) NOT NULL,
  message      TEXT,
  status       VARCHAR(16) NOT NULL DEFAULT 'pending',
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  reviewed_at  TIMESTAMPTZ,
  review_note  TEXT
);

-- 4. Camera (metadata du phong; nguon chinh van la cameras.yaml tren server)
CREATE TABLE IF NOT EXISTS cameras (
  id          VARCHAR(32) PRIMARY KEY,
  name        VARCHAR(128) NOT NULL,
  source      TEXT NOT NULL,
  location    VARCHAR(128),
  enabled     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4b. Gan camera cho tai khoan (dong bo tu assigned_users trong cameras.yaml)
CREATE TABLE IF NOT EXISTS camera_assignments (
  camera_id   VARCHAR(32) NOT NULL,
  username    VARCHAR(64) NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (camera_id, username)
);

-- 5. Snapshot metadata
CREATE TABLE IF NOT EXISTS snapshots (
  id          BIGSERIAL PRIMARY KEY,
  filename    VARCHAR(255) NOT NULL,
  event_id    BIGINT REFERENCES fall_events(id) ON DELETE SET NULL,
  url         TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. Ho so ca nhan theo tai khoan (tab Ho so tren app)
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

-- Admin: chay scripts/create_admin_user.py sau khi co DATABASE_URL trong .env
