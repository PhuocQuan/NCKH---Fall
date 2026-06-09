# Đề tài NCKH: Phát hiện té ngã bằng thị giác máy tính

Project mẫu cho sinh viên thi NCKH cấp trường. Hệ thống dùng webcam/video, trích xuất tư thế người bằng MediaPipe Pose, sau đó phát hiện té ngã dựa trên góc thân người, độ cao đầu/hông và vận tốc thay đổi tư thế.

## Tính năng

* Nhận diện người realtime từ webcam hoặc file video.
* Phát hiện nguy cơ té ngã bằng thuật toán có giải thích được.
* Hiển thị khung xương, trạng thái `normal`, `warning`, `fallen`.
* Ghi log sự kiện vào `data/events.csv`.
* Cấu hình ngưỡng trong `configs/default.yaml`.
* Có test đơn vị cho bộ phát hiện để bảo vệ logic cốt lõi.

## Cài đặt

Xem hướng dẫn Windows chi tiết trong `docs/SETUP_WINDOWS.md`.

Khuyến nghị ổn định cho demo AI pose: Python 3.10 đến 3.12. Nếu bạn dùng Python 3.13 và `pip install mediapipe` báo lỗi không tìm thấy phiên bản phù hợp, hãy cài thêm Python 3.12 riêng cho project này. Phần test webcam có thể chạy riêng với OpenCV.

Kiểm tra camera laptop trước:

```powershell
pip install -r requirements-camera.txt
python -m src.check_camera --camera 0
```

Cài đầy đủ để chạy phát hiện té ngã:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Chạy demo webcam

```powershell
python -m src.app --source 0
```

Chạy app desktop có nút Start/Stop/Reset:

```powershell
python -m src.desktop_app
```

Kiểm tra môi trường trước khi demo:

```powershell
python -m src.check_environment
```

Chạy với video:

```powershell
python -m src.app --source path\to\video.mp4
```

Chạy với IP camera/RTSP trong tương lai:

```powershell
python -m src.app --source rtsp://user:password@192.168.1.10:554/stream
```

## Runbook demo

Xem checklist chạy demo, quay video mẫu, tạo feature và train AI trong `docs/DEMO_RUNBOOK.md`.

## Chạy test

```powershell
python -m pytest
```

## Đánh giá trên bộ video

Sau khi đặt video theo nhãn trong `data/videos/`, chạy:

```powershell
python -m src.evaluate_videos --input data/videos --output data/evaluation/video_results.csv
```

Kết quả gồm dự đoán từng video và các chỉ số Accuracy, Precision, Recall, F1-score.

## Ý tưởng thuật toán

Mỗi frame sẽ lấy các điểm mốc cơ thể từ MediaPipe. Module `FallDetector` tính:

* Góc thân người so với trục dọc.
* Độ cao đầu so với hông.
* Vận tốc rơi của điểm hông.
* Tốc độ thay đổi góc thân người.
* Số frame liên tiếp có dấu hiệu bất thường.
* Thời gian nằm sau một chuyển động giống té ngã.

Một sự kiện chỉ được ghi log cảnh báo khi có chuỗi chuyển động giống té ngã và người nằm quá `alert_after_seconds`, mặc định 10 giây. Nếu người chỉ nằm ngủ hoặc nằm sẵn mà không có chuyển động giống té ngã, hệ thống hiện `lying` và không cảnh báo. Xem chi tiết trong `docs/FALL_DETECTION_LOGIC.md`.

## Hướng phát triển NCKH

* Xem thêm kiến trúc trong `docs/ARCHITECTURE.md`.
* Xem thêm logic phát hiện và phân biệt nằm ngủ/té ngã trong `docs/FALL_DETECTION_LOGIC.md`.
* Xem thêm cách train AI trong `docs/AI_INTEGRATION.md`.
* Thu thập video té ngã/không té ngã trong nhiều bối cảnh.
* Gán nhãn frame hoặc đoạn video thành `fall`, `normal`, `sitting`, `lying`.
* So sánh thuật toán ngưỡng với mô hình học máy như LSTM/GRU trên chuỗi landmark.
* Đo các chỉ số Accuracy, Precision, Recall, F1-score, FPS.
* Thêm cảnh báo qua email, Telegram, loa, hoặc dashboard web.
