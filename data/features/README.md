# Thu muc feature

Thu muc nay chua CSV dac trung duoc tao tu video trong `data/videos/`.

Lenh tao file feature:

```powershell
python -m src.build_feature_dataset --input data/videos --output data/features/features.csv
```

File CSV co the dung de train model:

```powershell
python -m src.train_ai_model --csv data/features/features.csv --output models/fall_classifier.joblib
```

Sau khi train, script tao them report metric trong `models/`.
