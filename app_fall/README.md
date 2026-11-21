# FallGuard App (Client)

This is the mobile/web client for the FallGuard AI Fall Detection System.

## Hướng dẫn Chạy Hệ thống (Server, Cloudflare, App) và Tải iOS

### 1. Bật Server (Webcam & API)
Mở terminal tại thư mục gốc của project (chứa `src`, `app_fall`, `cloudflared.exe`) và chạy:
```powershell
.\.venv\Scripts\Activate.ps1
python -m src.web.server
```
Server sẽ chạy ở `http://localhost:8000` và bật webcam để nhận diện.

### 2. Bật Cloudflare Tunnel
Mở một terminal khác tại thư mục gốc, chạy lệnh sau để public port 8000:
```powershell
.\cloudflared.exe tunnel --url http://localhost:8000
```
Copy đường link `.trycloudflare.com` được tạo ra. Dán link này vào file cấu hình API trong app Flutter (ví dụ: `app_fall/lib/core/api_client.dart`).

### 3. Bật App Fall (Flutter)
Mở một terminal khác tại thư mục `app_fall`:
```powershell
cd app_fall
flutter run
```
Hoặc mở thư mục `app_fall` bằng Android Studio / VS Code để chạy.

### Các bước tải iOS (File .ipa)
1. Truy cập trang **Releases** của repository trên GitHub.
2. Tải file `FallGuard.ipa` tại phần **Assets** của bản release mới nhất.
3. Để cài đặt lên iPhone/iPad, sử dụng các công cụ Sideload như **Sideloadly**, **AltStore**, hoặc **TrollStore** (Cài qua máy tính).
4. Sau khi cài đặt thành công, trên thiết bị iOS, vào **Cài đặt (Settings)** > **Cài đặt chung (General)** > **Quản lý thiết bị & VPN**, chọn tin cậy (Trust) chứng chỉ nhà phát triển để mở được app.

## Cập nhật gần đây (Recent Updates)
- Thêm Video Player (tích hợp `video_player`) để xem lại video từ Cloudinary trực tiếp trên app.
- Chuẩn hóa đăng nhập & hồ sơ: Tự động đưa email về viết thường và thêm đuôi `@nckh.vn` nếu người dùng quên nhập.
- Đăng xuất an toàn: Hiển thị cảnh báo xác nhận khi người dùng cập nhật email tài khoản, sau đó tự động đăng xuất để làm mới phiên đăng nhập.
- Khắc phục URL Launcher trên Android 11+: Đã cấu hình `<queries>` trong `AndroidManifest.xml` để mở link HTTPS và gọi điện thoại bình thường.
- Giao diện Thông báo & Cảnh báo:
  - Phân trang mục cảnh báo (10 cảnh báo mỗi trang) giúp tăng hiệu năng UI.
  - Thêm nút **Xóa tất cả** trong tab thông báo.
  - Ghim thông báo cập nhật ứng dụng ở trên cùng, khi nhấn "Xóa tất cả" sẽ không xóa thông báo cập nhật mới nhất.
  
## Getting Started

This project is a starting point for a Flutter application.

- [Lab: Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Cookbook: Useful Flutter samples](https://docs.flutter.dev/cookbook)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.
