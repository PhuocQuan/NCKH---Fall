# Tóm tắt cập nhật Ứng dụng Mobile (Flutter)

Tài liệu này tóm tắt các tính năng mới đã được tích hợp vào phiên bản Mobile (nhánh `Nhan`) của dự án FallGuard và hướng dẫn cách xuất file cài đặt cho cả hai hệ điều hành Android và iOS.

## 1. Các tính năng đã hoàn thiện trên Mobile
- **Tinh giản giao diện hiển thị:** Rút gọn danh sách camera mặc định. Giao diện giờ đây tự động thích ứng để chỉ hiển thị 1 camera duy nhất khi khởi động (chưa có kết nối API), tự sinh thêm thẻ khi có camera mới.
- **Tích hợp tính năng Web (Stranger Alerts):**
  - **Nhận diện tự động:** Hệ thống tự động nhận diện ID cảnh báo bắt đầu bằng `STRANGER-` để hiển thị tiêu đề và biểu tượng "👤 Người lạ xuất hiện" (màu xanh), phân biệt rõ với "⚠️ Cảnh báo ngã" (màu đỏ).
  - **Phân loại Thông báo:** Phân loại và tô viền các loại thông báo (`fall`, `stranger`, `disconnect`) giúp người dùng dễ nhận biết ngay lập tức.
  - **Huy hiệu Cloudinary:** Thêm huy hiệu (badge) "☁️ Cloudinary" phủ lên trên ảnh chụp bằng chứng trong chi tiết sự kiện nếu bức ảnh này được truyền lên từ dịch vụ Cloudinary.
- **Thanh trạng thái (Status Pill):**
  - Cập nhật logic thanh trạng thái ở màn hình chính: Hiện "Camera Off" (khi không có camera), "Camera On" (khi có camera nhưng đang ở màn hình ngoài), và chuyển sang "Đang mở cam" (khi người dùng ấn xem trực tiếp camera).
- **Màn hình Live Stream:** 
  - Thay đổi màn hình xem camera từ dạng cuộn lên (BottomSheet) sang dạng hiển thị toàn màn hình (Fullscreen) với phông nền đen chuyên nghiệp, có thanh AppBar chứa nút quay lại và tên camera.

---

## 2. Hướng dẫn cài đặt cho Android (File APK)
Với Android, việc cài đặt rất đơn giản, bạn có thể build trực tiếp trên máy tính Windows.

1. Mở Terminal/Command Prompt, trỏ vào thư mục `app_fall`.
2. Chạy câu lệnh: 
   ```bash
   flutter build apk
   ```
3. Sau khi chạy xong (khoảng 1-2 phút), file cài đặt sẽ xuất hiện tại đường dẫn:
   `app_fall/build/app/outputs/flutter-apk/app-release.apk`
4. Bạn chỉ cần chép file `.apk` này vào điện thoại Android, hoặc gửi qua Zalo/Google Drive và ấn vào để cài đặt trực tiếp.

---

## 3. Hướng dẫn tải và cài đặt cho iOS (File IPA)
Hệ điều hành iOS đóng và không cho phép build trực tiếp trên Windows cũng như cài đặt file tùy ý. Do đó, hệ thống đã được tự động hóa thông qua máy chủ GitHub.

### Bước 1: Tải file `.ipa` từ GitHub
1. Mã nguồn đã được cấu hình tự động build mỗi khi bạn đẩy code (Push) lên nhánh `Nhan`.
2. Truy cập vào trang GitHub của dự án -> Chọn tab **Actions**.
3. Bấm vào tiến trình build mới nhất (có dấu tích xanh).
4. Cuộn xuống dưới cùng trang, ở phần **Artifacts**, bấm tải xuống file **FallGuard-iOS**.
5. Giải nén file `.zip` vừa tải, bạn sẽ thu được file `FallGuard.ipa`. (Lưu ý: Không gửi file này qua Zalo để cài vì iPhone sẽ không nhận).

### Bước 2: Cài vào iPhone (Bằng Sideloadly)
1. Tải và cài đặt phần mềm **Sideloadly** trên máy tính Windows (sideloadly.io).
2. **Quan trọng:** Tải và cài đặt **iTunes 64-bit bản Web (.exe)** từ trang chủ Apple. (Tuyệt đối không dùng bản tải từ Microsoft Store).
3. Dùng cáp kết nối iPhone với máy tính, mở khóa màn hình iPhone và bấm **"Tin cậy" (Trust)**.
4. Mở Sideloadly, bạn sẽ thấy tên thiết bị iPhone hiện ra.
5. Kéo thả file `FallGuard.ipa` vào Sideloadly.
6. Nhập Apple ID cá nhân (iCloud) vào ô Apple ID và ấn **Start**.
7. Khi báo Done, vào iPhone: *Cài đặt -> Cài đặt chung -> Quản lý VPN & Thiết bị*. Nhấn chọn tên email của bạn và ấn **Tin cậy**. Sau đó, bạn có thể mở ứng dụng trên màn hình chính bình thường. (Ứng dụng có thời hạn 7 ngày, sau 7 ngày cắm cáp làm lại bước 6 để gia hạn).
