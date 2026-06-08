# Cai dat moi truong tren Windows

## 1. Kiem tra Python

Mo PowerShell trong thu muc project va chay:

```powershell
python --version
```

Neu PowerShell bao khong tim thay `python`, hay mo lai installer Python va chon:

- `Add python.exe to PATH`
- `Install launcher for all users`

Sau khi cai xong, dong PowerShell hien tai va mo lai PowerShell moi.

## 2. Tao moi truong ao

```powershell
cd D:\NCKH
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

## 3. Kiem tra webcam laptop

```powershell
pip install -r requirements-camera.txt
python -m src.check_camera --camera 0
```

Neu may co nhieu camera, thu:

```powershell
python -m src.check_camera --camera 1
```

## 4. Cai day du demo phat hien te nga

```powershell
pip install -r requirements.txt
python -m src.app --source 0
```

## 5. Neu MediaPipe khong cai duoc

MediaPipe tren PyPI hien liet ke ho tro chinh thuc cho Python 3.9 den 3.12. Neu Python 3.13 cua ban gap loi khi cai `mediapipe`, cach nhanh nhat cho de tai la cai them Python 3.12 va tao `.venv` bang Python 3.12.

Ban van co the giu Python 3.13 tren may; chi can project nay dung moi truong ao Python 3.12.
