# BÁO CÁO CẢI TIẾN HỆ THỐNG, BẢO MẬT & KIỂM THỬ TỰ ĐỘNG (24/09/2026)

Tài liệu ghi nhận toàn bộ các hạng mục nâng cấp kiến trúc, vá lỗ hổng bảo mật, tối ưu hiệu năng bộ nhớ và kết quả thực thi bộ kiểm thử tự động toàn diện (**Master Test Plan**) cho dự án **FallGuard AI** trong ngày **24/09/2026**.

---

## 1. Nâng cấp Bảo mật & Mã hóa Mật khẩu (`src/web/shared/auth.py`)

* **Lỗ hổng cũ:** 
  * Mật khẩu tài khoản lưu dạng văn bản thô (Plaintext) trong cơ sở dữ liệu và được so sánh trực tiếp (`db_pwd != password`).
  * Khóa bí mật JWT (`JWT_SECRET_KEY`) bị gắn cứng (hardcoded) trực tiếp trong file mã nguồn.
* **Cải tiến đã thực hiện:**
  * **Chuẩn băm mật khẩu công nghiệp:** Sử dụng thuật toán **PBKDF2-HMAC-SHA256** với Salt ngẫu nhiên 16 bytes và 100,000 vòng lặp chuẩn cryptographic (được tích hợp sẵn trong thư viện chuẩn Python `hashlib`, không cần cài thêm dependency).
  * **Hàm băm & Xác thực an toàn:**
    * `hash_password(password: str) -> str`: Tạo chuỗi hash có cấu trúc `$pbkdf2-sha256$100000${salt}${derived}`.
    * `verify_password(plain, stored) -> bool`: Sử dụng hàm so sánh an toàn `hmac.compare_digest` triệt tiêu nguy cơ tấn công dò thời gian (Timing Attack).
  * **Tương thích ngược 100% (Backward Compatibility):** Hệ thống tự động nhận biết nếu tài khoản đang dùng mật khẩu cũ dạng plaintext thì vẫn đăng nhập bình thường, không gây gián đoạn cho người dùng hiện tại.
  * **Bảo mật JWT Secret:** Cho phép nạp `JWT_SECRET_KEY` linh hoạt từ biến môi trường `FALLGUARD_JWT_SECRET` trên máy chủ sản xuất.

---

## 2. Khắc phục lỗi "Bẫy Giả lập" & Tự phục hồi Camera RTSP (`src/camera/video_source.py`)

* **Lỗ hổng cũ ("MockVideoCapture Trap"):**
  * Khi camera IP/RTSP khởi động sau máy chủ hoặc bị mất điện/rớt mạng tạm thời quá 30 frames, `VideoSource` chuyển sang dùng camera giả lập `MockVideoCapture`.
  * Tuy nhiên, trong phương thức `read()` ban đầu, hệ thống chỉ kiểm tra `if isinstance(self.capture, MockVideoCapture): return self.capture.read()`, khiến luồng xử lý **bị kẹt vĩnh viễn ở chế độ mô phỏng** mà không bao giờ kết nối lại camera vật lý dù camera đã có điện/mạng trở lại.
* **Cải tiến đã thực hiện:**
  * **Tách cơ chế mở camera thực:** Xây dựng hàm `_open_real_only()` riêng biệt để thử nghiệm kết nối camera thật mà không gây side-effect.
  * **Cơ chế Thăm dò Định kỳ (Auto-Recovery Probe):** Trong `read()`, nếu đang ở chế độ `MockVideoCapture`, hệ thống tự động thăm dò kết nối lại camera thật mỗi 5 giây (`_last_reconnect_time`).
  * **Khôi phục Luồng ngầm (Thread Rebirth):** Ngay khi kết nối lại thành công, hệ thống hoán đổi đối tượng `self.capture` sang camera thật và tự động khởi động lại luồng đọc ngầm tốc độ cao `_reader_loop`.
  * **Chống gián đoạn khung hình (Zero Dropped Frame on Reconnect):** Trong thời điểm luồng nền vừa bật, `read()` sẽ đọc trực tiếp khung hình đầu tiên để trả về cho AI xử lý ngay lập tức mà không bị trả về `(False, None)`.

---

## 3. Tối ưu Bộ nhớ Frame Buffer, Tiết kiệm 75% RAM (`src/web/shared/pipeline.py`)

* **Vấn đề cũ:**
  * Hàng đệm video 200 frame (`deque(maxlen=200)`) liên tục lưu frame gốc chất lượng 720p (`1280x720x3 bytes ~ 2.76MB/frame`).
  * Bộ đệm liên tục ngốn hơn **550MB RAM**, tạo áp lực cực lớn lên bộ gom rác Garbage Collector (GC) của Python khi chạy liên tục 24/7.
* **Cải tiến đã thực hiện:**
  * Xây dựng phương thức tối ưu `_buffer_frame(frame, cv2)`: Tự động điều chỉnh kích thước frame lưu vào buffer video clip về chuẩn **$640 \times 360$** (đủ sắc nét để làm bằng chứng pháp lý/sơ cứu, nhưng giảm 75% số lượng điểm ảnh).
  * **Kết quả:** Dung lượng bộ nhớ của 200 frame giảm từ **~552MB xuống còn ~132MB** (tiết kiệm hơn 420MB RAM).
  * Bức ảnh chụp cận cảnh biến cố (`snapshot_frame`) gửi qua Telegram vẫn được giữ nguyên độ phân giải Full HD gốc để nhận diện rõ khuôn mặt.

---

## 4. Bổ sung Cơ chế Ghi Log Ngoại tuyến (`src/web/shared/db.py`)

* **Vấn đề cũ:** Khi mạng Internet gặp sự cố, các truy vấn SQL tới Turso Database Cloud bị lỗi mạng/timeout dẫn đến nguy cơ bỏ sót lịch sử sự kiện.
* **Cải tiến đã thực hiện:**
  * Bổ sung cơ chế ghi log ngoại tuyến (Offline File Fallback): Khi `get_db_client()` ném ngoại lệ mất mạng, hàm `log_action()` tự động ghi sự kiện vào file nội bộ [`data/system_logs_offline.csv`](file:///d:/NCKH/NCKH---Fall/data/system_logs_offline.csv).
  * Đảm bảo tính sẵn sàng cao, hệ thống không bao giờ bị văng lỗi hay mất dữ liệu khi môi trường mạng chập chờn.

---

## 5. Kết quả Thực thi Bộ Kiểm thử Tự động (Master Test Plan)

Đã xây dựng 3 bộ kiểm thử tự động mới và chạy toàn bộ test suite dự án bằng công cụ `pytest`:

```powershell
python -m pytest tests/ --basetemp=data/pytest_tmp -p no:cacheprovider -v
```

### Kết quả Chi tiết: **20 / 20 Test Cases PASSED (100% Thành công)** trong **1.48s**

| STT | File Test | Kịch bản kiểm thử (Test Cases) | Trạng thái |
| :---: | :--- | :--- | :---: |
| 1 | `test_fall_detection_scenarios.py` | **TC-AI-01:** Phân biệt nằm ngủ bình thường vs té ngã (không báo động sai) | **PASSED** |
| 2 | `test_fall_detection_scenarios.py` | **TC-AI-02:** Phát hiện cú ngã thật đột ngột (đổi góc + vận tốc hông + nằm im) | **PASSED** |
| 3 | `test_fall_detection_scenarios.py` | **TC-AI-03:** Cúi nhặt đồ / buộc dây giày rồi đứng dậy (tự động reset về NORMAL) | **PASSED** |
| 4 | `test_fall_detection_scenarios.py` | **TC-AI-04:** Ngồi bệt dưới sàn nhà lưng thẳng (duy trì NORMAL) | **PASSED** |
| 5 | `test_fall_detection_scenarios.py` | **TC-AI-07:** Kiểm tra hệ số nhạy cảm theo đối tượng (Elderly, Child, Pregnant, Disabled) | **PASSED** |
| 6 | `test_concurrency_and_performance.py` | **TC-PF-01:** Kiểm tra tính Non-blocking: lưu video ngầm không nghẽn luồng camera chính | **PASSED** |
| 7 | `test_concurrency_and_performance.py` | **TC-PF-03:** Giới hạn bộ nhớ buffer 200 frame và hiệu quả tiết kiệm RAM | **PASSED** |
| 8 | `test_concurrency_and_performance.py` | **TC-DB-01:** Chống bão thông báo (Debounce / Cooldown khi nạn nhân bất tỉnh) | **PASSED** |
| 9 | `test_fault_tolerance.py` | **TC-FT-01:** Tự động khôi phục camera RTSP và thoát khỏi MockVideoCapture Trap | **PASSED** |
| 10 | `test_fault_tolerance.py` | **TC-FT-03:** Cơ chế ghi log ngoại tuyến fallback khi mất kết nối Turso Database | **PASSED** |
| 11 | `test_fault_tolerance.py` | **TC-SEC-01:** Hàm băm mật khẩu PBKDF2-SHA256 và tương thích ngược | **PASSED** |
| 12-20 | `test_fall_detector.py`, `test_face_recognizer.py`, `test_feature_extractor.py` | 9 test cases kế thừa về tư thế đứng, nhận dạng khuôn mặt và trích xuất đặc trưng | **PASSED** |

---

## 6. Tính năng Tự Động Dò Tìm & Tái Kết Nối Camera Wi-Fi (Zero-Configuration & Auto-Discovery)

* **Vấn đề thực tế:**
  * Camera Wi-Fi gia đình (như Imou Ranger 2, Ezviz, Dahua) nhận địa chỉ IP động từ Router qua DHCP.
  * Mỗi khi Router khởi động lại, cúp điện hoặc hết hạn cấp phát IP, địa chỉ IP của camera có thể bị đổi từ `192.168.1.20` sang `192.168.1.x`, khiến chuỗi RTSP cũ bị mất kết nối và người dùng phải dò IP rồi cấu hình lại thủ công rất bất tiện.
* **Cải tiến đã triển khai:**
  * **Module Dò tìm thông minh đa cơ chế ([`src/camera/camera_discovery.py`](file:///d:/NCKH/NCKH---Fall/src/camera/camera_discovery.py)):**
    * **ONVIF WS-Discovery (UDP Multicast 239.255.255.250:3702):** Chuẩn quốc tế của camera an ninh, gửi broadcast tìm kiếm thiết bị và nhận diện hãng (Imou, Dahua, Hikvision, Ezviz...).
    * **Fast Subnet RTSP Scanner (Đa luồng cổng 554 & 37777):** Quét toàn bộ 254 địa chỉ IP trên dải mạng Wi-Fi nội bộ bằng 64 worker threads, phát hiện camera chỉ trong **~1.5 giây**.
    * **RTSP Handshake Probe:** Gửi gói tin `OPTIONS rtsp://... RTSP/1.0` qua socket TCP để xác thực thiết bị camera có sẵn sàng cấp luồng hay không mà không cần tải thư viện nặng.
  * **Cơ chế Tự Phục Hồi (Self-Healing Auto-Rebind):**
    * Tích hợp vào [`src/web/server.py`](file:///d:/NCKH/NCKH---Fall/src/web/server.py) (`_auto_start_monitoring` & `_watchdog_loop`): Nếu camera tại IP cũ bị mất tín hiệu, server tự động quét tìm IP mới của camera trong mạng Wi-Fi, tự cập nhật lại IP và chuỗi RTSP vào CSDL Turso/SQLite, rồi tiếp tục chạy mà không cần con người can thiệp.
  * **Giao diện Web 1-Click ([`src/web/admin/index.html`](file:///d:/NCKH/NCKH---Fall/src/web/admin/index.html)):**
    * Thêm nút bấm nổi bật: **"🔍 Quét Wi-Fi tìm Camera"** tại trang Quản lý Camera.
    * Khi click, modal hiển thị dải mạng Wi-Fi nội bộ, tự quét và liệt kê danh sách camera kèm nút **"⚡ Kết nối camera này"** chỉ với 1 click.

---

## 7. Kết quả Thực thi Toàn bộ Test Suite (26 / 26 PASSED)

Đã xây dựng thêm bộ kiểm thử tự động `tests/test_camera_discovery.py` và chạy toàn bộ test suite dự án bằng công cụ `pytest`:

```powershell
python -m pytest tests/ --basetemp=data/pytest_tmp -p no:cacheprovider -v
```

### Kết quả Chi tiết: **26 / 26 Test Cases PASSED (100% Thành công)** trong **4.08s**

| STT | File Test | Kịch bản kiểm thử (Test Cases) | Trạng thái |
| :---: | :--- | :--- | :--- |
| 1 | `test_camera_discovery.py` | Kiểm tra lấy IP máy tính và tiền tố Subnet mạng nội bộ | **PASSED** |
| 2 | `test_camera_discovery.py` | Kiểm tra tự động tạo chuỗi RTSP Imou Ranger 2 chuẩn độ trễ thấp | **PASSED** |
| 3 | `test_camera_discovery.py` | Kiểm tra phản hồi gói tin RTSP OPTIONS socket handshake | **PASSED** |
| 4 | `test_camera_discovery.py` | Kiểm tra nhận diện camera Dahua/Imou trên cổng 554/37777 | **PASSED** |
| 5 | `test_camera_discovery.py` | **API GET /api/cameras/discover:** Quét và trả về danh sách camera trong Wi-Fi | **PASSED** |
| 6 | `test_camera_discovery.py` | **API POST /api/cameras/auto-bind:** Tự động đồng bộ IP mới và khởi động lại luồng AI | **PASSED** |
| 7 | `test_fall_detection_scenarios.py` | **TC-AI-01:** Phân biệt nằm ngủ bình thường vs té ngã (không báo động sai) | **PASSED** |
| 8 | `test_fall_detection_scenarios.py` | **TC-AI-02:** Phát hiện cú ngã thật đột ngột (đổi góc + vận tốc hông + nằm im) | **PASSED** |
| 9 | `test_fall_detection_scenarios.py` | **TC-AI-03:** Cúi nhặt đồ / buộc dây giày rồi đứng dậy (tự động reset về NORMAL) | **PASSED** |
| 10 | `test_fall_detection_scenarios.py` | **TC-AI-04:** Ngồi bệt dưới sàn nhà lưng thẳng (duy trì NORMAL) | **PASSED** |
| 11 | `test_fall_detection_scenarios.py` | **TC-AI-07:** Kiểm tra hệ số nhạy cảm theo đối tượng (Elderly, Child, Pregnant, Disabled) | **PASSED** |
| 12 | `test_concurrency_and_performance.py` | **TC-PF-01:** Kiểm tra tính Non-blocking: lưu video ngầm không nghẽn luồng camera chính | **PASSED** |
| 13 | `test_concurrency_and_performance.py` | **TC-PF-03:** Giới hạn bộ nhớ buffer 200 frame và hiệu quả tiết kiệm RAM | **PASSED** |
| 14 | `test_concurrency_and_performance.py` | **TC-DB-01:** Chống bão thông báo (Debounce / Cooldown khi nạn nhân bất tỉnh) | **PASSED** |
| 15 | `test_fault_tolerance.py` | **TC-FT-01:** Tự động khôi phục camera RTSP và thoát khỏi MockVideoCapture Trap | **PASSED** |
| 16 | `test_fault_tolerance.py` | **TC-FT-03:** Cơ chế ghi log ngoại tuyến fallback khi mất kết nối Turso Database | **PASSED** |
| 17 | `test_fault_tolerance.py` | **TC-SEC-01:** Hàm băm mật khẩu PBKDF2-SHA256 và tương thích ngược | **PASSED** |
| 18-26 | `test_fall_detector.py`, `test_face_recognizer.py`, `test_feature_extractor.py` | 9 test cases kế thừa về tư thế đứng, nhận dạng khuôn mặt và trích xuất đặc trưng | **PASSED** |

---

## 8. Danh mục File Đã Tạo & Cập Nhật

1. [`src/camera/camera_discovery.py`](file:///d:/NCKH/NCKH---Fall/src/camera/camera_discovery.py): Module dò tìm camera Wi-Fi thông minh (ONVIF + Fast Subnet Scan 1.5s + RTSP Handshake).
2. [`src/web/admin/router.py`](file:///d:/NCKH/NCKH---Fall/src/web/admin/router.py): Bổ sung API `/api/cameras/discover` và `/api/cameras/auto-bind`.
3. [`src/web/admin/service.py`](file:///d:/NCKH/NCKH---Fall/src/web/admin/service.py): Bổ sung service `auto_bind_camera` cập nhật CSDL và tái kích hoạt pipeline.
4. [`src/web/admin/repository.py`](file:///d:/NCKH/NCKH---Fall/src/web/admin/repository.py): Bổ sung repository `update_camera_network_db`.
5. [`src/web/server.py`](file:///d:/NCKH/NCKH---Fall/src/web/server.py): Thêm logic tự động dò tìm IP mới trong `_auto_start_monitoring()` khi camera cũ mất tín hiệu.
6. [`src/web/admin/index.html`](file:///d:/NCKH/NCKH---Fall/src/web/admin/index.html): Thêm nút "🔍 Quét Wi-Fi tìm Camera", modal quét thiết bị và nút kết nối 1-click.
7. [`tests/test_camera_discovery.py`](file:///d:/NCKH/NCKH---Fall/tests/test_camera_discovery.py): Test suite kiểm thử toàn diện chức năng dò tìm và auto-bind camera.
8. [`src/web/shared/auth.py`](file:///d:/NCKH/NCKH---Fall/src/web/shared/auth.py): Mã hóa mật khẩu PBKDF2-SHA256, nạp JWT secret từ biến môi trường.
9. [`src/camera/video_source.py`](file:///d:/NCKH/NCKH---Fall/src/camera/video_source.py): Sửa lỗi kẹt giả lập, tự phục hồi kết nối camera thật.
10. [`src/web/shared/pipeline.py`](file:///d:/NCKH/NCKH---Fall/src/web/shared/pipeline.py): Thêm `_buffer_frame` tối ưu giảm 75% RAM bộ đệm video.
11. [`src/web/shared/db.py`](file:///d:/NCKH/NCKH---Fall/src/web/shared/db.py): Bổ sung offline log fallback khi mất mạng.
12. [`docs/BAO_CAO_CAP_NHAT_2026_09_24.md`](file:///d:/NCKH/NCKH---Fall/docs/BAO_CAO_CAP_NHAT_2026_09_24.md): Tài liệu báo cáo cập nhật chi tiết.
