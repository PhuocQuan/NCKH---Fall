# Tich hop AI cho phat hien te nga

## AI hien co trong project

Project co 2 lop:

1. MediaPipe Pose: AI trich xuat khung xuong nguoi tu camera.
2. Fall AI Classifier: model hoc may tuy chon de phan loai chuoi chuyen dong thanh `fall` hoac `non_fall`.

Lop rule-based van duoc giu lai de demo on dinh va giai thich duoc. Model AI se bo sung xac suat `fall`, giup cai thien khi co dataset rieng.

## Cau truc du lieu video de train

Dat video vao cac thu muc theo nhan:

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

De bai NCKH nen tach ro `sleeping` hoac `lying` de model hoc phan biet nam ngu voi te nga. Khi train nhi phan, co the gop `sleeping`, `lying`, `walk`, `sit` thanh `non_fall`.

## Tao CSV dac trung

```powershell
python -m src.build_feature_dataset --input data/videos --output data/features.csv
```

CSV se gom cac dac trung nhu goc than, toc do roi cua hong, do cao dau so voi hong, do tin cay landmark.

## Train model AI

```powershell
python -m src.train_ai_model --csv data/features.csv --output models/fall_classifier.joblib
```

Mac dinh script train se luu them bao cao metric tai `models/fall_classifier.report.txt`. Nen dua cac chi so trong file nay vao bao cao thuc nghiem, kem confusion matrix.

Sau khi train, bat AI trong `configs/default.yaml`:

```yaml
ai:
  enabled: true
  model_path: models/fall_classifier.joblib
  alert_probability: 0.70
  smoothing_frames: 5
  decision_mode: display
  assist_min_frames: 5
```

Roi chay:

```powershell
python -m src.app --source 0
```

`decision_mode: display` chi hien xac suat AI, khong thay doi quyet dinh rule-based. Sau khi model da dat metric chap nhan duoc tren video test, co the thu `decision_mode: assist`; che do nay chi ho tro nang muc canh bao khi rule-based da thay nguoi nam/co dau hieu bat thuong, khong tu bien trang thai `normal` thanh te nga.

## Danh gia tren video

```powershell
python -m src.evaluate_videos --input data/videos --output data/evaluation/video_results.csv
```

Mac dinh cac trang thai `fallen` va `alert` duoc tinh la du doan te nga. Co the doi nguong danh gia:

```powershell
python -m src.evaluate_videos --positive-states possible_fall,fallen,alert
```

## Bao cao NCKH nen trinh bay

- Baseline 1: rule-based detector.
- Baseline 2: AI classifier.
- He thong de xuat: rule-based + AI probability.
- Chi so: Accuracy, Precision, Recall, F1-score, confusion matrix.
- Kich ban rieng: te nga, nam ngu, ngoi xuong, cui nguoi, tre nho choi duoi san, nguoi gia di cham.
