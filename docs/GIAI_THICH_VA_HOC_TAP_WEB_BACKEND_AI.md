# CẨM NANG HỌC TẬP VÀ GIẢI MÃ TOÀN BỘ HỆ THỐNG
## CHUYÊN ĐỀ 1: WEB, BACKEND & THỊ GIÁC MÁY TÍNH AI (FALLGUARD AI)

* **Tệp Word nộp kèm:** [`docs/GIAI_THICH_VA_HOC_TAP_WEB_BACKEND_AI.docx`](GIAI_THICH_VA_HOC_TAP_WEB_BACKEND_AI.docx)
* **Dành cho:** Backend Developer, AI Engineer, Thành viên bảo vệ đề tài mảng Server & Thị giác máy tính.

---

## MỤC LỤC
1. [Bản đồ Kiến trúc Mã nguồn (`src/`)](#1-bản-đồ-kiến-trúc-mã-nguồn)
2. [Module Thu nhận Video & Khử độ trễ RTSP (`src/camera/video_source.py`)](#2-module-thu-nhận-video--khử-độ-trễ-rtsp)
3. [Trích xuất Tư thế & Bộ lọc EMA Smoothing (`src/detection/pose_estimator.py`)](#3-trích-xuất-tư-thế--bộ-lọc-ema-smoothing)
4. [Thuật toán Phát hiện Té ngã Cốt lõi (`src/detection/fall_detector.py`)](#4-thuật-toán-phát-hiện-té-ngã-cốt-lõi)
5. [Nhận diện Khuôn mặt & Cảnh báo Người lạ (`src/face/face_recognizer.py`)](#5-nhận-diện-khuôn-mặt--cảnh-báo-người-lạ)
6. [Máy chủ Backend FastAPI & Quản lý Pipeline (`src/web/server.py`, `pipeline.py`)](#6-máy-chủ-backend-fastapi--quản-lý-pipeline)
7. [Cơ sở dữ liệu Turso libSQL & Offline Fallback (`src/web/shared/db.py`)](#7-cơ-sở-dữ-liệu-turso-libsql--offline-fallback)
8. [Đám mây Đa phương tiện Cloudinary & Kỹ thuật Ghi Video (`cloudinary_uploader.py`)](#8-đám-mây-đa-phương-tiện-cloudinary--kỹ-thuật-ghi-video)
9. [Đa kênh Cảnh báo Khẩn cấp: Telegram, Email, SMS (`notifications.py`)](#9-đa-kênh-cảnh-báo-khẩn-cấp)
10. [Bảo mật Hệ thống: PBKDF2-SHA256 & JWT Token (`src/web/shared/auth.py`)](#10-bảo-mật-hệ-thống)
11. [Bộ 15 Câu hỏi Vấn đáp Bảo vệ NCKH (Web & AI)](#11-bộ-15-câu-hỏi-vấn-đáp-bảo-vệ-nckh)

---

## 1. BẢN ĐỒ KIẾN TRÚC MÃ NGUỒN

| Module | Tệp tin cốt lõi | Chức năng chính |
| :--- | :--- | :--- |
| **`src/camera/`** | [`video_source.py`](file:///d:/NCKH/NCKH---Fall/src/camera/video_source.py) | Quản lý luồng RTSP camera IP / Webcam, luồng đọc nền FFmpeg độ trễ 0s, tự động reconnect. |
| **`src/detection/`** | [`pose_estimator.py`](file:///d:/NCKH/NCKH---Fall/src/detection/pose_estimator.py)<br>[`fall_detector.py`](file:///d:/NCKH/NCKH---Fall/src/detection/fall_detector.py) | Ước lượng 33 khớp xương MediaPipe Pose, làm mịn EMA, máy trạng thái FSM nhận diện té ngã. |
| **`src/face/`** | [`face_recognizer.py`](file:///d:/NCKH/NCKH---Fall/src/face/face_recognizer.py) | Nhận diện khuôn mặt YuNet + SFace ONNX, phân loại Người nhà / Cần chú ý / Người lạ. |
| **`src/web/shared/`** | [`server.py`](file:///d:/NCKH/NCKH---Fall/src/web/server.py)<br>[`pipeline.py`](file:///d:/NCKH/NCKH---Fall/src/web/shared/pipeline.py)<br>[`db.py`](file:///d:/NCKH/NCKH---Fall/src/web/shared/db.py)<br>[`auth.py`](file:///d:/NCKH/NCKH---Fall/src/web/shared/auth.py) | FastAPI Server, Watchdog tự phục hồi, Turso Database, mã hóa mật khẩu PBKDF2. |

---

## 2. MODULE THU NHẬN VIDEO & KHỬ ĐỘ TRỄ RTSP (`video_source.py`)

* **Vấn đề trễ 15–30s:** Mặc định OpenCV tích lũy bộ đệm mạng TCP của FFmpeg.
* **Giải pháp 0s Latency:**
  1. Cờ FFmpeg Low-latency: `flags=low_delay|fflags=nobuffer|analyzeduration=0|probesize=32`.
  2. Threaded Grabber: Một luồng daemon ngầm `_reader_loop` liên tục đọc và xả bộ đệm, giữ khung hình mới nhất tại `self._latest_frame`.
  3. Thoát bẫy giả lập (Mock Trap): Nếu camera mất điện, hệ thống tạm chuyển sang `MockVideoCapture`. Cứ 5 giây, phương thức `read()` tự động thử kết nối lại camera thật bằng `_open_real_only()`.

---

## 3. TRÍCH XUẤT TƯ THẾ & BỘ LỌC EMA SMOOTHING (`pose_estimator.py`)

* **Bộ lọc EMA ($\alpha = 0.65$):**
  $$P_{\text{smooth}}(t) = 0.65 \cdot P_{\text{raw}}(t) + 0.35 \cdot P_{\text{smooth}}(t-1)$$
  Giúp khử rung toạ độ khớp xương do nhiễu ánh sáng, triệt tiêu các gai vận tốc ảo gây báo động sai.
* **Bộ lọc đồ vật tĩnh (Static Object Filter):** Nếu các điểm mốc đứng yên tuyệt đối qua >60 frame ($\Delta < 0.0005$), hệ thống xác định đó là ghế/áo treo và loại bỏ ngay.

---

## 4. THUẬT TOÁN PHÁT HIỆN TÉ NGÃ CỐT LÕI (`fall_detector.py`)

* **Máy trạng thái hữu hạn (FSM):**
  * `NORMAL`: Góc thân $< 32^\circ$ (đứng/ngồi thẳng).
  * `LYING`: Góc thân $\ge 50^\circ$, đầu ngang hông, không rơi nhanh $\rightarrow$ **Không bao giờ cảnh báo**.
  * `POSSIBLE_FALL`: Xuất hiện biến đổi rơi nhanh ($v_{\text{hip}} \ge 0.025$ hoặc $\omega \ge 14^\circ/\text{frame}$).
  * `FALLEN`: Duy trì tư thế nằm bất thường $\ge 5$ frames.
  * `ALERT`: Nằm im quá thời gian quy định ($T_{\text{lying}} \ge 10\text{s}$) $\rightarrow$ Kích hoạt chuông và cảnh báo.
* **Hồ sơ nhạy cảm theo đối tượng:**
  * `elderly`: Nhân hệ số nhạy cảm $0.85$ (góc ngã $44.2^\circ$, vận tốc $0.021$).
  * `child`: Nhân hệ số $0.90$.
  * `disabled`: Nhân hệ số $0.80$ (nhạy nhất).

---

## 5. NHẬN DIỆN KHUÔN MẶT & CẢNH BÁO NGƯỜI LẠ (`face_recognizer.py`)

* **Mô hình Deep Learning:** Sử dụng OpenCV YuNet (Phát hiện khuôn mặt) + SFace (Vector 128 chiều) định dạng ONNX.
* **Phân loại 3 nhóm:**
  * `FAMILY` (Người nhà): Cosine similarity $\ge 0.35$ với ảnh trong `data/known_faces/family/`.
  * `ATTENTION` (Cần chú ý): Đối tượng người già/bệnh nhân.
  * `STRANGER` (Người lạ): Xuất hiện liên tục $\ge 15$ frame $\rightarrow$ Phát còi và khóa phiên 60s chống spam.

---

## 6. MÁY CHỦ BACKEND FASTAPI & QUẢN LÝ PIPELINE (`server.py`, `pipeline.py`)

* **Giám sát tự động 24/7:** Hàm `lifespan` tự động khởi chạy camera từ database ngay khi server bật.
* **Watchdog Loop:** Kiểm tra mỗi 15 giây, tự động hồi sinh pipeline nếu bị crash ngầm.
* **Tối ưu RAM Buffer:** Hàm `_buffer_frame()` tự động resize frame về $640 \times 360$ khi lưu vào hàng đệm 200 frame, giảm 75% RAM từ 552MB xuống 132MB.

---

## 7. CƠ SỞ DỮ LIỆU TURSO LIBSQL & OFFLINE FALLBACK (`db.py`)

* **Turso libSQL:** SQLite Serverless phân tán trên Cloud, truy vấn qua HTTP API không phụ thuộc driver C.
* **Offline Logging Fallback:** Khi mất Internet, hàm `log_action()` tự động ghi vào [`data/system_logs_offline.csv`](file:///d:/NCKH/NCKH---Fall/data/system_logs_offline.csv) dự phòng.

---

## 8. ĐÁM MÂY CLOUDINARY & KỸ THUẬT GHI VIDEO (`cloudinary_uploader.py`)

* Luồng ngầm độc lập cắt clip 5–10 giây bằng `cv2.VideoWriter`, tải lên Cloudinary và cập nhật URL công khai vào database. Luồng chính AI duy trì 45–60 FPS không bị nghẽn.

---

## 9. ĐA KÊNH CẢNH BÁO KHẨN CẤP (`notifications.py`)

* **Telegram Bot:** Gửi tin nhắn màu đỏ kèm ảnh snapshot và file video clip MP4 xem trực tiếp.
* **Email & SMS:** Hỗ trợ gửi Email SMTP (Gmail) và SMS (Twilio).

---

## 10. BẢO MẬT HỆ THỐNG (`auth.py`)

* **Mã hóa PBKDF2-HMAC-SHA256:** 16 bytes salt ngẫu nhiên, 100,000 vòng lặp, tương thích ngược với mật khẩu cũ.
* **Chống Timing Attack:** So sánh mật khẩu bằng `hmac.compare_digest`.
* **JWT Token:** Ký bằng secret key 64 bytes chuẩn RFC 7518, thời hạn 12 giờ.

---

## 11. BỘ 15 CÂU HỎI VẤN ĐÁP BẢO VỆ NCKH (WEB & AI LEAD)

*(Xem chi tiết trong tệp Word [`docs/GIAI_THICH_VA_HOC_TAP_WEB_BACKEND_AI.docx`](GIAI_THICH_VA_HOC_TAP_WEB_BACKEND_AI.docx) gồm 15 câu hỏi kèm câu trả lời mẫu chuẩn xác)*
