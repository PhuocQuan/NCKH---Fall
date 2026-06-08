# Logic phat hien te nga

## Muc tieu

He thong khong canh bao chi vi thay nguoi dang nam. Canh bao chi duoc tao khi co chuoi dau hieu:

1. Co chuyen dong giong te nga: than nguoi doi tu the nhanh, hong roi nhanh, hoac truoc do dang dung/ngoi thang.
2. Sau chuyen dong do, nguoi nam ngang va dau thap gan muc hong.
3. Trang thai nam keo dai qua `alert_after_seconds`, mac dinh 10 giay.

Voi logic nay, nguoi nam ngu san tren giuong/san se duoc gan `lying`, khong tao canh bao neu khong co chuyen dong giong te nga truoc do.

Neu can demo nhanh tinh nang canh bao trong phong lab, co the dung:

```powershell
python -m src.app --source 0 --alert-on-long-lying
```

Che do nay se canh bao khi nguoi nam lau hon `alert_after_seconds` du khong co chuyen dong giong te nga. No huu ich de test pipeline canh bao, nhung khong nen dung lam ket qua chinh khi danh gia kha nang phan biet nam ngu voi te nga.

## Cac trang thai

- `normal`: binh thuong.
- `lying`: dang nam nhung chua co dau hieu te nga.
- `possible_fall`: co dau hieu bat thuong ngan han.
- `fallen`: da xac nhan co chuoi te nga, dang dem thoi gian nam.
- `alert`: da te va nam lau hon nguong canh bao.

## Ho tro nhieu nhom nguoi

Project khong tu dong doan mot nguoi la nguoi gia, tre nho, phu nu co thai hay nguoi khuyet tat tu camera. Viec do khong on dinh va de sai. Thay vao do, he thong co `profile` do nguoi van hanh chon trong `configs/default.yaml`:

- `default`
- `elderly`
- `child`
- `pregnant`
- `disabled`

Profile nhay hon se giam mot so nguong ve toc do roi, toc do doi goc va so frame toi thieu. Cach nay phu hop giai doan dau cua de tai vi co the demo va giai thich duoc.

## Buoc tiep theo de lam NCKH tot hon

- Thu thap video rieng cho tung nhom doi tuong.
- Gan nhan cac doan: `normal`, `sleeping`, `sitting`, `lying`, `fall`.
- So sanh logic nguong voi model chuoi thoi gian nhu LSTM/GRU/Transformer tren landmark.
- Bao cao Precision, Recall, F1-score rieng cho tung nhom.
