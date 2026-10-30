# Kiến trúc hệ thống

Mục tiêu của project là bắt đầu bằng webcam laptop, sau đó mở rộng sang camera IP/RTSP hoặc thiết bị camera riêng.

## Thành phần

```text
Camera/Webcam/Video/RTSP
        |
        v
VideoSource
        |
        v
PoseEstimator
        |
        v
FallDetector
        |
        +--> App overlay
        +--> EventLogger
```

## Vai trò từng module

- `src/camera/video_source.py`: mở và đọc frame từ webcam, video file, HTTP stream, RTSP stream.
- `src/camera/check_camera.py`: kiểm tra webcam trước khi chạy demo.
- `src/detection/pose_estimator.py`: chuyển frame thành các điểm mốc cơ thể người.
- `src/detection/fall_detector.py`: xử lý chuỗi điểm mốc và trả về trạng thái `normal`, `warning`, `fallen`.
- `src/detection/feature_extractor.py`: trích xuất đặc trưng từ chuỗi landmark.
- `src/ai/ai_classifier.py`: phân loại fall/non_fall bằng model học máy.
- `src/ai/build_feature_dataset.py`, `src/ai/train_ai_model.py`: pipeline train AI.
- `src/core/event_logger.py`: ghi sự kiện để phục vụ báo cáo và đánh giá.
- `src/core/config.py`: cấu hình YAML.
- `src/core/app.py`: ghép các module thành demo realtime.
- `src/web/`: dashboard web FallGuard AI.

## Lộ trình tích hợp camera thực tế

1. Laptop webcam: dùng `--source 0`.
2. Video thử nghiệm: dùng `--source data/videos/sample.mp4`.
3. IP camera cùng mạng LAN: dùng `--source rtsp://user:password@ip:554/stream`.
4. Hệ thống nhiều camera: tạo vòng lặp nhiều `VideoSource`, mỗi camera có một `FallDetector` riêng.
5. Cảnh báo: thêm module gửi Telegram/email/loa khi `event_started=True`.

## Nguyên tắc thiết kế

- Thuật toán không biết frame đến từ đâu, chỉ nhận landmark.
- Nguồn camera nằm riêng trong `VideoSource`.
- Ngưỡng phát hiện nằm trong YAML để dễ điều chỉnh khi thử nghiệm.
- Log sự kiện giúp đo Precision, Recall và F1-score sau khi có dữ liệu gán nhãn.

