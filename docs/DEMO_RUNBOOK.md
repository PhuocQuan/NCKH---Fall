# Runbook demo phat hien te nga

Tai lieu nay gom cac buoc can lam de chay demo co the lap lai trong phong lab.

## 1. Kich hoat moi truong

```powershell
cd D:\NCKH\NCKH---Fall
.\.venv\Scripts\Activate.ps1
python -m pytest
```

Ket qua mong doi: tat ca test trong `tests/` deu pass.

Kiem tra moi truong:

```powershell
python -m src.check_environment
```

Ket qua mong doi: cac package chinh `cv2`, `mediapipe`, `numpy`, `sklearn`, `pandas` deu `OK`. Model AI co the hien `not trained yet` neu chua train.

## 2. Kiem tra camera

Kiem tra camera khong mo cua so preview:

```powershell
python -c "from src.video_source import probe_camera; print(probe_camera(0))"
```

Mo preview camera:

```powershell
python -m src.check_camera --camera 0
```

Nhan `q` hoac `Esc` de thoat.

## 3. Chay demo realtime

Chay che do chinh:

```powershell
cd D:\NCKH\NCKH---Fall
python -m src.app --source 0
```

Nhan `q` hoac `Esc` trong cua so video de thoat. Co the nhan `r` de reset detector, hoac `Ctrl+C` trong terminal neu cua so video khong nhan phim.

Chay app desktop co nut dieu khien:

```powershell
cd D:\NCKH\NCKH---Fall
python -m src.desktop_app
```

Trong app desktop, de `Nguon camera/video` la `0` neu dung webcam laptop, sau do bam `Start`. Co the bat checkbox `Demo: canh bao khi nam lau` de test nhanh pipeline canh bao.

Chay che do test nhanh canh bao nam lau:

```powershell
cd D:\NCKH\NCKH---Fall
python -m src.app --source 0 --alert-on-long-lying
```

Che do `--alert-on-long-lying` chi dung de test pipeline canh bao. Khi bao cao ket qua phan biet nam ngu voi te nga, dung che do chinh.

## 4. Kich ban quay video demo

Nen quay moi kich ban 3 den 5 video, moi video 10 den 20 giay:

- `fall`: dang dung/di chuyen roi nga xuong va nam yen.
- `non_fall`: di bo, dung yen, ngoi xuong, cui nguoi, quay nguoi.
- `sleeping`: nam san/nam giuong ngay tu dau, khong co chuyen dong te nga.

Luu video vao:

```text
data/videos/fall/
data/videos/non_fall/
data/videos/sleeping/
```

## 5. Tao feature va train AI

Sau khi co video:

```powershell
python -m src.build_feature_dataset --input data/videos --output data/features/features.csv
python -m src.train_ai_model --csv data/features/features.csv --output models/fall_classifier.joblib
```

Lenh train se tao them bao cao metric mac dinh tai:

```text
models/fall_classifier.report.txt
```

Bat AI trong `configs/default.yaml`:

```yaml
ai:
  enabled: true
  model_path: models/fall_classifier.joblib
  alert_probability: 0.70
  smoothing_frames: 5
  decision_mode: display
  assist_min_frames: 5
```

Mac dinh `decision_mode: display` chi hien xac suat AI tren man hinh. Chi doi sang `assist` sau khi model da duoc danh gia tren video test, vi khi do AI co the ho tro nang muc canh bao trong cac trang thai da co dau hieu bat thuong.

## 6. Danh gia tren video test

Sau khi co video gan nhan trong `data/videos/`, chay:

```powershell
python -m src.evaluate_videos --input data/videos --output data/evaluation/video_results.csv
```

Script se in Accuracy, Precision, Recall, F1-score va luu ket qua tung video vao CSV. Thu muc co ten `fall` duoc tinh la nhan duong; cac thu muc khac nhu `non_fall`, `sleeping` duoc tinh la nhan am.

## 7. Tieu chi demo dat yeu cau

- Camera mo duoc va hien khung xuong nguoi.
- Trang thai binh thuong khong bi canh bao sai khi dung/ngoi/cui.
- Nguoi nam ngay tu dau hien `lying`, khong tao event `alert` trong che do chinh.
- Kich ban te nga chuyen qua `possible_fall`/`fallen`, sau do `alert` neu nam qua nguong.
- File `data/events.csv` co dong su kien khi co `alert`.
