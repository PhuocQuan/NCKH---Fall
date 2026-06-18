# Kien truc he thong

Muc tieu cua project la bat dau bang webcam laptop, sau do mo rong sang camera IP/RTSP hoac thiet bi camera rieng.

## Thanh phan

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

## Vai tro tung module

- `src/camera/video_source.py`: mo va doc frame tu webcam, video file, HTTP stream, RTSP stream.
- `src/camera/check_camera.py`: kiem tra webcam truoc khi chay demo.
- `src/detection/pose_estimator.py`: chuyen frame thanh cac diem moc co the nguoi.
- `src/detection/fall_detector.py`: xu ly chuoi diem moc va tra ve trang thai `normal`, `warning`, `fallen`.
- `src/detection/feature_extractor.py`: trich xuat dac trung tu chuoi landmark.
- `src/ai/ai_classifier.py`: phan loai fall/non_fall bang model hoc may.
- `src/ai/build_feature_dataset.py`, `src/ai/train_ai_model.py`: pipeline train AI.
- `src/core/event_logger.py`: ghi su kien de phuc vu bao cao va danh gia.
- `src/core/config.py`: cau hinh YAML.
- `src/core/app.py`: ghep cac module thanh demo realtime.
- `src/web/`: dashboard web FallGuard AI.

## Lo trinh tich hop camera thuc te

1. Laptop webcam: dung `--source 0`.
2. Video thu nghiem: dung `--source data/videos/sample.mp4`.
3. IP camera cung mang LAN: dung `--source rtsp://user:password@ip:554/stream`.
4. He thong nhieu camera: tao vong lap nhieu `VideoSource`, moi camera co mot `FallDetector` rieng.
5. Canh bao: them module gui Telegram/email/loa khi `event_started=True`.

## Nguyen tac thiet ke

- Thuat toan khong biet frame den tu dau, chi nhan landmark.
- Nguon camera nam rieng trong `VideoSource`.
- Nguong phat hien nam trong YAML de de dieu chinh khi thu nghiem.
- Log su kien giup do Precision, Recall va F1-score sau khi co du lieu gan nhan.

