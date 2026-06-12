# Ket noi Supabase cho NCKHFall

Project: **NCKHFall**  
URL: `https://qmamwtlhpmvtupcezeyp.supabase.co`

## Buoc 1 — Tao bang

1. Vao [Supabase Dashboard](https://supabase.com/dashboard) -> project **NCKHFall**
2. Menu trai: **SQL Editor** -> **New query**
3. Copy noi dung file `scripts/init_supabase.sql` -> **Run**
4. Menu **Table Editor** — kiem tra co bang: `users`, `user_patient_profiles`, `fall_events`, `access_requests`, `cameras`, `snapshots`

## Buoc 2 — Lay mat khau & connection string

1. **Project Settings** (bánh răng) -> **Database**
2. Neu quen mat khau DB: **Reset database password** -> luu lai
3. Phan **Connection string** -> tab **URI**
4. Chon **Session pooler** (on dinh tu may dev) hoac **Direct**
5. Copy chuoi, thay `[YOUR-PASSWORD]` bang mat khau that

## Buoc 3 — Tao file .env tren may dev

```powershell
cd D:\NCKH\NCKH---Fall
copy .env.example .env
notepad .env
```

Dien `DATABASE_URL` vao `.env`.

## Buoc 4 — Cai package & test

```powershell
.\.venv\Scripts\Activate.ps1
pip install sqlalchemy psycopg2-binary python-dotenv bcrypt
python scripts\test_supabase_connection.py
python scripts\create_admin_user.py
python scripts\test_supabase_connection.py
```

Lan 2 phai thay user `admin` trong bang `users`.

## Buoc 5 — Xem du lieu tren web

- **Table Editor** -> bang `users`, `fall_events`
- Khi code duoc tich hop, moi lan alert se ghi vao `fall_events`

## Trang thai "Unhealthy"

Neu dashboard hien **Unhealthy**, doi 2–5 phut roi refresh. Neu van do:
- Kiem tra project chua bi pause (free tier)
- Thu lai buoc ket noi bang `test_supabase_connection.py`

## Buoc 6 — Chay server voi cloud

Khi co file `.env` voi `DATABASE_URL`, server tu dong:

- Dang nhap / quan ly user tu bang `users` (bcrypt)
- Luu ho so ca nhan theo tai khoan vao `user_patient_profiles`
- Ghi su kien te nga vao `fall_events` (dong thoi giu `data/events.csv`)
- Luu yeu cau truy cap vao `access_requests`

Kiem tra:

```powershell
python -m src.api_server --host 0.0.0.0 --port 8000
```

Mo http://127.0.0.1:8000/api/health — phai thay `"storage": "database"`, `"cloud": {"enabled": true, "status": "ok"}`.

Ep dung file local (khong cloud):

```env
AUTH_STORAGE=yaml
```

## Tao ho so mau cho mot tai khoan (tuy chon)

```powershell
python scripts\seed_patient_profile.py
```

Mac dinh script tao ho so trong cho tai khoan `admin`. Co the doi bang bien moi truong:

```powershell
$env:PROFILE_USERNAME="caregiver.a"
$env:PROFILE_FULL_NAME="Nguoi duoc giam sat"
python scripts\seed_patient_profile.py
```

Nguoi dung van co the tu nhap va luu lai thong tin trong tab **Ho so** cua app.

## Cac bang da tich hop

| Bang | Dung de lam gi | Kich thuoc du lieu |
|------|----------------|-------------------|
| `users` | Tai khoan dang nhap app (admin, caregiver) | Rat nho (~1 KB / user) |
| `user_patient_profiles` | Ho so ca nhan theo tai khoan dang nhap | Rat nho (~1 KB / nguoi) |
| `fall_events` | Lich su trang thai / te nga moi frame quan trong | ~0.5 KB / dong; 10.000 dong ~ 5 MB |
| `access_requests` | Yeu cau xin tai khoan tu man login | Rat nho |
| `cameras` | Metadata camera (du phong) | Rat nho |
| `camera_assignments` | Gan camera cho user (`assigned_users`) | Rat nho |
| `snapshots` | **Chua code** — metadata anh canh bao | ~0.2 KB / anh khi co |

**Du lieu co lon khong?** Voi de tai NCKH (1 phong, vai thang demo): thuong **duoi 50 MB**, nam trong free tier Supabase (500 MB). Anh snapshot van luu tren may chu (`data/snapshots/`), khong day len cloud.

| Bang | Thay the file |
|------|----------------|
| `users` | `configs/auth.yaml` |
| `user_patient_profiles` | `data/patient_profiles.json` khi chay local |
| `fall_events` | `data/events.csv` (ghi song song) |
| `access_requests` | `data/access_requests.json` |
| `camera_assignments` | `assigned_users` trong `configs/cameras.yaml` |

## Gan camera cho user

Admin them/sua camera -> chon tai khoan -> chi user do thay camera (admin thay tat ca).

Tao bang gan (neu chua co):

```powershell
python -c "from dotenv import load_dotenv; from sqlalchemy import create_engine, text; import os; load_dotenv(); e=create_engine(os.environ['DATABASE_URL']); e.begin().execute(text(open('scripts/seed_camera_assignments.sql').read()))"
```
