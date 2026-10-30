# Cài đặt môi trường trên Windows

## 1. Kiểm tra Python

Mở PowerShell trong thư mục project và chạy:

```powershell
python --version
```

Nếu PowerShell báo không tìm thấy `python`, hãy mở lại installer Python và chọn:

- `Add python.exe to PATH`
- `Install launcher for all users`

Sau khi cài xong, đóng PowerShell hiện tại và mở lại PowerShell mới.

## 2. Tạo môi trường ảo

```powershell
cd D:\NCKH
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

## 3. Kiểm tra webcam laptop

```powershell
pip install -r requirements-camera.txt
python -m src.camera.check_camera --camera 0
```

Nếu máy có nhiều camera, thử:

```powershell
python -m src.camera.check_camera --camera 1
```

## 4. Cài đầy đủ demo phát hiện té ngã

```powershell
pip install -r requirements.txt
python -m src.core.app --source 0
```

## 5. Nếu MediaPipe không cài được

MediaPipe trên PyPI hiện liệt kê hỗ trợ chính thức cho Python 3.9 đến 3.12. Nếu Python 3.13 của bạn gặp lỗi khi cài `mediapipe`, cách nhanh nhất cho đề tài là cài thêm Python 3.12 và tạo `.venv` bằng Python 3.12.

Bạn vẫn có thể giữ Python 3.13 trên máy; chỉ cần project này dùng môi trường ảo Python 3.12.
