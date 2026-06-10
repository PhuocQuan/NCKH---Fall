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
- Pipeline chung (`pipeline.py`) cho cả CLI và desktop.
- Quét và chọn webcam, chọn file video/config.
- Cảnh báo âm thanh (beep Windows), lưu **snapshot** khi alert (`data/snapshots/`).
- Thanh tiến trình đếm thời gian nằm; event log CSV với session mode.
- Cài đặt người dùng lưu trong `configs/user.yaml` (profile, thời gian cảnh báo, skeleton, snapshot).
- Phím tắt desktop: **Space** Start/Stop, **R** Reset.

### Đánh giá & AI (sẵn sàng code, chờ dữ liệu)
- Script đánh giá trên bộ video gán nhãn: `evaluate_videos.py`.
- Trích feature, train model, fusion rule + AI: `build_feature_dataset.py`, `train_ai_model.py`, `decision_fusion.py`.
- Model AI tắt mặc định (`ai.enabled: false`); bật sau khi train xong.

### Chất lượng
- **37** unit test (`pytest`), bao gồm detector, pipeline, event log, settings, snapshot.
- Kiểm tra môi trường: `check_environment`, `check_camera`.

## Cấu trúc thư mục

```text
NCKH---Fall/
├── configs/
│   ├── default.yaml      # Ngưỡng detector, pose, AI
│   └── user.yaml         # Cài đặt desktop (tự lưu từ app)
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
│   └── ...               # AI, evaluate, train scripts
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

Kết quả mong đợi: **37 test pass**.

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
```

Chi tiết module: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## Tiến độ dự án

| Giai đoạn | Nội dung | Trạng thái |
|-----------|----------|------------|
| G1–G2 | Khảo sát, core pipeline, detector | Hoàn thành |
| G3–G4 | Desktop app, tối ưu, settings, test | Hoàn thành |
| G5 | Thu video, metric, train AI | Chưa có dữ liệu |
| G6 | Báo cáo, slide, demo bảo vệ | Chưa làm |

## Tài liệu tham khảo trong repo

| Tài liệu | Mô tả |
|----------|-------|
| [`docs/SETUP_WINDOWS.md`](docs/SETUP_WINDOWS.md) | Cài đặt trên Windows |
| [`docs/DEMO_RUNBOOK.md`](docs/DEMO_RUNBOOK.md) | Checklist demo & quay video |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Kiến trúc hệ thống |
| [`docs/FALL_DETECTION_LOGIC.md`](docs/FALL_DETECTION_LOGIC.md) | Logic phát hiện té ngã |
| [`docs/AI_INTEGRATION.md`](docs/AI_INTEGRATION.md) | Tích hợp & train AI |

## Hướng phát triển

- Thu thập video đa bối cảnh → đo Accuracy, Precision, Recall, F1-score.
- So sánh rule-only với rule + AI (`decision_mode`: `display` / `assist`).
- Cảnh báo qua Telegram, email hoặc dashboard web.
- Hỗ trợ nhiều camera, model chuỗi thời gian (LSTM/GRU).
