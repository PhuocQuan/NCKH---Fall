# Huong dan app mobile (web)

App dien thoai dung **trinh duyet** (Chrome/Safari), ket noi den server Python tren laptop qua WiFi.

## 1. Cai them dependency

```powershell
cd D:\NCKH\NCKH---Fall
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. Chay server tren laptop

```powershell
python -m src.api_server --host 0.0.0.0 --port 8000
```

Kiem tra tren laptop: http://127.0.0.1:8000

## 3. Dang nhap

Mac dinh (doi trong `configs/auth.yaml`):

- Tai khoan: `admin`
- Mat khau: `nckh2025`

## 4. Mo tren dien thoai

1. Dien thoai va laptop **cung WiFi**.
2. Tim IP laptop:

```powershell
ipconfig
```

Vi du IP: `192.168.1.5`

3. Tren dien thoai mo trinh duyet:

```
http://192.168.1.5:8000
```

4. Bam **Start** de chay giam sat (webcam laptop).
5. Khung **Camera giam sat** se hien video live tu laptop (MJPEG stream).

Neu khung den van trong:
- Phai bam **Start** truoc (chua Start thi chi thay chu placeholder).
- Kiem tra webcam khong bi app khac (desktop_app) chiem.
- Thu refresh trang sau khi Start.

## API chinh

| Endpoint | Mo ta |
|----------|-------|
| `GET /api/health` | Kiem tra server (khong can dang nhap) |
| `POST /api/auth/login` | Dang nhap, nhan token |
| `GET /api/auth/me` | Kiem tra phien dang nhap |
| `GET /api/status` | Trang thai hien tai |
| `GET /api/events` | Lich su su kien |
| `POST /api/control/start` | Bat giam sat |
| `POST /api/control/stop` | Dung giam sat |
| `POST /api/control/reset` | Reset bo dem |
| `GET /api/snapshots/latest` | Anh canh bao moi nhat |
| `WS /ws/status` | Cap nhat realtime |

## Luu y

- **Khong mo** `desktop_app` va `api_server` cung luc neu ca hai dung webcam `0`.
- Windows Firewall co the hoi quyen — cho phep Python tren mang rieng.
- AI van chay tren laptop; dien thoai chi xem trang thai va canh bao.

## Test

```powershell
python -m pytest tests/test_api_server.py tests/test_mobile_service.py -q
```
