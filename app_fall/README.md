# FallGuard App (Client)

This is the mobile/web client for the FallGuard AI Fall Detection System.

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
