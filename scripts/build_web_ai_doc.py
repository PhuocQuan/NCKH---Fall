"""
Script tạo tài liệu học tập và giải thích toàn bộ mã nguồn chuyên sâu:
Phần 1: WEB, BACKEND & AI CORE (FastAPI, OpenCV, MediaPipe, Turso, Cloudinary, Telegram)
Tạo file: docs/GIAI_THICH_VA_HOC_TAP_WEB_BACKEND_AI.docx và .md
"""

from scripts.docx_builder import DocxBuilder


def build_web_backend_ai_doc():
    print("[2/3] Dang tao Tai lieu Hoc tap Chuyen sau: Web, Backend & AI Core...")
    doc = DocxBuilder(
        title="CẨM NANG HỌC TẬP VÀ GIẢI MÃ TOÀN BỘ HỆ THỐNG: WEB, BACKEND & AI CORE",
        author="FallGuard AI Engineering Team"
    )

    doc.add_title("CẨM NANG HỌC TẬP VÀ GIẢI MÃ TOÀN BỘ DỰ ÁN\nCHUYÊN ĐỀ 1: WEB, BACKEND & THỊ GIÁC MÁY TÍNH AI")
    doc.add_subtitle("Hệ thống FallGuard AI - Hướng dẫn chi tiết từng dòng code, nguyên lý hoạt động và bộ câu hỏi bảo vệ NCKH")

    doc.add_callout(
        "Mục đích tài liệu: Giúp thành viên trong nhóm, sinh viên hoặc lập trình viên mới có thể tự học, hiểu sâu 100% "
        "từng dòng code, tự tin thuyết trình và trả lời bất kỳ câu hỏi phản biện nào của Hội đồng Giám khảo về mảng Server, "
        "Thị giác máy tính AI, Cơ sở dữ liệu và Tích hợp Đám mây.",
        title="DÀNH CHO BACKEND & AI ENGINEER"
    )

    doc.add_heading_1("PHẦN 1: BẢN ĐỒ KIẾN TRÚC MÃ NGUỒN (CODE MAP)")
    doc.add_paragraph(
        "Toàn bộ mã nguồn phía máy chủ và AI nằm trong thư mục src/ với cấu trúc phân tầng rõ ràng:"
    )
    headers_map = ["Thư mục / Module", "Tệp mã nguồn chính", "Nhiệm vụ & Chức năng cốt lõi"]
    rows_map = [
        ["src/camera/", "video_source.py\ncheck_camera.py", "Mở camera (Webcam, RTSP Imou, Video test), luồng đọc ngầm FFmpeg độ trễ 0s, tự kết nối lại khi mất điện."],
        ["src/detection/", "pose_estimator.py\nfall_detector.py\nfeature_extractor.py", "Trích xuất 33 khớp xương bằng MediaPipe Pose, lọc rung EMA, thuật toán máy trạng thái FSM nhận diện té ngã và chống báo động giả."],
        ["src/face/", "face_recognizer.py", "Nhận diện khuôn mặt Deep Learning ONNX (YuNet + SFace), phân loại Người nhà / Cần chú ý / Người lạ."],
        ["src/ai/", "ai_classifier.py\ntrain_ai_model.py", "Mô hình Machine Learning (Random Forest/SVM) phụ trợ dự đoán chuỗi hành động té ngã."],
        ["src/web/shared/", "server.py\npipeline.py\ndb.py\ncloudinary_uploader.py\nnotifications.py\nauth.py", "Máy chủ FastAPI, quản lý luồng ngầm AI, kết nối cơ sở dữ liệu Turso libSQL, tải media lên Cloudinary, gửi Telegram và mã hóa mật khẩu PBKDF2."],
        ["src/web/admin/", "index.html, router.py, service.py", "Cổng thông tin quản trị: xem trực tiếp tất cả camera, quản lý người dùng, chỉnh sửa ngưỡng nhạy."],
        ["src/web/user/", "index.html, router.py", "Giao diện người thân: theo dõi camera gia đình, xem lịch sử cảnh báo ngã, xem video bằng chứng."]
    ]
    doc.add_table(headers_map, rows_map)

    doc.add_heading_1("PHẦN 2: GIẢI MÃ TỪNG MODULE CỐT LÕI (DEEP-DIVE CODE ANALYSIS)")
    
    # 2.1 Video Source
    doc.add_heading_2("2.1. Module Thu nhận Video & Triệt tiêu Độ trễ (src/camera/video_source.py)")
    doc.add_paragraph(
        "Camera IP gia đình (như Imou Ranger 2) truyền dữ liệu qua giao thức RTSP (Real-Time Streaming Protocol). "
        "Mặc định, OpenCV sử dụng bộ đệm mạng tích lũy (network buffer) từ 15 đến 30 giây, dẫn đến việc xem trực tiếp bị trễ rất nặng.",
        bold_prefix="Vấn đề gặp phải:"
    )
    doc.add_paragraph(
        "Hệ thống áp dụng 2 kỹ thuật tối ưu hóa then chốt:",
        bold_prefix="Giải pháp công nghệ:"
    )
    doc.add_bullet("1. Cờ FFmpeg Low-Latency: Thiết lập 'flags=low_delay|fflags=nobuffer|analyzeduration=0|probesize=32' ép FFmpeg giải mã ngay lập tức từng gói tin NAL mà không chờ nạp đệm.")
    doc.add_bullet("2. Luồng đọc khung hình độc lập (_reader_loop): Một daemon thread chạy liên tục với vòng lặp cap.read(), luôn giữ khung hình mới nhất trong self._latest_frame và xả sạch các frame cũ.")
    doc.add_bullet("3. Thoát khỏi bẫy giả lập (MockVideoCapture Trap): Khi camera bị ngắt điện, hệ thống tạm dùng simulator. Cứ mỗi 5 giây, phương thức read() tự động gọi _open_real_only() để thăm dò; khi camera có điện lại, hệ thống tự động hoán đổi và kết nối lại ngay lập tức.")
    doc.add_code_block(
        "# Trích đoạn mã nguồn tự phục hồi trong src/camera/video_source.py:\n"
        "if isinstance(self.capture, MockVideoCapture):\n"
        "    now = time.time()\n"
        "    if _is_live_stream(self.source) and (now - self._last_reconnect_time > 5.0):\n"
        "        self._last_reconnect_time = now\n"
        "        real = self._open_real_only()\n"
        "        if real is not None:\n"
        "            self.capture = real\n"
        "            self._thread = threading.Thread(target=self._reader_loop, daemon=True)\n"
        "            self._thread.start()"
    )

    # 2.2 Pose Estimator
    doc.add_heading_2("2.2. Trích xuất Tư thế & Bộ lọc EMA Smoothing (src/detection/pose_estimator.py)")
    doc.add_paragraph(
        "MediaPipe Pose cung cấp 33 điểm mốc (Pose Landmarks). Tuy nhiên, trong điều kiện camera thực tế có ánh sáng yếu, các điểm mốc thường bị rung giật (jitter). "
        "Nếu tính vận tốc rơi dựa trên toạ độ rung này, hệ thống sẽ phát sinh các gai xung vận tốc ảo (false velocity spikes) dẫn đến báo động ngã sai."
    )
    doc.add_paragraph(
        "Để giải quyết triệt để, hệ thống áp dụng bộ lọc trung bình trượt hàm mũ EMA (Exponential Moving Average) với hệ số α = 0.65:",
        bold_prefix="Giải thuật làm mịn:"
    )
    doc.add_code_block(
        "# Thuật toán lọc EMA trong pose_estimator.py:\n"
        "alpha = 0.65  # 65% frame hiện tại, 35% frame lịch sử\n"
        "for key, pt in points.items():\n"
        "    prev = self._prev_points[key]\n"
        "    smoothed_points[key] = Point(\n"
        "        x=prev.x * (1 - alpha) + pt.x * alpha,\n"
        "        y=prev.y * (1 - alpha) + pt.y * alpha,\n"
        "        visibility=pt.visibility\n"
        "    )"
    )
    doc.add_paragraph(
        "Đồng thời, hệ thống tích hợp bộ lọc đồ vật tĩnh (Static Object Filter): Nếu một cụm điểm mốc đứng yên tuyệt đối qua hơn 60 frame liên tục "
        "(độ dịch chuyển < 0.0005) với độ tin cậy thấp, hệ thống xác định đó là ghế, bàn hoặc áo treo tường và loại bỏ ngay lập tức."
    )

    # 2.3 Fall Detector
    doc.add_heading_2("2.3. Giải mã Thuật toán Phát hiện Té ngã (src/detection/fall_detector.py)")
    doc.add_paragraph(
        "Thuật toán FallDetector là 'trái tim' của hệ thống, hoạt động theo máy trạng thái hữu hạn FSM có khả năng giải thích được (Explainable AI):"
    )
    headers_fsm = ["Trạng thái (State)", "Màu sắc", "Điều kiện kích hoạt", "Ý nghĩa trong thực tế"]
    rows_fsm = [
        ["NORMAL", "Xanh lá (70, 200, 90)", "Góc thân nghiêng < 32° hoặc đang đứng/ngồi thẳng.", "Người dùng sinh hoạt bình thường."],
        ["LYING", "Xám (180, 180, 180)", "Góc thân > 50°, đầu ngang hông, KHÔNG có rơi nhanh.", "Người đang nằm ngủ, nằm xem tivi trên giường/sàn."],
        ["WARNING", "Vàng cam (0, 190, 255)", "Góc thân nghiêng bất thường trong 2–4 frames.", "Người cúi người, chới với hoặc mất thăng bằng nhẹ."],
        ["POSSIBLE_FALL", "Cam đậm (0, 140, 255)", "Có chuyển động rơi nhanh (fall_like_transition = True).", "Nghi ngờ có sự cố ngã vừa diễn ra."],
        ["FALLEN", "Đỏ sẫm (40, 40, 230)", "Duy trì tư thế nằm bất thường >= 5 frames.", "Xác nhận đã ngã xuống sàn, bắt đầu đếm thời gian nằm."],
        ["ALERT", "Đỏ tươi (0, 0, 255)", "Nằm im trên sàn quá thời gian quy định (mặc định 10s).", "Báo động khẩn cấp: hú còi, gửi Telegram, đẩy app!"]
    ]
    doc.add_table(headers_fsm, rows_fsm)

    doc.add_callout(
        "BÍ QUYẾT PHÂN BIỆT NẰM NGỦ VÀ TÉ NGÃ:\n"
        "Một cú ngã thật bắt buộc phải có chuỗi biến đổi hình học (fall_like_transition = True):\n"
        "1. Trước đó đang đứng thẳng (recent_upright_frames >= 2).\n"
        "2. Vận tốc hông rơi nhanh (hip_velocity >= 0.025) HOẶC góc thân xoay nhanh (angle_velocity >= 14°/frame).\n"
        "3. Thân người đổ ngang (torso_fall_angle >= 52°).\n"
        "Nếu người dùng chỉ từ từ nằm xuống nệm/sàn, các chỉ số vận tốc đều ở dưới ngưỡng -> Hệ thống chỉ gán trạng thái LYING và KHÔNG BAO GIỜ kích hoạt còi báo động!",
        title="LOGIC CỐT LÕI ĐƯỢC GIÁM KHẢO NCKH QUAN TÂM NHẤT"
    )

    # 2.4 Face Recognizer
    doc.add_heading_2("2.4. Nhận diện Khuôn mặt Đa tầng & Cảnh báo Người lạ (src/face/face_recognizer.py)")
    doc.add_paragraph(
        "Không dùng thư viện `face_recognition` nặng nề phụ thuộc dlib C++, FallGuard AI tích hợp mô hình Deep Learning chuẩn quốc tế của OpenCV Zoo:"
    )
    doc.add_bullet("1. Phát hiện khuôn mặt: Mô hình YuNet ONNX (face_detection_yunet_2023mar.onnx) với tốc độ xử lý siêu nhanh (~3ms/frame), nhận diện được khuôn mặt ở nhiều góc độ và khoảng cách.")
    doc.add_bullet("2. Trích xuất đặc trưng khuôn mặt: Mô hình SFace ONNX (face_recognition_sface_2021dec.onnx) biến khuôn mặt thành vector 128 chiều (Embedding Vector).")
    doc.add_bullet("3. So sánh nhận dạng: Tính Cosine Similarity giữa vector khuôn mặt hiện tại và thư mục data/known_faces/. Nếu similarity >= 0.35 -> Nhận dạng người quen. Nếu < 0.35 -> Gán nhãn STRANGER (Người lạ).")
    doc.add_bullet("4. Chống bão cảnh báo người lạ (Stranger Debounce): Người lạ phải xuất hiện liên tục >= 15 frame (~1-1.5s) mới phát còi, và khóa phiên theo dõi (_stranger_active_session = True) để không kêu lặp lại suốt thời gian người đó còn đứng trong phòng.")

    # 2.5 Pipeline & Server
    doc.add_heading_2("2.5. Máy chủ Backend FastAPI & Quản lý Pipeline (src/web/server.py, pipeline.py)")
    doc.add_bullet("Cơ chế Tự động Giám sát 24/7 (Auto-Start): Khi server bật qua lệnh python -m src.web.server, hàm lifespan tự động kích hoạt luồng AI đọc camera từ database.")
    doc.add_bullet("Cơ chế Chó canh phòng (Watchdog Loop): Một tiến trình nền độc lập kiểm tra mỗi 15 giây. Nếu pipeline AI bị dừng đột ngột (do lỗi driver camera hoặc đứt mạng), Watchdog tự động khởi động lại pipeline.")
    doc.add_bullet("Tối ưu hóa RAM Frame Buffer: Phương thức _buffer_frame() tự động resize khung hình về 640x360 pixels khi lưu vào buffer quay clip biến cố, giúp giảm 75% RAM tiêu thụ (từ 552MB xuống còn 132MB) và triệt tiêu giật lag.")
    doc.add_bullet("Phát video trực tiếp chuẩn MJPEG: Endpoint /api/live/stream xuất luồng multipart/x-mixed-replace; boundary=frame cho phép cả trình duyệt Web và ứng dụng di động xem trực tiếp không cần cài đặt thêm plugin.")

    # 2.6 Database & Cloud
    doc.add_heading_2("2.6. Cơ sở dữ liệu Turso libSQL & Đám mây Cloudinary (src/web/shared/db.py, cloudinary_uploader.py)")
    doc.add_bullet("Turso libSQL: Cơ sở dữ liệu SQLite phân tán trên nền tảng Cloud, kết nối qua giao thức HTTP API không phụ thuộc driver C cục bộ. Lưu trữ bảng users, cameras, alerts, app_state, system_logs.")
    doc.add_bullet("Cơ chế Ghi log Ngoại tuyến (Offline Fallback): Khi mất mạng Internet, hàm log_action() tự động bắt ngoại lệ và ghi vào file nội bộ data/system_logs_offline.csv dự phòng, bảo đảm an toàn dữ liệu 100%.")
    doc.add_bullet("Cloudinary Cloud Storage: Khi phát hiện té ngã, luồng ngầm cắt đoạn video 5–10 giây kèm ảnh snapshot vẽ khung xương, tự động upload lên Cloudinary và lưu đường dẫn trực tuyến (URL) vào cơ sở dữ liệu.")

    # 2.7 Security & Auth
    doc.add_heading_2("2.7. Cơ chế Bảo mật: PBKDF2-SHA256 & JWT Token (src/web/shared/auth.py)")
    doc.add_paragraph(
        "Hệ thống tuân thủ các chuẩn an toàn thông tin hiện đại:"
    )
    doc.add_bullet("Mật khẩu băm an toàn: Sử dụng PBKDF2-HMAC-SHA256 với 16 bytes salt ngẫu nhiên và 100,000 vòng lặp, lưu dưới dạng $pbkdf2-sha256$100000$salt$hash. Miễn nhiễm hoàn toàn với tấn công Rainbow Table.")
    doc.add_bullet("Chống Timing Attack: Sử dụng hmac.compare_digest để so sánh chuỗi mật khẩu trong thời gian hằng số.")
    doc.add_bullet("Xác thực JWT: Cấp mã JSON Web Token có thời hạn 12 giờ, ký bằng khóa bí mật 64-bytes an toàn theo RFC 7518.")
    doc.add_bullet("Phân quyền vai trò (RBAC): Phân chia rành mạch giữa Admin (toàn quyền cấu hình camera, xem log) và User (chỉ xem camera được phân quyền).")

    doc.add_heading_1("PHẦN 3: BỘ 15 CÂU HỎI VẤN ĐÁP BẢO VỆ NCKH (DÀNH CHO WEB / AI LEAD)")
    
    qa_list = [
        ("Câu 1: Tại sao nhóm chọn MediaPipe Pose thay vì YOLOv8-Pose hay OpenPose?",
         "MediaPipe Pose được thiết kế chuyên biệt cho xử lý thời gian thực trên CPU với kiến trúc tích chập nhẹ (Depthwise Separable Convolution). OpenPose quá nặng (chỉ đạt 5-10 FPS trên CPU), còn YOLOv8-Pose yêu cầu cấu hình GPU rời đắt đỏ. MediaPipe giúp hệ thống đạt 45-60 FPS ngay trên máy tính văn phòng hoặc thiết bị nhúng giá rẻ."),
        
        ("Câu 2: Làm thế nào hệ thống phân biệt được người nằm ngủ với người bị té ngã?",
         "Hệ thống dựa trên chuỗi biến đổi hình học (fall_like_transition). Người ngã thật bắt buộc phải có gia tốc rơi hông nhanh (v_hip >= 0.025) và đổi góc thân đột ngột (angle_velocity >= 14°/frame) từ tư thế đứng trước đó. Người nằm ngủ từ từ không có các gai xung vận tốc này, hệ thống sẽ gán trạng thái LYING và không phát chuông cảnh báo."),
         
        ("Câu 3: Bộ lọc EMA giải quyết vấn đề gì trong xử lý khung xương?",
         "EMA (Exponential Moving Average) giải quyết hiện tượng rung giật toạ độ (jitter) do nhiễu ánh sáng camera. Bằng cách lấy trung bình có trọng số (65% frame hiện tại + 35% frame trước), các toạ độ khớp xương chuyển động mượt mà, triệt tiêu các gai vận tốc ảo gây báo động sai."),
         
        ("Câu 4: Tại sao hệ thống lại đạt được độ trễ RTSP dưới 0.2 giây?",
         "Nhờ kết hợp 2 kỹ thuật: cấu hình FFmpeg low-latency ('fflags=nobuffer|flags=low_delay') và luồng đọc khung hình ngầm độc lập (_reader_loop) liên tục xả sạch bộ đệm mạng OpenCV. Ứng dụng luôn được cấp frame mới nhất tức thời."),
         
        ("Câu 5: Khi camera bị mất điện hoặc rút dây mạng, hệ thống xử lý ra sao?",
         "Hệ thống phát hiện sau 30 frame lỗi và chuyển sang camera giả lập (MockVideoCapture) để server không bị crash. Đồng thời, một luồng thăm dò tự động thử kết nối lại mỗi 5 giây. Ngay khi camera có điện lại, hệ thống tự động hoán đổi và khôi phục live stream bình thường mà không cần restart server."),
         
        ("Câu 6: Cơ chế chống bão thông báo (Anti-spam Debounce) hoạt động như thế nào?",
         "Khi nạn nhân ngã và nằm bất động, sau khi phát cảnh báo ALERT lần đầu tiên, hệ thống bật cờ _alert_active và đặt bộ đếm hồi chiêu (cooldown_frames). Telegram và App chỉ nhận đúng 1 thông báo ban đầu kèm clip, tuyệt đối không bị spam tin nhắn liên tục mỗi giây."),
         
        ("Câu 7: Việc lưu 200 frame để quay video biến cố có làm tràn bộ nhớ RAM không?",
         "Không, vì nhóm đã tối ưu hàm _buffer_frame() tự động nén kích thước frame về 640x360 pixels trước khi đưa vào hàng đệm deque(maxlen=200). Dung lượng 200 frame chỉ tốn ~132MB RAM thay vì ~552MB như ban đầu, tiết kiệm 75% bộ nhớ và giải phóng áp lực cho bộ gom rác Python."),
         
        ("Câu 8: Tại sao lại chọn cơ sở dữ liệu Turso libSQL thay vì MySQL hay SQLite truyền thống?",
         "SQLite truyền thống lưu file cục bộ, khó đồng bộ khi mở rộng nhiều chi nhánh hoặc kết nối với server đám mây. MySQL/PostgreSQL thì cồng kềnh, tốn chi phí duy trì server DB. Turso libSQL là giải pháp serverless SQLite trên Cloud, truy vấn qua HTTP API siêu nhẹ, bảo mật và miễn phí cho quy mô vừa và nhỏ."),
         
        ("Câu 9: Cơ chế ghi log ngoại tuyến hoạt động ra sao khi mất mạng Internet?",
         "Trong file db.py, khi câu lệnh truy vấn tới Turso bị timeout do mất Internet, khối lệnh try...except sẽ tự động bắt lỗi và chuyển hướng ghi dữ liệu vào file CSV nội bộ (data/system_logs_offline.csv). Khi có mạng trở lại, quản trị viên có thể đồng bộ ngược lên Cloud."),
         
        ("Câu 10: Nhận diện khuôn mặt YuNet + SFace có ưu điểm gì so với thư viện face_recognition thông thường?",
         "Thư viện face_recognition thông thường phụ thuộc vào thư viện dlib viết bằng C++ rất khó cài đặt trên Windows và chạy chậm. YuNet và SFace là mô hình Deep Learning chuẩn của OpenCV Zoo định dạng ONNX, chạy đa luồng trực tiếp qua OpenCV DNN với tốc độ nhận diện dưới 5ms, độ chính xác cao ngay cả khi mặt nghiêng."),
         
        ("Câu 11: Mật khẩu người dùng được bảo vệ như thế nào?",
         "Mật khẩu được băm bằng thuật toán PBKDF2-HMAC-SHA256 với 16 bytes salt ngẫu nhiên và 100,000 vòng lặp. Khi xác thực, hệ thống dùng hàm hmac.compare_digest để so sánh constant-time nhằm chống tấn công dò thời gian."),
         
        ("Câu 12: Việc upload video lên Cloudinary có làm đứng (freeze) luồng camera đang nhận diện không?",
         "Tuyệt đối không, vì toàn bộ tác vụ ghi file video bằng cv2.VideoWriter và gửi HTTP request lên Cloudinary đều được bọc trong một luồng daemon độc lập (threading.Thread(target=self._save_event_media, daemon=True)). Luồng chính xử lý AI vẫn chạy mượt mà ở tốc độ 45–60 FPS."),
         
        ("Câu 13: Làm thế nào hệ thống phân biệt được trẻ em và người già khi té ngã?",
         "Hệ thống không đoán mò độ tuổi qua camera (vì rất dễ sai lệch do góc máy và quần áo), mà cho phép người vận hành chọn hồ sơ (Profile) trong cấu hình: elderly, child, pregnant, disabled. Profile người già sẽ tự động nhân hệ số nhạy cảm 0.85, giảm ngưỡng góc và tốc độ rơi để phát hiện cả những cú ngã chậm do trượt chân."),
         
        ("Câu 14: Tại sao server lại có cơ chế Watchdog?",
         "Trong môi trường giám sát y tế 24/7, camera có thể gặp sự cố phần cứng, tràn bộ đệm hệ điều hành hoặc lỗi driver. Watchdog chạy định kỳ mỗi 15 giây kiểm tra trạng thái pipeline.is_running(). Nếu phát hiện luồng AI bị dừng ngoài ý muốn, Watchdog sẽ tự động kích hoạt hồi sinh hệ thống ngay lập tức."),
         
        ("Câu 15: Dự án đã được kiểm thử như thế nào để chứng minh độ tin cậy?",
         "Hệ thống đã xây dựng bộ kiểm thử tự động toàn diện gồm 20 test cases chạy trên nền tảng Pytest, bao phủ: kịch bản ngã thật vs nằm ngủ, cúi nhặt đồ, ngồi bệt, hiệu năng non-blocking, giới hạn RAM buffer, tự phục hồi camera và xác thực mật khẩu. Kết quả kiểm thử đạt 100% Passed.")
    ]

    for q, a in qa_list:
        doc.add_paragraph(q, bold_prefix="❓", justify=False)
        doc.add_paragraph(a, bold_prefix="👉 Trả lời:", justify=True)

    path_docx = "docs/GIAI_THICH_VA_HOC_TAP_WEB_BACKEND_AI.docx"
    doc.save(path_docx)
    return path_docx


if __name__ == "__main__":
    build_web_backend_ai_doc()
