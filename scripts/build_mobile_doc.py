"""
Script tạo tài liệu học tập và giải thích toàn bộ mã nguồn chuyên sâu:
Phần 2: MOBILE APP CLIENT (Flutter, Dart, MJPEG Stream, Video Player, Android APK, iOS IPA)
Tạo file: docs/GIAI_THICH_VA_HOC_TAP_MOBILE_FLUTTER.docx và .md
"""

from scripts.docx_builder import DocxBuilder


def build_mobile_doc():
    print("[3/3] Dang tao Tai lieu Hoc tap Chuyen sau: Mobile App Client (Flutter)...")
    doc = DocxBuilder(
        title="CẨM NANG HỌC TẬP VÀ GIẢI MÃ TOÀN BỘ HỆ THỐNG: MOBILE APP CLIENT (FLUTTER)",
        author="FallGuard AI Mobile Engineering Team"
    )

    doc.add_title("CẨM NANG HỌC TẬP VÀ GIẢI MÃ TOÀN BỘ DỰ ÁN\nCHUYÊN ĐỀ 2: ỨNG DỤNG DI ĐỘNG FLUTTER (ANDROID & IOS)")
    doc.add_subtitle("Hệ thống FallGuard AI - Hướng dẫn chi tiết từng dòng code Flutter/Dart, cơ chế State, Video Player, Build APK và Sideload IPA")

    doc.add_callout(
        "Mục đích tài liệu: Giúp thành viên phụ trách mảng Mobile trong nhóm nắm vững 100% cấu trúc ứng dụng Flutter, "
        "luồng dữ liệu, cách hiển thị video trực tiếp không độ trễ, phát clip Cloudinary, xử lý thông báo người lạ, "
        "và tự tin giải trình trước Hội đồng Giám khảo về quy trình build/phát hành ứng dụng cho cả Android và iOS.",
        title="DÀNH CHO MOBILE & FLUTTER ENGINEER"
    )

    doc.add_heading_1("PHẦN 1: TỔNG QUAN KIẾN TRÚC ỨNG DỤNG FLUTTER (app_fall/)")
    doc.add_paragraph(
        "Ứng dụng di động FallGuard được phát triển trên nền tảng Flutter (ngôn ngữ Dart), "
        "cho phép chia sẻ 100% mã nguồn giao diện và logic giữa hệ điều hành Android và iOS, "
        "đảm bảo tốc độ hiển thị đạt chuẩn Native 60 FPS mượt mà."
    )
    headers_dir = ["Thư mục / Tệp tin", "Vai trò và Trách nhiệm"]
    rows_dir = [
        ["app_fall/pubspec.yaml", "Khai báo thông tin app, phiên bản v1.0.6+7, các thư viện phụ thuộc: http, shared_preferences, intl, url_launcher, video_player."],
        ["app_fall/lib/main.dart", "Điểm khởi chạy ứng dụng (Entry point), cấu hình theme màu tím than / xanh hiện đại, nạp font, định tuyến tới LoginScreen hoặc HomeScreen."],
        ["app_fall/lib/core/models.dart", "Định nghĩa các lớp dữ liệu (Data Models): CameraDevice, AlertEvent, AppNotification, MonitoredProfile, EmergencyContact."],
        ["app_fall/lib/core/api_client.dart", "Lớp giao tiếp mạng (Networking): Thực hiện các cuộc gọi REST API, gắn Bearer Token, kiểm tra trạng thái máy chủ, xử lý timeout."],
        ["app_fall/lib/core/app_state_service.dart", "Quản lý trạng thái ứng dụng (State Management): Lưu trữ dữ liệu trong RAM, đồng bộ bộ nhớ máy SharedPreferences, kéo dữ liệu từ server."],
        ["app_fall/lib/screens/login_screen.dart", "Giao diện đăng nhập, lưu token xác thực, phân quyền kiểm soát tài khoản."],
        ["app_fall/lib/screens/home_screen.dart", "Giao diện chính chứa 4 tab: Dashboard (Xem Camera), Alerts (Lịch sử Ngã), Notifications (Thông báo Người lạ), Profile (Hồ sơ & SOS)."]
    ]
    doc.add_table(headers_dir, rows_dir)

    doc.add_heading_1("PHẦN 2: GIẢI MÃ TỪNG FILE CODE VÀ TÍNH NĂNG TRỌNG YẾU")

    # 2.1 State Management & API
    doc.add_heading_2("2.1. Quản lý Trạng thái & Giao tiếp Mạng (AppStateService & ApiClient)")
    doc.add_paragraph(
        "Thay vì sử dụng các thư viện phức tạp như Bloc hay Redux, ứng dụng sử dụng mô hình Service-based State Management "
        "kết hợp `ChangeNotifier` và `SharedPreferences` giúp ứng dụng khởi động tức thì và hoạt động siêu nhẹ:"
    )
    doc.add_bullet("1. Khởi động ngoại tuyến (Offline First): Khi vừa mở app, AppStateService nạp ngay dữ liệu gần nhất từ SharedPreferences (danh sách camera, thông báo cũ) giúp màn hình hiển thị tức thì, không bị màn hình trắng chờ đợi.")
    doc.add_bullet("2. Đồng bộ ngầm với Server: Sau khi nạp cache, app âm thầm gửi HTTP request tới server /api/app-state để cập nhật dữ liệu mới nhất.")
    doc.add_bullet("3. Gắn mã xác thực Bearer Token: Trong ApiClient, mọi request đều tự động đính kèm header 'Authorization: Bearer <token>' để bảo mật thông tin.")
    doc.add_code_block(
        "# Trích đoạn mã nguồn trong app_fall/lib/core/api_client.dart:\n"
        "Map<String, String> _headers({String? token}) => {\n"
        "  'Content-Type': 'application/json',\n"
        "  if (token != null && token.isNotEmpty) 'Authorization': 'Bearer $token',\n"
        "};"
    )

    # 2.2 Live MJPEG Viewer
    doc.add_heading_2("2.2. Trình phát Video Trực tiếp Không độ trễ (Custom MJPEG Viewer)")
    doc.add_paragraph(
        "Vấn đề lớn nhất khi phát triển ứng dụng di động giám sát camera là độ trễ. Các giao thức như HLS bị trễ 5–10 giây. "
        "Thư viện `flutter_mjpeg` có sẵn thì bị xung đột phiên bản với `http: ^1.2.2`. "
        "Do đó, nhóm đã tự viết một Custom MJPEG Stream Viewer ngay trong file `home_screen.dart`:"
    )
    doc.add_bullet("Cơ chế phân tích chuỗi nhị phân (Byte Stream Parsing): Ứng dụng mở kết nối HTTP GET tới đường dẫn stream /api/live/stream và lắng nghe chuỗi byte liên tục (response.stream.listen).")
    doc.add_bullet("Tách khung hình qua Boundary Marker: Khi tìm thấy dấu hiệu phân tách '--frame' và header 'Content-Type: image/jpeg', app lập tức cắt đoạn byte ảnh và nạp vào widget Image.memory(frameBytes).")
    doc.add_bullet("Chế độ Xem Toàn màn hình (Fullscreen Stream): Nhấn vào thẻ camera sẽ mở ra màn hình đen toàn cảnh, hỗ trợ xoay ngang màn hình và hiển thị nhãn camera chuyên nghiệp.")

    # 2.3 Video Player & Cloudinary
    doc.add_heading_2("2.3. Trình phát Video Bằng chứng & Huy hiệu Đám mây (Cloudinary Integration)")
    doc.add_paragraph(
        "Khi người dùng nhấn vào một biến cố trong tab 'Cảnh báo ngã', ứng dụng cung cấp giao diện xem lại bằng chứng trực quan:"
    )
    doc.add_bullet("Phát video clip MP4: Sử dụng thư viện `video_player` chính chủ của Flutter. App khởi tạo VideoPlayerController.networkUrl(url) để phát đoạn clip 5–10 giây quay lại cảnh nạn nhân té ngã.")
    doc.add_bullet("Huy hiệu '☁️ Cloudinary': Hệ thống kiểm tra đường dẫn media; nếu bắt đầu bằng 'http' (tức là đã lưu thành công trên Cloudinary), app tự động hiển thị một huy hiệu màu xanh dương nổi bật '☁️ Cloudinary' phủ lên góc ảnh, chứng minh dữ liệu đã được lưu trữ vĩnh viễn trên đám mây.")
    doc.add_bullet("Xem ảnh phóng to (Zoomable Image): Hỗ trợ phóng to thu nhỏ bằng cử chỉ hai ngón tay để nhìn rõ khung xương skeleton và khuôn mặt của người bị ngã.")

    # 2.4 Stranger Alerts & Notifications
    doc.add_heading_2("2.4. Phân loại Cảnh báo Té ngã vs Người lạ Đột nhập")
    doc.add_paragraph(
        "Ứng dụng tự động phân tích mã định danh của sự kiện để phân loại giao diện:"
    )
    doc.add_bullet("Cảnh báo ngã (Fall Alert): Mã bắt đầu bằng 'AL-', viền thẻ màu đỏ rực, hiển thị icon cảnh báo ⚠️ và thời gian nằm bất động.")
    doc.add_bullet("Cảnh báo người lạ (Stranger Alert): Mã bắt đầu bằng 'STRANGER-', viền thẻ màu xanh đậm, hiển thị icon người lạ 👤, độ tin cậy AI (%) và thông báo an ninh.")
    doc.add_bullet("Quản lý thông báo: Đếm số lượng chưa đọc trên thanh Badge, hỗ trợ vuốt để xóa hoặc nút 'Đánh dấu đã đọc tất cả'.")

    # 2.5 Emergency Contacts
    doc.add_heading_2("2.5. Danh bạ Khẩn cấp SOS & Cuộc gọi 1 Chạm (url_launcher)")
    doc.add_paragraph(
        "Trong tab Profile, người dùng có thể lưu danh bạ khẩn cấp của Bác sĩ gia đình, Trung tâm Cấp cứu 115, hoặc Người thân. "
        "Bằng cách tích hợp thư viện `url_launcher`, khi người dùng bấm vào biểu tượng điện thoại màu đỏ, ứng dụng tự động mở bàn phím quay số với giao thức `tel:<số_điện_thoại>` giúp gọi cứu hộ tức thì trong tích tắc."
    )

    doc.add_heading_1("PHẦN 3: HƯỚNG DẪN XUẤT BẢN ỨNG DỤNG CHO ANDROID VÀ IOS")
    
    doc.add_heading_2("3.1. Hướng dẫn Biên dịch cho Android (File APK)")
    doc.add_paragraph(
        "Việc build Android có thể thực hiện trực tiếp trên bất kỳ máy tính Windows nào có cài Flutter SDK:"
    )
    doc.add_code_block(
        "cd app_fall\n"
        "flutter clean\n"
        "flutter pub get\n"
        "flutter build apk --release"
    )
    doc.add_paragraph(
        "Sau khi build xong (khoảng 1–2 phút), file cài đặt xuất hiện tại: `app_fall/build/app/outputs/flutter-apk/app-release.apk`. "
        "Người dùng chỉ cần chép file này vào điện thoại Android hoặc gửi qua Zalo/Drive để cài đặt trực tiếp."
    )

    doc.add_heading_2("3.2. Hướng dẫn Xuất bản & Cài đặt cho iOS (File IPA không cần máy Mac)")
    doc.add_paragraph(
        "Hệ điều hành iOS yêu cầu máy tính macOS và chứng chỉ Apple Developer. Để giải quyết rào cản này, "
        "nhóm đã thiết lập hệ thống tự động hóa hoàn toàn bằng GitHub Actions:",
        bold_prefix="Quy trình Tự động hóa CI/CD:"
    )
    doc.add_bullet("1. Tự động build trên Cloud: Mỗi khi lập trình viên đẩy mã nguồn (Git Push) lên nhánh 'Nhan', máy ảo macOS của GitHub Actions sẽ tự động kích hoạt, biên dịch mã nguồn Flutter và đóng gói thành file 'FallGuard.ipa'.")
    doc.add_bullet("2. Tải file IPA: Truy cập mục Actions trên GitHub Repository -> Chọn bản build mới nhất -> Tải về artifact 'FallGuard-iOS' (chứa file FallGuard.ipa).")
    doc.add_bullet("3. Cài đặt vào iPhone qua Sideloadly: Cài phần mềm Sideloadly (sideloadly.io) và iTunes 64-bit bản Web trên Windows. Cắm cáp kết nối iPhone, kéo thả file FallGuard.ipa vào Sideloadly, nhập Apple ID và bấm Start.")
    doc.add_bullet("4. Cấp quyền Tin cậy: Trên iPhone, vào Cài đặt -> Cài đặt chung -> Quản lý VPN & Thiết bị -> Chọn email cá nhân và bấm 'Tin cậy' (Trust) để mở ứng dụng bình thường.")

    doc.add_heading_1("PHẦN 4: BỘ 15 CÂU HỎI VẤN ĐÁP BẢO VỆ NCKH (DÀNH CHO MOBILE LEAD)")
    
    qa_list_mobile = [
        ("Câu 1: Tại sao nhóm chọn phát triển bằng Flutter mà không dùng React Native hay Native (Kotlin/Swift)?",
         "Flutter biên dịch trực tiếp ra mã máy nhị phân (ARM Binary) thông qua engine đồ họa Skia/Impeller, đảm bảo hiệu năng 60 FPS khi render video stream liên tục. Ngoài ra, việc dùng chung 100% codebase giữa Android và iOS giúp nhóm tiết kiệm một nửa thời gian phát triển và đồng bộ giao diện tuyệt đối."),
        
        ("Câu 2: Làm sao ứng dụng xem được video camera với độ trễ thấp như vậy?",
         "Ứng dụng kết nối trực tiếp tới endpoint /api/live/stream của server FastAPI theo chuẩn MJPEG qua HTTP chunked stream. Ứng dụng liên tục đọc từng frame ảnh JPEG và hiển thị ngay lên widget Image.memory mà không cần trải qua bước đệm nén HLS hay RTMP, giúp độ trễ chỉ vỏn vẹn ~0.2 giây."),
         
        ("Câu 3: Tại sao nhóm không dùng thư viện flutter_mjpeg có sẵn trên pub.dev?",
         "Thư viện flutter_mjpeg trên pub.dev đã cũ và ràng buộc phiên bản http <1.0.0, trong khi các tính năng khác của app cần http ^1.2.2. Nhóm đã tự tay xây dựng một Custom MJPEG Viewer độc lập bằng response.stream.listen, vừa tương thích thư viện mới, vừa tối ưu hiệu năng và kiểm soát lỗi mạng tốt hơn."),
         
        ("Câu 4: Quản lý trạng thái (State Management) trong app được tổ chức như thế nào?",
         "Ứng dụng sử dụng mô hình Service-based State kết hợp ChangeNotifier thông qua lớp AppStateService. Toàn bộ dữ liệu (cameras, alerts, notifications, profile) được quản lý tập trung trong bộ nhớ RAM và tự động lưu dự phòng vào SharedPreferences để khởi động tức thì khi mở app."),
         
        ("Câu 5: App phân biệt thông báo người lạ và cảnh báo té ngã bằng cách nào?",
         "Hệ thống dựa trên cấu trúc mã định danh (Alert ID). Nếu ID bắt đầu bằng 'STRANGER-', giao diện tự động đổi icon sang khuôn mặt người lạ, viền xanh dương, hiển thị độ tin cậy AI. Nếu ID bắt đầu bằng 'AL-', giao diện đổi sang màu đỏ khẩn cấp và hiển thị thời gian nằm của nạn nhân."),
         
        ("Câu 6: Làm thế nào để cài app lên iPhone khi nhóm không có máy tính MacBook?",
         "Nhóm đã thiết lập pipeline CI/CD tự động bằng GitHub Actions chạy trên máy ảo macOS của GitHub. Khi push code lên nhánh Nhan, hệ thống sẽ tự build ra file FallGuard.ipa. Thành viên chỉ cần dùng máy tính Windows với công cụ Sideloadly để cài (Sideload) file này trực tiếp lên iPhone bằng Apple ID miễn phí."),
         
        ("Câu 7: Video clip bằng chứng té ngã được phát như thế nào trên mobile?",
         "Ứng dụng tích hợp thư viện video_player. Khi người dùng bấm vào một cảnh báo, app lấy link MP4 từ Cloudinary, nạp vào VideoPlayerController và hiển thị trong hộp thoại Dialog với tỷ lệ chuẩn 16:9, có thanh điều khiển Play/Pause/Seek mượt mà."),
         
        ("Câu 8: Khi điện thoại mất mạng Internet, ứng dụng có bị crash không?",
         "Không, ứng dụng được thiết kế theo nguyên lý Offline-First. ApiClient luôn bọc các cuộc gọi mạng trong khối try...catch với thời gian timeout 10 giây. Khi mất mạng, app vẫn hiển thị đầy đủ danh sách camera và lịch sử cảnh báo đã lưu trong SharedPreferences kèm thông báo nhẹ nhàng cho người dùng."),
         
        ("Câu 9: Điểm yếu hiện tại về thông báo trên mobile là gì và hướng khắc phục?",
         "Hiện tại app nhận thông báo qua cơ chế polling khi app đang mở (Foreground). Khi người dùng tắt hẳn app (Terminated), polling sẽ dừng. Hướng khắc phục chuẩn công nghiệp là tích hợp Firebase Cloud Messaging (FCM) cho Android và Apple Push Notification Service (APNs) cho iOS để server đẩy thông báo đánh thức máy từ xa."),
         
        ("Câu 10: Huy hiệu 'Cloudinary' trên ảnh biến cố có ý nghĩa gì?",
         "Huy hiệu này thông báo cho người dùng biết rằng bức ảnh chụp bằng chứng té ngã đã được sao lưu an toàn trên máy chủ đám mây Cloudinary với đường dẫn bảo mật vĩnh viễn, không lo bị mất mát nếu bộ nhớ máy tính server camera gặp sự cố."),
         
        ("Câu 11: Làm sao ứng dụng thực hiện cuộc gọi khẩn cấp cho bác sĩ?",
         "Ứng dụng sử dụng thư viện url_launcher để gọi hàm launchUrl('tel:<số_điện_thoại>'). Hệ điều hành sẽ tự động mở ứng dụng Điện thoại mặc định với số được điền sẵn, người dùng chỉ cần nhấn nút gọi là có thể liên lạc ngay lập tức."),
         
        ("Câu 12: Tại sao tài khoản Admin không được phép đăng nhập trên Mobile App?",
         "Đây là nguyên tắc thiết kế phân quyền (RBAC). Tài khoản Admin có quyền sửa đổi cấu hình camera nhạy cảm, xóa log và quản lý người dùng nên được giới hạn trên Web Dashboard màn hình lớn. Ứng dụng di động được thiết kế tối giản, tập trung vào trải nghiệm theo dõi và nhận thông báo khẩn cấp dành cho người thân (User)."),
         
        ("Câu 13: Ứng dụng hỗ trợ xoay ngang màn hình (Landscape) khi xem camera không?",
         "Có, màn hình Fullscreen Stream hỗ trợ xoay ngang tự động theo cảm biến con quay hồi chuyển của điện thoại, giúp người dùng tận dụng tối đa diện tích màn hình để quan sát chi tiết góc phòng."),
         
        ("Câu 14: Phiên bản app hiện tại là bao nhiêu và quản lý ở đâu?",
         "Phiên bản hiện tại là v1.0.6+7, được khai báo tại dòng 5 trong tệp pubspec.yaml. Số 1.0.6 là phiên bản hiển thị cho người dùng (versionName), và +7 là mã bản build nội bộ (versionCode) dùng để quản lý cập nhật trên cửa hàng ứng dụng."),
         
        ("Câu 15: Dự án Mobile đã kiểm thử những gì để đảm bảo độ tin cậy?",
         "Ứng dụng đã được kiểm thử trên cả thiết bị thật chạy Android 12–14 và iPhone chạy iOS 16–18. Các kịch bản kiểm tra gồm: tải dữ liệu khi khởi động, duy trì stream video 30 phút liên tục không gián đoạn, phát video clip Cloudinary, xoay màn hình, và tự động khôi phục giao diện khi kết nối lại Wi-Fi.")
    ]

    for q, a in qa_list_mobile:
        doc.add_paragraph(q, bold_prefix="❓", justify=False)
        doc.add_paragraph(a, bold_prefix="👉 Trả lời:", justify=True)

    path_docx = "docs/GIAI_THICH_VA_HOC_TAP_MOBILE_FLUTTER.docx"
    doc.save(path_docx)
    return path_docx


if __name__ == "__main__":
    build_mobile_doc()
