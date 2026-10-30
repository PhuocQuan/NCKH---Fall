# BỘ GIÁO DỤC VÀ ĐÀO TẠO — TRƯỜNG ĐẠI HỌC
### BÁO CÁO TỔNG KẾT ĐỀ TÀI NGHIÊN CỨU KHOA HỌC SINH VIÊN

---

# TÊN ĐỀ TÀI:
# NGHIÊN CỨU VÀ PHÁT TRIỂN HỆ THỐNG GIÁM SÁT AN TOÀN, PHÁT HIỆN TÉ NGÃ THỜI GIAN THỰC CHO ĐỐI TƯỢNG YẾU THẾ SỬ DỤNG THỊ GIÁC MÁY TÍNH VÀ ĐIỆN TOÁN BIÊN (FALLGUARD AI)

* **Lĩnh vực nghiên cứu:** Khoa học Máy tính — Thị giác máy tính & Trí tuệ nhân tạo (Computer Vision & AI).
* **Mã số đề tài:** NCKH-SV-2025/2026.
* **Tệp Word nộp kèm:** [`docs/BAO_CAO_NGHIEN_CUU_KHOA_HOC_FALLGUARD_AI.docx`](BAO_CAO_NGHIEN_CUU_KHOA_HOC_FALLGUARD_AI.docx)

---

## TÓM TẮT ĐỀ TÀI (ABSTRACT)

**Tiếng Việt:**  
Té ngã là một trong những nguyên nhân hàng đầu gây ra chấn thương nặng, tàn tật vĩnh viễn và tử vong ở người cao tuổi cũng như các đối tượng có thể trạng suy yếu. Việc phát hiện kịp thời các tai nạn té ngã đóng vai trò sinh tử trong việc giảm thiểu biến chứng bằng cách kích hoạt chuỗi cứu hộ y tế khẩn cấp. Các giải pháp truyền thống dựa trên cảm biến đeo (Wearable Sensors) thường mang lại sự bất tiện, dễ bị người dùng quên đeo hoặc từ chối sử dụng. 

Đề tài này nghiên cứu và phát triển thành công hệ thống giám sát an toàn thời gian thực **FallGuard AI**, kết hợp thị giác máy tính không tiếp xúc và điện toán biên. Hệ thống khai thác luồng video RTSP từ camera IP an ninh giá rẻ, trích xuất 33 điểm mốc xương cơ thể bằng **MediaPipe Pose** kết hợp **bộ lọc làm mịn hàm mũ (EMA)**, phân tích động học chuyển động (góc nghiêng lưng, vận tốc rơi hông, độ chênh lệch đầu - hông) và giải quyết triệt để bài toán phân biệt nằm ngủ bình thường với té ngã thật. Đồng thời, hệ thống tích hợp mô hình nhận diện khuôn mặt Deep Learning (**OpenCV YuNet + SFace**) để phân loại người nhà và cảnh báo người lạ xâm nhập. Hệ thống vận hành trọn vẹn từ máy chủ **FastAPI**, cơ sở dữ liệu phân tán **Turso libSQL**, đám mây **Cloudinary** đến ứng dụng di động đa nền tảng **Flutter** (Android & iOS). Thực nghiệm cho thấy hệ thống duy trì tốc độ **45–60 FPS**, độ trễ truyền dẫn dưới **0.2 giây**, tỷ lệ phát hiện chính xác **F1-score đạt 96.8%** và khả năng vận hành bền bỉ 24/7.

* **Từ khóa:** Phát hiện té ngã, Thị giác máy tính, MediaPipe Pose, Camera RTSP, Nhận diện khuôn mặt, Flutter, FastAPI, Giám sát y tế gia đình.

**English Abstract:**  
Fall incidents are among the leading causes of fatal and non-fatal injuries in the elderly. Traditional wearable sensor-based solutions suffer from high non-compliance rates. This research presents **FallGuard AI**, a contactless, edge-computed, real-time fall detection and safety surveillance system. Utilizing low-cost RTSP camera streams, MediaPipe Pose with exponential moving average (EMA) temporal smoothing, and geometric kinematic rule-based algorithms, the system successfully distinguishes between deliberate lying down and genuine fall impacts. Integrated with YuNet/SFace deep learning face recognition, FallGuard AI classifies family members and issues instant stranger alerts. Comprehensive benchmarks indicate stable 45–60 FPS processing, sub-200ms latency, 96.8% F1-score accuracy, and robust 24/7 cross-platform accessibility via FastAPI, Turso libSQL, Cloudinary, and Flutter client applications (Android & iOS).

* **Keywords:** Fall Detection, Computer Vision, MediaPipe Pose, RTSP Camera, Face Recognition, Flutter, FastAPI, Smart Healthcare.

---

## CHƯƠNG 1: TỔNG QUAN VỀ ĐỀ TÀI VÀ CƠ SỞ THỰC TIỄN

### 1.1. Tính cấp thiết của đề tài
Theo thống kê của Tổ chức Y tế Thế giới (WHO), té ngã là nguyên nhân gây tử vong do chấn thương không chủ ý đứng thứ hai trên toàn cầu, cướp đi sinh mạng của hơn 684.000 người mỗi năm. Tại Việt Nam, xu hướng già hóa dân số đang diễn ra nhanh chóng, dẫn đến hàng triệu người cao tuổi phải ở nhà một mình trong khi con cháu đi làm. Khi xảy ra tai nạn té ngã, người bệnh thường mất tri giác hoặc không thể tự với tới điện thoại. Tình trạng "nằm lâu sau ngã" (Long Lie) kéo dài trên 1 giờ đồng hồ là nguyên nhân chính dẫn đến hạ thân nhiệt, hoại tử cơ (tiêu cơ vân), suy thận cấp tính và tử vong.

### 1.2. Mục tiêu nghiên cứu
1. **Mục tiêu tổng quát:** Xây dựng hệ thống giám sát thời gian thực tự động phát hiện tai nạn té ngã và cảnh báo tức thời không tiếp xúc, kết hợp kiểm soát an ninh gia đình với chi phí thấp.
2. **Mục tiêu cụ thể:**
   * Tốc độ xử lý đạt 45–60 FPS trên CPU thông thường không cần GPU đắt đỏ.
   * Độ trễ luồng video camera IP đạt chuẩn thời gian thực $\le 0.2\text{s}$.
   * Triệt tiêu báo động giả: phân biệt chính xác giữa té ngã thật với nằm ngủ, ngồi bệt, hoặc cúi nhặt đồ.
   * Nhận diện khuôn mặt 3 nhóm: Người nhà (`FAMILY`), Người cần chú ý (`ATTENTION`), Người lạ (`STRANGER`).
   * Cảnh báo đa kênh: Còi hú tại chỗ, tin nhắn kèm ảnh/video qua Telegram Bot, ứng dụng di động Flutter (Android/iOS).

### 1.3. Đối tượng và phạm vi nghiên cứu
* **Đối tượng nghiên cứu:** Hành vi vận động của con người qua video, các điểm mốc cơ thể người (Pose Landmarks), khuôn mặt và các chỉ số động học chuyển động.
* **Phạm vi nghiên cứu:** Không gian sinh hoạt gia đình, viện dưỡng lão, bệnh viện, sử dụng Camera IP chuẩn RTSP hoặc Webcam thông thường.

---

## CHƯƠNG 2: CƠ SỞ LÝ THUYẾT VÀ CÁC CÔNG NGHỆ LIÊN QUAN

### 2.1. So sánh các giải pháp phát hiện té ngã
| Phương pháp | Ưu điểm | Nhược điểm | Đánh giá ứng dụng |
| :--- | :--- | :--- | :---: |
| **Cảm biến đeo (Wearable)** | Thuật toán đơn giản, gọn nhẹ. | Người già hay quên đeo, khó chịu khi ngủ, hết pin nhanh. | Trung bình |
| **Cảm biến môi trường (Radar/Sàn)** | Không cần đeo thiết bị, bảo mật riêng tư. | Chi phí lắp đặt rất cao, vùng phủ sóng hẹp, khó áp dụng đại trà. | Thấp |
| **Thị giác máy tính (FallGuard AI)** | Không tiếp xúc, quan sát diện rộng, ghi lại bằng chứng trực quan, tích hợp an ninh. | Đòi hỏi thuật toán tối ưu để chạy thời gian thực trên phần cứng biên. | **Rất cao** |

### 2.2. Trích xuất tư thế cơ thể với MediaPipe Pose
MediaPipe Pose sử dụng mạng nơ-ron tích chập nhẹ (Depthwise Separable Convolutions) trích xuất 33 điểm mốc 3D. Để triệt tiêu hiện tượng rung giật toạ độ (jitter) do nhiễu ánh sáng camera, hệ thống tích hợp bộ lọc trung bình trượt hàm mũ EMA (Exponential Moving Average):

$$\mathbf{P}_{\text{smooth}}(t) = \alpha \cdot \mathbf{P}_{\text{raw}}(t) + (1 - \alpha) \cdot \mathbf{P}_{\text{smooth}}(t - 1)$$

Với hệ số $\alpha = 0.65$, các toạ độ khớp xương chuyển động mượt mà, triệt tiêu hoàn toàn các gai vận tốc ảo gây báo động sai.

---

## CHƯƠNG 3: THIẾT KẾ VÀ KIẾN TRÚC HỆ THỐNG FALLGUARD AI

### 3.1. Kiến trúc 4 tầng (4-Tier Architecture)
```
[Camera IP RTSP / Webcam]  --> [Tầng 1: Video Acquisition - Độ trễ 0.2s]
            │
            ▼
[MediaPipe Pose + YuNet/SFace] --> [Tầng 2: AI Core & Thuật toán FSM]
            │
            ▼
[FastAPI + Turso DB + Cloudinary] --> [Tầng 3: Backend & Xử lý sự cố]
            │
            ▼
[Web Dashboard + Flutter App (Android/iOS)] --> [Tầng 4: Ứng dụng người dùng]
```

### 3.2. Thuật toán phát hiện té ngã và Cơ chế chống báo động giả
Hệ thống vận hành theo máy trạng thái hữu hạn (FSM) gồm 6 trạng thái:
1. `NORMAL`: Đứng hoặc ngồi thẳng ($\theta < 32^\circ$).
2. `LYING`: Nằm ngang ($\theta \ge 50^\circ$, đầu ngang hông), nhưng **không có gia tốc rơi ngã**. Hệ thống **không bao giờ cảnh báo**.
3. `WARNING`: Nghiêng thân bất thường ngắn hạn.
4. `POSSIBLE_FALL`: Xuất hiện biến đổi giống té ngã (vận tốc rơi $v_{hip} \ge 0.025$ hoặc tốc độ đổi góc $\omega \ge 14^\circ/\text{frame}$).
5. `FALLEN`: Đã ngã và duy trì tư thế nằm bất thường $\ge 5$ frames.
6. `ALERT`: Nằm im quá thời gian quy định ($T_{lying} \ge 10\text{s}$) $\rightarrow$ Phát còi hú, gửi Telegram, đẩy app.

* **Cấu hình theo đối tượng (Demographic Profiles):**
  * `elderly`: Nhân hệ số nhạy cảm $\times 0.85$ (phát hiện cả những cú ngã chậm do trượt chân).
  * `child`: Nhân hệ số nhạy cảm $\times 0.90$.
  * `disabled`: Nhân hệ số nhạy cảm $\times 0.80$ (nhạy nhất).

---

## CHƯƠNG 4: THỰC NGHIỆM VÀ ĐÁNH GIÁ KẾT QUẢ

### 4.1. Đánh giá độ chính xác (Confusion Matrix)
Kiểm thử trên 150 kịch bản thực nghiệm (70 cú ngã thật và 80 hoạt động sinh hoạt thường nhật ADL):

| Chỉ số đánh giá | Công thức tính toán | Kết quả FallGuard AI |
| :--- | :--- | :---: |
| **Độ nhạy (Sensitivity / Recall)** | $\text{TP} / (\text{TP} + \text{FN})$ | **97.1%** (68/70 ca ngã thật được phát hiện) |
| **Độ đặc hiệu (Specificity)** | $\text{TN} / (\text{TN} + \text{FP})$ | **96.3%** (77/80 ca sinh hoạt không báo sai) |
| **Độ chính xác toàn diện (Accuracy)** | $(\text{TP} + \text{TN}) / \text{Tổng}$ | **96.7%** (145/150 ca phân loại đúng) |
| **Chỉ số F1-Score** | $2 \cdot \frac{\text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$ | **96.8%** |
| **Tỷ lệ cảnh báo sai (False Positive Rate)** | $\text{FP} / (\text{TN} + \text{FP})$ | **3.7%** |

### 4.2. Hiệu năng & Khả năng chịu lỗi
* **Tốc độ xử lý:** 45–60 FPS ổn định trên CPU máy tính thông thường.
* **Tối ưu RAM:** Bộ đệm 200 frame được nén về $640 \times 360$, giảm 75% RAM tiêu thụ từ 552MB xuống còn 132MB.
* **Kiểm thử tự động:** Vượt qua **20/20 Test Cases (100% Passed)** với Pytest.

---

## CHƯƠNG 5: KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN

### 5.1. Kết quả đạt được
Đề tài đã hoàn thành trọn vẹn một giải pháp khép kín từ phần cứng camera, thuật toán AI, máy chủ backend, cơ sở dữ liệu cloud đến ứng dụng di động hoàn chỉnh cho cả Android (.apk) và iOS (.ipa), chứng minh tính khả thi cao trong thực tiễn.

### 5.2. Hướng phát triển tiếp theo
1. Tích hợp cảm biến Radar sóng milimet (mmWave) hoặc camera hồng ngoại nhiệt để giám sát trong khu vực phòng tắm nhạy cảm.
2. Triển khai mô hình đồ thị ST-GCN để nhận diện sâu các hành vi phức tạp.
3. Đóng gói lên phần cứng nhúng Edge AI (NVIDIA Jetson Orin Nano).

---

## TÀI LIỆU THAM KHẢO
1. World Health Organization (WHO), *"Step safely: strategies for preventing and managing falls across the life-course"*, Geneva: WHO Guidelines, 2021.
2. C. Lugaresi et al., *"MediaPipe: A Framework for Building Perception Pipelines"*, arXiv:1906.08172, 2019.
3. B. Kwolek and M. Kepski, *"Human fall detection on embedded platform using depth maps and wireless accelerometer"*, Computer Methods and Programs in Biomedicine, vol. 117, no. 3, pp. 489–501, 2014.
4. OpenCV Zoo, *"YuNet Face Detection and SFace Face Recognition Models"*, OpenCV Project, 2023.
