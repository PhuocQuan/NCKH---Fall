# Thu muc video demo

Dat video thu nghiem theo nhan:

```text
fall/       video co hanh dong te nga
non_fall/   video binh thuong, ngoi, cui, di bo
sleeping/   video nam ngu/nam san khong co chuyen dong te nga
```

Ten file nen ngan gon va co so thu tu, vi du:

```text
fall/fall_001.mp4
non_fall/walk_001.mp4
sleeping/sleep_001.mp4
```

Thu muc nay duoc dung boi:

```powershell
python -m src.build_feature_dataset --input data/videos --output data/features/features.csv
```
