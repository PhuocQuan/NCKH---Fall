CREATE TABLE IF NOT EXISTS camera_assignments (
  camera_id   VARCHAR(32) NOT NULL,
  username    VARCHAR(64) NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (camera_id, username)
);
