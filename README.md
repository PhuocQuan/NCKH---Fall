# Đề tài NCKH: Phát hiện té ngã bằng thị giác máy tính

Hệ thống phát hiện té ngã realtime từ webcam hoặc file video. Dự án dùng **MediaPipe Pose** để trích xuất landmark cơ thể, sau đó áp dụng thuật toán **rule-based** có giải thích được; có thể bổ sung lớp **AI** (tùy chọn) khi đã có dữ liệu huấn luyện.

**Repository:** [github.com/PhuocQuan/NCKH---Fall](https://github.com/PhuocQuan/NCKH---Fall)

## Tính năng chính

### Phát hiện & xử lý
- Nhận diện người realtime từ webcam, file video hoặc RTSP.
- Phát hiện té ngã theo góc thân người, độ cao đầu/hông, vận tốc rơi và thời gian nằm sau chuyển động giống té ngã.
- Phân biệt **nằm ngủ / nằm sẵn** (`lying`) với **té ngã thật** (`fallen` → `alert`).
- Grace period khi mất pose tạm thời (`max_pose_lost_frames`), không reset trạng thái ngay.
- Tối ưu Pose: resize `640×360`, `model_complexity: 0`, hiển thị `pose_ms` mỗi frame.

### Ứng dụng
- **CLI** (`app.py`): overlay OpenCV, phím `q` thoát, `r` reset.
- **Desktop** (`desktop_app.py`): giao diện Tkinter 3 tab — **Giám sát / Cài đặt / Nhật ký**.
- **Mobile / Web** (`mobile/web/` + `api_server.py`): app **Guardian Watch** — login, giám sát, cảnh báo, quản lý camera (admin).
- **APK Android** (Capacitor): xem [`docs/BUILD_APK.md`](docs/BUILD_APK.md).
- Pipeline chung (`pipeline.py`) cho CLI, desktop và API mobile.
- Quét và chọn webcam, chọn file video/config; hỗ trợ RTSP.
- Cảnh báo âm thanh (chuông WAV + beep Windows), lưu **snapshot** khi alert (`data/snapshots/`).
- Thanh tiến trình đếm thời gian nằm; event log CSV với session mode.
- Cài đặt người dùng lưu trong `configs/user.yaml` (profile, thời gian cảnh báo, skeleton, snapshot).
- Tài khoản do **admin cấp**; quản lý user + yêu cầu truy cập trên app.
- Phím tắt desktop: **Space** Start/Stop, **R** Reset.

### Đánh giá & AI (sẵn sàng code, chờ dữ liệu)
- Script đánh giá trên bộ video gán nhãn: `evaluate_videos.py`.
- Trích feature, train model, fusion rule + AI: `build_feature_dataset.py`, `train_ai_model.py`, `decision_fusion.py`.
- Model AI tắt mặc định (`ai.enabled: false`); bật sau khi train xong.

### Chất lượng
- **75** unit test (`pytest`), bao gồm detector, pipeline, API mobile, auth, camera, event log, settings, snapshot.
- Kiểm tra môi trường: `check_environment`, `check_camera`.
- Tiến độ công việc chi tiết: [`docs/TIEN_DO_CONG_VIEC.md`](docs/TIEN_DO_CONG_VIEC.md).

## Cấu trúc thư mục

```text
NCKH---Fall/
├── configs/
│   ├── default.yaml      # Ngưỡng detector, pose, AI
│   ├── user.yaml         # Cài đặt desktop (tự lưu từ app)
│   ├── cameras.yaml      # Danh sách camera (mặc định trống; admin thêm qua app)
│   ├── auth.yaml         # Tài khoản admin + users (không commit — dùng .example)
│   ├── cameras.yaml.example
│   └── auth.yaml.example
├── data/
│   ├── events.csv        # Log sự kiện
│   ├── snapshots/        # Ảnh khi cảnh báo
│   ├── videos/           # Video gán nhãn (fall / non_fall / sleeping)
│   ├── features/         # Feature CSV cho train AI
│   └── evaluation/       # Kết quả đánh giá
├── docs/                 # Kiến trúc, logic, setup, demo, AI
├── models/               # fall_classifier.joblib (sau khi train)
├── src/
│   ├── pipeline.py       # Pipeline chung CLI + desktop
│   ├── desktop_app.py    # App Tkinter
│   ├── desktop_view.py   # UI helpers, throttle render
│   ├── app.py            # Demo CLI OpenCV
│   ├── fall_detector.py  # Thuật toán rule-based
│   ├── pose_estimator.py # MediaPipe Pose
│   ├── video_source.py   # Webcam / video / RTSP
│   ├── event_logger.py   # Ghi CSV
│   ├── ui_overlay.py     # Vẽ trạng thái lên frame
│   ├── alert_sound.py    # Cảnh báo âm thanh
│   ├── user_settings.py  # Load/save user.yaml
│   ├── snapshot.py       # Lưu ảnh alert
│   ├── api_server.py     # API + web mobile
│   ├── mobile_service.py # Pipeline chạy nền cho API
│   ├── auth.py           # Đăng nhập, quản lý user
│   ├── camera_registry.py
│   ├── access_requests.py
│   └── ...               # AI, evaluate, train scripts
├── mobile/
│   ├── web/              # Giao diện Guardian Watch (HTML/CSS/JS)
│   └── android-app/      # Capacitor — build APK
└── tests/
```

## Cài đặt

Xem hướng dẫn Windows chi tiết trong [`docs/SETUP_WINDOWS.md`](docs/SETUP_WINDOWS.md).

**Khuyến nghị:** Python **3.10 – 3.12**. Python 3.13 có thể không cài được `mediapipe` — nên dùng 3.12 riêng cho project này.

```powershell
cd D:\NCKH\NCKH---Fall
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Kiểm tra camera trước (chỉ cần OpenCV):

```powershell
pip install -r requirements-camera.txt
python -m src.check_camera --camera 0
```

Kiểm tra môi trường đầy đủ:

```powershell
python -m src.check_environment
```

## Chạy demo

### Desktop (khuyến nghị cho demo NCKH)

```powershell
python -m src.desktop_app
```

### Mobile (trình duyệt điện thoại — cùng WiFi với laptop)

```powershell
python -m src.api_server --host 0.0.0.0 --port 8000
```

Terminal sẽ in link `http://127.0.0.1:8000` và IP WiFi/LAN (ví dụ `http://192.168.1.10:8000`) — nhập link đó vào app mobile.

Chi tiết: [`docs/MOBILE_APP.md`](docs/MOBILE_APP.md)

### APK Android (Capacitor)

```powershell
cd mobile\android-app
npm install
npm run cap:sync
npm run cap:open
```

Build APK trong Android Studio. Chi tiết: [`docs/BUILD_APK.md`](docs/BUILD_APK.md)

### CLI (OpenCV)

```powershell
python -m src.app --source 0
python -m src.app --source path\to\video.mp4
python -m src.app --source rtsp://user:password@192.168.1.10:554/stream
```

Phím trong CLI: `q` thoát, `r` reset detector.

## Trạng thái hệ thống

| Trạng thái | Ý nghĩa |
|------------|---------|
| `normal` | Đứng/ngồi bình thường |
| `lying` | Nằm sẵn hoặc nằm ngủ — **không** cảnh báo nếu không có chuyển động giống té ngã |
| `warning` | Dấu hiệu bất thường ngắn |
| `possible_fall` | Nghi ngã — đang theo dõi |
| `fallen` | Đã phát hiện ngã — đang đếm thời gian nằm |
| `alert` | **Cảnh báo** — ngã và nằm quá `alert_after_seconds` (mặc định 10 giây) |

Chi tiết logic: [`docs/FALL_DETECTION_LOGIC.md`](docs/FALL_DETECTION_LOGIC.md)

## Cấu hình

| File | Nội dung |
|------|----------|
| `configs/default.yaml` | Ngưỡng detector, kích thước camera, pose, AI |
| `configs/user.yaml` | Profile, thời gian cảnh báo, skeleton, snapshot — chỉnh từ tab **Cài đặt** trong desktop |

Profile có sẵn: `default`, `elderly` (ngưỡng nhạy hơn cho người già).

## Chạy test

```powershell
python -m pytest
```

Kết quả mong đợi: **75 test pass**.

## Đánh giá & huấn luyện AI

1. Đặt video theo thư mục nhãn trong `data/videos/` (xem `data/videos/README.md`).
2. Chạy đánh giá rule-based:

```powershell
python -m src.evaluate_videos --input data/videos --output data/evaluation/video_results.csv
```

3. Tạo feature dataset:

```powershell
python -m src.build_feature_dataset --input data/videos --config configs/default.yaml
```

4. Train model:

```powershell
python -m src.train_ai_model
```

5. Bật AI trong `configs/default.yaml`: `ai.enabled: true`

Hướng dẫn chi tiết: [`docs/AI_INTEGRATION.md`](docs/AI_INTEGRATION.md) · [`docs/DEMO_RUNBOOK.md`](docs/DEMO_RUNBOOK.md)

## Kiến trúc

```text
Camera / Video / RTSP
        ↓
   VideoSource
        ↓
  PoseEstimator  (resize 640×360, MediaPipe)
        ↓
   FallDetector  (rule-based)
        ↓
 DecisionFusion + AI (tùy chọn)
        ↓
  Overlay + EventLogger + Snapshot + AlertSound
        ↓
  Desktop (Tkinter)  |  Mobile API (FastAPI) → Web/APK
```

Chi tiết module: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

### Luồng mobile (Guardian Watch)

```text
Điện thoại/APK → HTTP/WS → api_server.py
        ↓
  Đăng nhập (auth.yaml) → Chọn camera → Start giám sát
        ↓
  mobile_service.py (pipeline) → MJPEG stream + JSON status
        ↓
  Cảnh báo: banner + chuông WAV + màn hình khẩn cấp
```

## Tiến độ dự án

Bảng chi tiết đầy đủ (35 hạng mục, luồng hoạt động, ngôn ngữ lập trình): **[`docs/TIEN_DO_CONG_VIEC.md`](docs/TIEN_DO_CONG_VIEC.md)**

| Giai đoạn | Nội dung | STT | Trạng thái |
|-----------|----------|-----|------------|
| G1–G2 | Core pipeline, detector, CLI | 1–5 | Hoàn thành |
| G3–G4 | Desktop app, tối ưu, settings, pytest | 6–19 | Hoàn thành |
| G5-mobile | API, Guardian Watch, APK, auth, camera, user | 20–32 | Hoàn thành |
| G5-AI | Thu video, metric, train AI | 34 | Chưa có dữ liệu |
| G6 | Báo cáo, slide, demo bảo vệ | 33, 35 | Chưa làm |

## Tài liệu tham khảo trong repo

| Tài liệu | Mô tả |
|----------|-------|
| [`docs/SETUP_WINDOWS.md`](docs/SETUP_WINDOWS.md) | Cài đặt trên Windows |
| [`docs/DEMO_RUNBOOK.md`](docs/DEMO_RUNBOOK.md) | Checklist demo & quay video |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Kiến trúc hệ thống |
| [`docs/FALL_DETECTION_LOGIC.md`](docs/FALL_DETECTION_LOGIC.md) | Logic phát hiện té ngã |
| [`docs/AI_INTEGRATION.md`](docs/AI_INTEGRATION.md) | Tích hợp & train AI |
| [`docs/MOBILE_APP.md`](docs/MOBILE_APP.md) | Hướng dẫn app mobile / API |
| [`docs/BUILD_APK.md`](docs/BUILD_APK.md) | Build APK Android |
| [`docs/TIEN_DO_CONG_VIEC.md`](docs/TIEN_DO_CONG_VIEC.md) | Bảng tiến độ công việc NCKH |

## Hướng phát triển

- Thu thập video đa bối cảnh → đo Accuracy, Precision, Recall, F1-score.
- So sánh rule-only với rule + AI (`decision_mode`: `display` / `assist`).
- Cảnh báo qua Telegram, email hoặc dashboard web.
- Hỗ trợ nhiều camera, model chuỗi thời gian (LSTM/GRU).
