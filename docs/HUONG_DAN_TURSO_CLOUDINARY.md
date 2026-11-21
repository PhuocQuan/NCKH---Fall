# HƯỚNG DẪN CÀI ĐẶT & KẾT NỐI TURSO DATABASE VÀ CLOUDINARY CLOUD STORAGE

Tài liệu này hướng dẫn chi tiết cách thiết lập, cài đặt thư viện, đăng ký tài khoản trực tuyến và cấu hình đồng thời **Turso (Cơ sở dữ liệu)** và **Cloudinary (Lưu trữ hình ảnh/video cảnh báo)** cho dự án FallGuard.

---

## MÔ HÌNH HOẠT ĐỘNG
* **Turso Database**: Lưu trữ dữ liệu dạng bảng như tài khoản người dùng, cấu hình camera, nhật ký hệ thống, danh bạ liên hệ khẩn cấp.
* **Cloudinary Storage**: Khi phát hiện sự kiện té ngã hoặc khi quản trị viên chụp ảnh kiểm tra hệ thống, hình ảnh/video sẽ được tải lên Cloudinary để lấy đường dẫn (URL) lưu trữ lâu dài trên internet.

---

## PHẦN 1: CÀI ĐẶT THƯ VIỆN BỔ TRỢ (PYTHON)

Mở Terminal / PowerShell tại thư mục gốc của dự án (`NCKH---Fall`) và chạy các lệnh dưới đây:

1. **Kích hoạt môi trường ảo (Virtual Env)**:
   ```powershell
   .venv\Scripts\activate
   ```
2. **Cài đặt thư viện kết nối Turso & Cloudinary**:
   ```powershell
   pip install libsql-client cloudinary
   ```
   *(Hoặc cài đặt toàn bộ thư viện dự án bằng lệnh: `pip install -r requirements.txt`)*

---

## PHẦN 2: HƯỚNG DẪN ĐĂNG KÝ VÀ LẤY KHÓA KẾT NỐI

### A. Thiết lập Turso (Database Online)
1. Truy cập trang chủ [https://turso.tech](https://turso.tech) và đăng ký tài khoản (khuyên dùng tài khoản GitHub).
2. Tạo database mới bằng cách nhấn **Create Database**, đặt tên ví dụ là `nckh-fall-db`.
3. Lưu lại thông tin **URL**: có dạng `libsql://nckh-fall-db-xxxxx.turso.io`.
4. Nhấn **Generate Token** và sao chép mã bảo mật **Auth Token** (chuỗi ký tự JWT dài).

### B. Thiết lập Cloudinary (Lưu trữ ảnh/video)
1. Truy cập trang chủ [https://cloudinary.com](https://cloudinary.com) và đăng ký tài khoản miễn phí.
2. Tại trang quản trị chính (**Dashboard / Console**), bạn sẽ thấy mục **Product Environment Credentials**.
3. Lưu lại 3 thông tin quan trọng sau:
   * **Cloud Name** (Tên môi trường cloud của bạn)
   * **API Key** (Khóa API định danh)
   * **API Secret** (Mật mã API bảo mật - nhấn vào biểu tượng mắt để hiển thị đầy đủ)

---

## PHẦN 3: CẤU HÌNH FILE `configs/db.json`

1. Tìm đến file [db.json](file:///c:/Users/ADMIN/Downloads/NCKH/NCKH---Fall/configs/db.json) trong thư mục `configs` của dự án.
   *(Nếu chưa có file này, hãy sao chép từ file mẫu [db.json.example](file:///c:/Users/ADMIN/Downloads/NCKH/NCKH---Fall/configs/db.json.example) rồi đổi tên thành `db.json`).*
2. Điền chính xác các thông tin bạn đã lấy ở phần trước vào cấu trúc JSON bên dưới:

```json
{
  "turso": {
    "url": "libsql://nckh-fall-db-xxxxx.turso.io",
    "auth_token": "MÃ_AUTH_TOKEN_CỦA_TURSO_Ở_ĐÂY"
  },
  "cloudinary": {
    "cloud_name": "TÊN_CLOUD_NAME_CỦA_BẠN",
    "api_key": "MÃ_API_KEY_CỦA_BẠN",
    "api_secret": "MÃ_API_SECRET_CỦA_BẠN"
  }
}
```
3. Lưu file lại.

---

## PHẦN 4: KHỞI CHẠY VÀ KIỂM TRA KẾT NỐI

1. **Bật Backend Server**:
   ```bash
   python -m src.web.server
   ```
2. **Kiểm tra kết nối Turso**:
   * Truy cập `http://localhost:8000/index.html` và thử đăng nhập (tài khoản mẫu: `admin`, mật khẩu: `nckh2025`).
   * Nếu đăng nhập thành công và xem được danh sách thiết bị, kết nối Turso hoạt động tốt.
3. **Kiểm tra kết nối Cloudinary**:
   * Vào mục **Admin Dashboard** -> Chọn **Camera Monitoring** hoặc danh sách camera.
   * Nhấn nút **Chụp ảnh test** hoặc chụp snapshot từ camera.
   * Hệ thống sẽ tự động chụp ảnh và tải lên Cloudinary. Nếu thành công, giao diện sẽ hiển thị dòng chữ thông báo màu xanh lá cây `"Lưu Cloudinary thành công!"` kèm theo link ảnh trực tuyến.
