# Tích hợp AI cho phát hiện té ngã

## AI hiện có trong project

Project có 2 lớp:

1. MediaPipe Pose: AI trích xuất khung xương người từ camera.
2. Fall AI Classifier: model học máy tùy chọn để phân loại chuỗi chuyển động thành `fall` hoặc `non_fall`.

Lớp rule-based vẫn được giữ lại để demo ổn định và giải thích được. Model AI sẽ bổ sung xác suất `fall`, giúp cải thiện khi có dataset riêng.

## Cấu trúc dữ liệu video để train

Đặt video vào các thư mục theo nhãn:

```text
data/videos/
  fall/
    fall_001.mp4
    fall_002.mp4
  non_fall/
    walk_001.mp4
    sit_001.mp4
  sleeping/
    sleep_001.mp4
```

Đề tài NCKH nên tách rõ `sleeping` hoặc `lying` để model học phân biệt nằm ngủ với té ngã. Khi train nhị phân, có thể gộp `sleeping`, `lying`, `walk`, `sit` thành `non_fall`.

## Tạo CSV đặc trưng

```powershell
python -m src.ai.build_feature_dataset --input data/videos --output data/features.csv
```

CSV sẽ gồm các đặc trưng như góc thân, tốc độ rơi của hông, độ cao đầu so với hông, độ tin cậy landmark.

## Train model AI

```powershell
python -m src.ai.train_ai_model --csv data/features.csv --output models/fall_classifier.joblib
```

Sau khi train, bật AI trong `configs/default.yaml`:

```yaml
ai:
  enabled: true
  model_path: models/fall_classifier.joblib
  alert_probability: 0.70
  smoothing_frames: 5
```

Rồi chạy:

```powershell
python -m src.core.app --source 0
```

## Báo cáo NCKH nên trình bày

- Baseline 1: rule-based detector.
- Baseline 2: AI classifier.
- Hệ thống đề xuất: rule-based + AI probability.
- Chỉ số: Accuracy, Precision, Recall, F1-score, confusion matrix.
- Kịch bản riêng: té ngã, nằm ngủ, ngồi xuống, cúi người, trẻ nhỏ chơi dưới sàn, người già đi chậm.
