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
python -m src.camera.check_camera --camera 0
```

Cài đầy đủ để chạy phát hiện té ngã:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Chạy demo webcam

```powershell
python -m src.core.app --source 0
```

Chạy với video:

```powershell
python -m src.core.app --source path\to\video.mp4
```

Chạy với IP camera/RTSP trong tương lai:

```powershell
python -m src.core.app --source rtsp://user:password@192.168.1.10:554/stream
```

## Chạy test

Hệ thống có bộ kiểm thử tự động toàn diện (20 test cases bao quát: phân biệt nằm ngủ vs ngã thật, hiệu năng non-blocking, chống bão thông báo, chịu lỗi camera và mã hóa bảo mật):

```powershell
python -m pytest tests/ --basetemp=data/pytest_tmp -p no:cacheprovider -v
```

## Báo cáo cập nhật & Tiến độ hệ thống

* **Báo cáo mới nhất (24/09/2026):** Xem tại [docs/BAO_CAO_CAP_NHAT_2026_09_24.md](docs/BAO_CAO_CAP_NHAT_2026_09_24.md) (Bảo mật PBKDF2-SHA256, tự phục hồi camera, tối ưu 75% RAM buffer và kết quả 20/20 test cases).
* Báo cáo ca làm việc (02/08/2026): Xem tại [docs/BAO_CAO_CAP_NHAT_2026_08_02.md](docs/BAO_CAO_CAP_NHAT_2026_08_02.md).

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

## FallGuard App Client
Các bản cập nhật về giao diện ứng dụng Flutter (thêm tính năng thông báo, xử lý video bằng video_player, sửa lại Android Manifest và chuẩn hóa UI/UX) có thể được tìm thấy trong thư mục [app_fall/README.md](app_fall/README.md).

## Hướng dẫn Chạy Hệ thống & Tải iOS

Chi tiết về cách chạy Server (Webcam), Cloudflare Tunnel, App Fall (Flutter) và tải bản build iOS (.ipa), vui lòng xem tại file: [app_fall/README.md](app_fall/README.md).

### 1. Bật Server (Webcam & API)
Mở terminal tại thư mục gốc của project (chứa src, app_fall, cloudflared.exe) và chạy:
`powershell
.\.venv\Scripts\Activate.ps1
python -m src.web.server
`
Server sẽ chạy ở http://localhost:8000 và bật webcam để nhận diện.

### 2. Bật Cloudflare Tunnel
Mở một terminal khác tại thư mục gốc, chạy lệnh sau để public port 8000:
`powershell
.\cloudflared.exe tunnel --url http://localhost:8000
`
Copy đường link .trycloudflare.com được tạo ra. Dán link này vào file cấu hình API trong app Flutter (ví dụ: app_fall/lib/core/api_client.dart).

### 3. Bật App Fall (Flutter)
Mở một terminal khác tại thư mục app_fall:
`powershell
cd app_fall
flutter run
`
Hoặc mở thư mục app_fall bằng Android Studio / VS Code để chạy.

### Các bước tải iOS (File .ipa)
1. Truy cập trang **Releases** của repository trên GitHub.
2. Tải file FallGuard.ipa tại phần **Assets** của bản release mới nhất.
3. Để cài đặt lên iPhone/iPad, sử dụng các công cụ Sideload như **Sideloadly**, **AltStore**, hoặc **TrollStore** (Cài qua máy tính).
4. Sau khi cài đặt thành công, trên thiết bị iOS, vào **Cài đặt (Settings)** > **Cài đặt chung (General)** > **Quản lý thiết bị & VPN**, chọn tin cậy (Trust) chứng chỉ nhà phát triển để mở được app.
