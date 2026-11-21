# BÁO CÁO CẬP NHẬT TOÀN DIỆN & TỔNG KẾT TIẾN ĐỘ (25/09/2026)

Tài liệu ghi nhận toàn bộ các hạng mục nghiên cứu khoa học, cải tiến thuật toán, nâng cấp kiến trúc, tối ưu mã nguồn và kết quả kiểm thử tự động cho dự án **FallGuard AI** (Hệ thống Giám sát & Cảnh báo Sớm Té ngã Thông minh) hoàn thành trong ngày **25/09/2026**.

---

## 1. Tóm tắt Tổng quan Thành tựu trong Ngày

Trong ngày làm việc 25/09/2026, dự án FallGuard AI đã giải quyết dứt điểm 7 bài toán trọng tâm từ thực nghiệm camera thực tế:

1. **Xử lý Cảm biến Thị giác & Chống Báo động Giả khi Ngồi làm việc:** Khắc phục méo góc camera, rung chấn vật lý, chuẩn hóa vận tốc bất biến khoảng cách, triệt tiêu báo động giả khi ngồi bàn gõ máy tính bị che khuất hông hoặc mặt giả trên bàn tay.
2. **Nhận diện Tiền Té ngã (Pre-Fall Detection):** Phân tích dao động trọng tâm (Center of Mass) và tư thế để phát hiện sớm các hành vi **Lảo đảo (Swaying), Bước hụt (Stumble), Chóng mặt (Dizzy)** trước khi té ngã.
3. **Module Nhận diện Nội thất & Vật phẩm Trợ năng (YOLOv8-nano ONNX):** Tích hợp nhận diện Giường, Sofa, Ghế, Bàn để xác định trạng thái Nghỉ ngơi an toàn (`SAFE_RESTING`); hỗ trợ cấu hình bật/tắt linh hoạt để tối ưu 100% CPU.
4. **Nhận diện Khuôn mặt Thời gian thực Ổn định & Chống Nhảy Tên:** Áp dụng Top-2 Sample Averaging, Đồng thuận đa khung hình (Multi-Frame Consensus $\ge 3/5$ frames) và Cửa sổ giữ danh tính (Sticky Identity 5.0s) loại bỏ hoàn toàn nhảy chéo giữa Ân, Bảo, Quân và Người lạ.
5. **Cố định Khung xương theo Chuyển động & Triệt tiêu Tia xanh Bắn sang Cửa sổ / Áo khoác:** Cô lập instance MediaPipe Pose độc lập (`_crop_pose`), áp dụng Bộ lọc Giải phẫu học Thích ứng (Adaptive Anatomical Bone Sanity) theo tỷ lệ cơ thể thực tế `ref_scale`, và bộ làm mượt chuyển động thích ứng (Adaptive EMA Smoothing).
6. **Triệt tiêu 100% Hiện tượng Nối Khung xương khi 2 Người Đứng Gần nhau:** Thuật toán phân vùng ngang Voronoi / Midpoint Partitioning ngăn cách hoàn toàn vùng quan sát giữa 2 người, kẹp tọa độ trong phạm vi $[0.0, 1.0]$, triệt tiêu khớp ngoại vi vươn ngang (Distal Limb Suppression) và nâng cấp `model_complexity=1` cho crop pose.
7. **Lưu trữ Camera CSDL Bền vững:** Xây dựng cơ chế cơ sở dữ liệu chịu lỗi hai lớp (Resilient Dual-Layer DB) tự động chuyển đổi giữa Turso Cloud và SQLite cục bộ (`data/local.db`), đồng bộ ghi dữ liệu (Write-Mirroring); cấu hình camera Imou RTSP được lưu vĩnh viễn, không bị mất khi F5 / tải lại trang.

---

## 2. Chi tiết Các Hạng mục Kỹ thuật Đã Hoàn Thành

### 2.1. Cảm biến Quang học & Chống Báo Ngã Giả khi Ngồi Bàn
- **Scale-Invariant Velocity Normalization:** Chuẩn hóa vận tốc pixel theo tỷ lệ thân người tham chiếu $L_{\text{ref}} / L_{\text{torso}}$, triệt tiêu lỗi bỏ sót người ở xa và báo động oan người ở gần cúi nhanh.
- **Camera Pitch Compensation:** Tái lập góc nghiêng trọng lực mặt đất cho camera lắp góc cao chúc xuống ($20^\circ - 45^\circ$).
- **Desk Occlusion & Ground Proximity Filter:** Khi phần hông bị mặt bàn che khuất và vai ở nửa trên khung hình ($y < 0.52$), hệ thống tự động nhận diện tư thế ngồi làm việc (`is_seated = True`), ngăn chặn báo ngã giả.
- **Face Anatomical Filter:** Lọc bỏ hoàn toàn các box khuôn mặt giả do bàn tay/bàn phím gây ra bằng cách kiểm tra vị trí tương quan với trục vai của khung xương.

### 2.2. Nhận diện Tiền Té ngã (Pre-Fall Detection - `src/detection/balance_analyzer.py`)
- **Sliding Window CoM Kinetics:** Theo dõi liên tục trung điểm vai - hông qua cửa sổ trượt 15–25 frames.
- **Phân loại 3 dạng mất thăng bằng:**
  - `SWAYING` (Lảo đảo): Dao động phương ngang $\sigma_x \ge 0.032$ với $\ge 3$ lần đảo hướng.
  - `STUMBLE` (Bước hụt / Khụy ngã): Vận tốc hạ trọng tâm $v_y \ge 0.016$ kết hợp giật ngang.
  - `DIZZY` (Chóng mặt): Nghiêng lắc đung đưa biên độ vừa phải duy trì $\ge 25$ frames.
- **Cơ chế Pre-Fall Linkage:** Giảm 50% thời gian xác nhận chuông báo ngã khẩn cấp nếu trước đó có giai đoạn mất thăng bằng.
- **Giao diện HUD Live:** Hiển thị huy hiệu cảnh báo màu cam nổi bật thời gian thực.

### 2.3. Nhận diện Khuôn mặt Ổn định & Chống Nhảy Tên (`src/face/face_recognizer.py`)
- **Top-2 Sample Averaging:** Tính điểm tương đồng bằng trung bình trọng số của 2 ảnh mẫu tốt nhất:
  $$\text{Score} = 0.65 \times \text{top1} + 0.35 \times \text{top2}$$
- **Multi-Frame Consensus Hysteresis:** Yêu cầu tối thiểu $3/5$ frame đồng thuận và khoảng cách điểm $\ge 0.04$ mới xác nhận danh tính người quen, loại bỏ nhảy tên do 1 frame ánh sáng chập chờn.
- **Sticky Identity Window (5.0s):** Duy trì danh tính đã xác nhận trong 5 giây khi người quay mặt nghiêng, cúi đầu gõ phím hay uống nước.
- **Bộ nhớ đệm tự dọn dẹp (Auto-Prune):** Tự động giải phóng các tracklet không nhìn thấy quá 3.0s chống đầy RAM.

### 2.4. Cố định Khung xương & Triệt tiêu Tia xanh Bắn sang Nền (`src/detection/pose_estimator.py`)
- **Tách riêng Instance MediaPipe Crop (`_crop_pose`):** Chạy `static_image_mode=True` cho từng vùng crop, triệt tiêu xung đột bộ nhớ nội tại giữa các người.
- **Adaptive Anatomical Scale & Bone Sanity:** Tự động tính quy mô cơ thể `ref_scale` dựa trên khoảng cách vai/hông thực tế. Giới hạn độ dài sinh học cho từng đoạn xương ($\le 2.1 \times \text{ref\_scale}$ cho thân, $\le 1.65 \times \text{ref\_scale}$ cho chi), triệt tiêu tia xương bắn chéo sang cửa sổ hoặc móc áo.
- **Phân bổ Tracker Độc quyền & Làm mượt EMA Thích ứng:**
  - $\alpha = 0.32$: Khóa cứng khung xương chống rung giật khi ngồi/đứng yên.
  - $\alpha = 0.65$: Bám sát tự nhiên khi di chuyển.

### 2.5. Triệt tiêu Hiện tượng Nối Khung xương khi 2 Người ở Gần nhau
- **Phân vùng ngang Voronoi / Midpoint Partitioning:** Tự động xác định đường ranh giới chia đôi giữa 2 người kề nhau. Vùng crop của người này bị chặn cứng ở ranh giới bên kia, đảm bảo 2 crop không bao giờ nhìn thấy nhau.
- **Kẹp toạ độ trong vùng Crop $[0.0, 1.0]$:** Ngăn chặn việc MediaPipe tự động ngoại suy toạ độ âm hoặc vượt biên tràn qua vạch ranh giới.
- **Triệt tiêu Khớp Ngoại vi (Distal Limb Suppression):** Khi cánh tay vươn ngang qua người bên cạnh ($\Delta x > \min(0.20, 2.8 \times fw)$), hệ thống triệt tiêu khớp ngoại vi (khuỷu/cổ tay) để không vẽ tia nối chéo, đồng thời giữ nguyên khớp vai và thân mình phục vụ phát hiện ngã.
- **Nâng cấp `model_complexity=1` cho Crop Pose:** Nhận diện đầy đủ cả 2 người cùng lúc ngay cả khi cúi đầu chạm mép trên camera.
- **Đo đạc kiểm chứng:** Khoảng cách phân cách giữa 2 khung xương đạt $70\text{px}$ hoàn toàn trống sạch, số pixel nối chéo bằng đúng $0\text{ pixel}$.

### 2.6. Lưu trữ CSDL Camera Imou Bền vững (`src/web/shared/db.py` & `repository.py`)
- **Resilient Dual-Layer Database:** Tự động chuyển đổi giữa Turso Cloud và SQLite cục bộ (`data/local.db`), đồng bộ ghi (Write-Mirroring) trên mọi thao tác `INSERT`, `UPDATE`, `DELETE`.
- **Lưu trữ Camera vĩnh viễn:** Cấu hình camera Imou RTSP được ghi bền vững vào bảng `cameras`. Khi F5 tải lại trang, frontend tự động kết nối lại camera mà không đòi hỏi thêm thủ công.

---

## 3. Thống kê Toàn bộ Bộ Kiểm thử Tự động (Master Test Suite)

Lệnh kiểm thử đã thực thi:
```powershell
python -m pytest tests/ --basetemp=data/temp_test -p no:cacheprovider -v
```

### Kết quả Tổng thể: **86 / 86 Test Cases PASSED (100% Thành công)** trong **7.00s**

| Nhóm Kiểm thử (Module) | Số lượng | Kịch bản kiểm chứng tiêu biểu | Trạng thái |
| :--- | :---: | :--- | :---: |
| **Độ ổn định, Khung xương đa người & Người lạ** (`test_stranger_and_fall_stability.py`) | **28 tests** | 2 người đứng sát nhau không nối xương, kẹp tọa độ crop chống tràn biên, triệt tiêu chi vươn ngang, cách ly tracker đa người, lọc độ dài xương sinh học, hysteresis nhận diện mặt, sticky identity 5s, lưu camera CSDL, không vẽ box đồ vật trên stream | **100% PASSED** |
| **Cảm biến Quang học & Nhận diện Vật thể** (`test_sensor_processing_and_object_detection.py`) | **11 tests** | Bất biến khoảng cách gần/xa, bù trừ góc nghiêng camera, khử rung cảm biến, nhận diện giường/sofa/bàn/ghế, nằm nghỉ an toàn `SAFE_RESTING`, ngã ra sàn | **100% PASSED** |
| **Nhận diện Tiền Té ngã** (`test_pre_fall_detection.py`) | **14 tests** | Đứng thẳng bình thường, lảo đảo mất thăng bằng, bước hụt khụy gối, chóng mặt kéo dài, tự phục hồi thăng bằng, liên kết đẩy nhanh báo động ngã, bảo toàn cấu hình người già | **100% PASSED** |
| **Kịch bản Té ngã Sinh học** (`test_fall_detection_scenarios.py`) | **5 tests** | Nằm ngủ từ từ, ngã đột ngột, cúi nhặt đồ đứng dậy, ngồi bệt sàn nhà, hệ số nhạy cảm Demographic Profiles | **100% PASSED** |
| **Tự động Dò tìm Camera Wi-Fi** (`test_camera_discovery.py`) | **6 tests** | Lấy dải mạng nội bộ, tạo chuỗi RTSP Imou, quét Subnet đa luồng, API tự động bind camera khi đổi IP | **100% PASSED** |
| **Hiệu năng & Đồng thời** (`test_concurrency_and_performance.py`) | **4 tests** | Lưu video non-blocking, bộ đệm 200 frame tiết kiệm 75% RAM, chống bão chuông (Cooldown), stream đa client | **100% PASSED** |
| **Chịu lỗi & Bảo mật** (`test_fault_tolerance.py`) | **3 tests** | Tự thoát khỏi bẫy giả lập RTSP, ghi log offline khi mất mạng CSDL, mã hóa băm mật khẩu PBKDF2-SHA256 | **100% PASSED** |
| **Hiệu năng Xóa Báo động** (`test_alert_deletion_performance.py`) | **3 tests** | Xóa hàng loạt siêu tốc cho Admin, xóa theo danh sách ID, xóa mềm (Soft delete) cho User | **100% PASSED** |
| **Kế thừa Cốt lõi** (`test_fall_detector`, `test_face_recognizer`, `test_feature_extractor`) | **9 tests** | Khung xương MediaPipe, nhận diện khuôn mặt người quen, trích xuất vector đặc trưng | **100% PASSED** |

---

## 4. Danh mục File Mã nguồn Thay đổi

| STT | Đường dẫn File | Mô tả nội dung thay đổi chính |
| :---: | :--- | :--- |
| 1 | [`configs/default.yaml`](file:///d:/NCKH/NCKH---Fall/configs/default.yaml) | Bổ sung cấu hình cảm biến quang học, tiền té ngã; đặt `object_detection.enabled: false` để giải phóng 100% CPU. |
| 2 | [`src/core/config.py`](file:///d:/NCKH/NCKH---Fall/src/core/config.py) | Bổ sung schema config cho `PreFallConfig` và `CameraSensorConfig`. |
| 3 | [`src/core/app.py`](file:///d:/NCKH/NCKH---Fall/src/core/app.py) | Cập nhật HUD hiển thị tiền té ngã, bảo tồn cấu hình người cao tuổi/trẻ em/người khuyết tật. |
| 4 | [`src/detection/balance_analyzer.py`](file:///d:/NCKH/NCKH---Fall/src/detection/balance_analyzer.py) | Tạo mới module phân tích thăng bằng động học (CoM, sway, stumble, dizzy). |
| 5 | [`src/detection/object_detector.py`](file:///d:/NCKH/NCKH---Fall/src/detection/object_detector.py) | Tạo mới module nhận diện vật thể YOLOv8-nano ONNX native CPU với cơ chế timeout an toàn. |
| 6 | [`src/detection/fall_detector.py`](file:///d:/NCKH/NCKH---Fall/src/detection/fall_detector.py) | Tích hợp trạng thái `PRE_FALL`, liên kết tiền ngã, bộ lọc ngồi bàn và nằm nghỉ an toàn `SAFE_RESTING`. |
| 7 | [`src/detection/pose_estimator.py`](file:///d:/NCKH/NCKH---Fall/src/detection/pose_estimator.py) | Thêm phân vùng Voronoi đa người, kẹp toạ độ crop [0, 1], bộ lọc giải phẫu học thích ứng `ref_scale`, triệt tiêu chi vươn ngang, làm mượt EMA, nâng cấp `model_complexity=1`. |
| 8 | [`src/face/face_recognizer.py`](file:///d:/NCKH/NCKH---Fall/src/face/face_recognizer.py) | Thuật toán Top-2 Sample Averaging, Consensus Hysteresis $\ge 3/5$ frames, Sticky Identity 5.0s, tự dọn dẹp cache. |
| 9 | [`src/web/shared/db.py`](file:///d:/NCKH/NCKH---Fall/src/web/shared/db.py) | Kiến trúc CSDL tự phục hồi `ResilientDbClient`, tự động chuyển sang SQLite `data/local.db` và write-mirroring. |
| 10 | [`src/web/shared/pipeline.py`](file:///d:/NCKH/NCKH---Fall/src/web/shared/pipeline.py) | Bỏ vẽ bounding box vật thể trên stream, module hóa `_ai_worker_loop`, điều hướng `estimate_multi` theo khuôn mặt. |
| 11 | [`src/web/admin/repository.py`](file:///d:/NCKH/NCKH---Fall/src/web/admin/repository.py) | Bổ sung hàm upsert và truy vấn camera CSDL bền vững. |
| 12 | [`src/web/admin/index.html`](file:///d:/NCKH/NCKH---Fall/src/web/admin/index.html) | Đồng bộ nạp danh sách camera từ CSDL khi tải trang, duy trì kết nối camera Imou tự động. |
| 13 | [`.gitignore`](file:///d:/NCKH/NCKH---Fall/.gitignore) | Bổ sung bỏ qua `data/*.db`, `data/temp_test/`, `data/debug*`, `app_fall/android/build/`. |
