# CẨM NANG HỌC TẬP VÀ GIẢI MÃ TOÀN BỘ HỆ THỐNG
## CHUYÊN ĐỀ 2: ỨNG DỤNG DI ĐỘNG FLUTTER (ANDROID & IOS)

* **Tệp Word nộp kèm:** [`docs/GIAI_THICH_VA_HOC_TAP_MOBILE_FLUTTER.docx`](GIAI_THICH_VA_HOC_TAP_MOBILE_FLUTTER.docx)
* **Dành cho:** Mobile Developer, Flutter Engineer, Thành viên bảo vệ đề tài mảng Ứng dụng Di động.

---

## MỤC LỤC
1. [Tổng quan Kiến trúc Ứng dụng Flutter (`app_fall/`)](#1-tổng-quan-kiến-trúc-ứng-dụng-flutter)
2. [Cấu trúc Dự án & Các Tệp Tin Mã Nguồn](#2-cấu-trúc-dự-án--các-tệp-tin-mã-nguồn)
3. [Quản lý Trạng thái & Giao tiếp API (`AppStateService` & `ApiClient`)](#3-quản-lý-trạng-thái--giao-tiếp-api)
4. [Trình phát Video Trực tiếp Không độ trễ (Custom MJPEG Viewer)](#4-trình-phát-video-trực-tiếp-không-độ-trễ)
5. [Trình phát Video Bằng chứng & Huy hiệu Đám mây Cloudinary](#5-trình-phát-video-bằng-chứng--huy-hiệu-đám-mây-cloudinary)
6. [Phân loại Cảnh báo Té ngã vs Người lạ Đột nhập](#6-phân-loại-cảnh-báo-té-ngã-vs-người-lạ-đột-nhập)
7. [Danh bạ Khẩn cấp SOS & Cuộc gọi 1 Chạm (`url_launcher`)](#7-danh-bạ-khẩn-cấp-sos--cuộc-gọi-1-chạm)
8. [Hướng dẫn Xuất bản Android APK & Sideload iOS IPA](#8-hướng-dẫn-xuất-bản-android-apk--sideload-ios-ipa)
9. [Bộ 15 Câu hỏi Vấn đáp Bảo vệ NCKH (Mobile Lead)](#9-bộ-15-câu-hỏi-vấn-đáp-bảo-vệ-nckh)

---

## 1. TỔNG QUAN KIẾN TRÚC ỨNG DỤNG FLUTTER

* **Ngôn ngữ & Framework:** Flutter (Dart ^3.8.1).
* **Phiên bản:** v1.0.6+7 (Khai báo trong `pubspec.yaml`).
* **Ưu điểm kiến trúc:** Chia sẻ 100% mã nguồn giao diện và logic giữa Android và iOS, render đồ họa 60 FPS mượt mà.

---

## 2. CẤU TRÚC DỰ ÁN & CÁC TỆP TIN MÃ NGUỒN

| Tệp tin / Thư mục | Chức năng chính |
| :--- | :--- |
| **[`app_fall/pubspec.yaml`](file:///d:/NCKH/NCKH---Fall/app_fall/pubspec.yaml)** | Khai báo thư viện: `http`, `shared_preferences`, `video_player`, `url_launcher`. |
| **[`app_fall/lib/main.dart`](file:///d:/NCKH/NCKH---Fall/app_fall/lib/main.dart)** | Điểm khởi chạy (Entry point), cấu hình Material 3 theme màu tím than / xanh hiện đại. |
| **[`app_fall/lib/core/models.dart`](file:///d:/NCKH/NCKH---Fall/app_fall/lib/core/models.dart)** | Data models: `CameraDevice`, `AlertEvent`, `AppNotification`, `MonitoredProfile`. |
| **[`app_fall/lib/core/api_client.dart`](file:///d:/NCKH/NCKH---Fall/app_fall/lib/core/api_client.dart)** | REST API client, gắn Bearer Token, xử lý timeout 10 giây. |
| **[`app_fall/lib/core/app_state_service.dart`](file:///d:/NCKH/NCKH---Fall/app_fall/lib/core/app_state_service.dart)** | Quản lý state in-memory, lưu cache `SharedPreferences`, đồng bộ dữ liệu server. |
| **[`app_fall/lib/screens/login_screen.dart`](file:///d:/NCKH/NCKH---Fall/app_fall/lib/screens/login_screen.dart)** | Màn hình đăng nhập, phân quyền Admin (chỉ Web) vs User (dùng trên App). |
| **[`app_fall/lib/screens/home_screen.dart`](file:///d:/NCKH/NCKH---Fall/app_fall/lib/screens/home_screen.dart)** | Màn hình chính điều hướng 4 Tab (Dashboard, Alerts, Notifications, Profile). |

---

## 3. QUẢN LÝ TRẠNG THÁI & GIAO TIẾP API

* **Mô hình Offline-First:** Khi mở app, `AppStateService` lập tức nạp dữ liệu gần nhất từ `SharedPreferences` để hiển thị tức thì mà không bị màn hình trắng.
* **Đồng bộ ngầm:** Sau đó, app âm thầm gọi `/api/app-state` để cập nhật trạng thái mới nhất từ cơ sở dữ liệu Turso.
* **Xác thực bảo mật:** Tự động gắn header `Authorization: Bearer <jwt_token>` trong mọi request.

---

## 4. TRÌNH PHÁT VIDEO TRỰC TIẾP KHÔNG ĐỘ TRỄ (CUSTOM MJPEG VIEWER)

* **Tại sao không dùng thư viện có sẵn:** Thư viện `flutter_mjpeg` bị xung đột phiên bản với `http: ^1.2.2`.
* **Cơ chế Custom:** Nhóm tự viết bộ giải mã luồng byte trực tiếp:
  ```dart
  final client = http.Client();
  final request = http.Request('GET', Uri.parse(streamUrl));
  final response = await client.send(request);
  response.stream.listen((chunk) {
    // Tách frame dựa trên boundary marker '--frame' và header 'image/jpeg'
    // Hiển thị trực tiếp qua widget Image.memory(frameBytes)
  });
  ```
* **Chế độ Toàn màn hình (Fullscreen Viewer):** Phông nền đen sang trọng, hỗ trợ tự động xoay ngang màn hình (Landscape) theo cảm biến con quay hồi chuyển.

---

## 5. TRÌNH PHÁT VIDEO BẰNG CHỨNG & HUY HIỆU ĐÁM MÂY CLOUDINARY

* **Tích hợp `video_player`:** Nhấn vào sự kiện ngã sẽ mở dialog phát đoạn video MP4 (5-10 giây) trích xuất từ Cloudinary với tỷ lệ chuẩn 16:9, có nút Play/Pause/Seek.
* **Huy hiệu "☁️ Cloudinary":** Tự động hiển thị huy hiệu màu xanh dương nổi bật nếu video/ảnh đã được lưu an toàn trên đám mây.

---

## 6. PHÂN LOẠI CẢNH BÁO TÉ NGÃ VS NGƯỜI LẠ ĐỘT NHẬP

* **Nhận diện tự động qua ID:**
  * Mã bắt đầu bằng `AL-`: Cảnh báo ngã (Màu đỏ khẩn cấp, icon ⚠️).
  * Mã bắt đầu bằng `STRANGER-`: Cảnh báo người lạ (Màu xanh đậm, icon 👤, hiển thị % tin cậy AI).
* **Quản lý thông báo:** Hiển thị số lượng chưa đọc trên Badge tab điều hướng, hỗ trợ đánh dấu đã đọc hoặc vuốt để xóa.

---

## 7. DANH BẠ KHẨN CẤP SOS & CUỘC GỌI 1 CHẠM (`url_launcher`)

* Lưu danh bạ Người thân, Bác sĩ gia đình, Trung tâm Cấp cứu 115 trong tab Profile.
* Bấm biểu tượng điện thoại đỏ tự động kích hoạt `launchUrl(Uri.parse('tel:$phone'))`, mở bàn phím gọi tức thời trong tích tắc.

---

## 8. HƯỚNG DẪN XUẤT BẢN ANDROID APK & SIDELOAD IOS IPA

### Xuất file APK cho Android
```bash
cd app_fall
flutter build apk --release
```
File cài đặt xuất hiện tại: `app_fall/build/app/outputs/flutter-apk/app-release.apk`. Chép vào máy Android hoặc gửi qua Zalo/Drive để cài trực tiếp.

### Tự động hóa iOS trên GitHub Actions & Cài qua Sideloadly
1. Đẩy mã nguồn lên nhánh `Nhan`, GitHub Actions sẽ tự động biên dịch và tạo artifact `FallGuard-iOS`.
2. Tải file `FallGuard.ipa` về máy tính Windows.
3. Mở phần mềm **Sideloadly**, cắm cáp kết nối iPhone, kéo thả file `FallGuard.ipa` vào, nhập Apple ID và bấm **Start**.
4. Trên iPhone, vào **Cài đặt -> Cài đặt chung -> Quản lý VPN & Thiết bị**, chọn tin cậy (Trust) chứng chỉ để mở app.

---

## 9. BỘ 15 CÂU HỎI VẤN ĐÁP BẢO VỆ NCKH (MOBILE LEAD)

*(Xem chi tiết trong tệp Word [`docs/GIAI_THICH_VA_HOC_TAP_MOBILE_FLUTTER.docx`](GIAI_THICH_VA_HOC_TAP_MOBILE_FLUTTER.docx) gồm 15 câu hỏi kèm câu trả lời mẫu chuẩn xác)*
