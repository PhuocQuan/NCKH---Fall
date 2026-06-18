import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../services/socket_service.dart';
import '../widgets/mjpeg_view.dart';
import 'Camera_detail_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentTab = 0;
  final socketService = SocketService();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        automaticallyImplyLeading: false,
        title: const Text(
          'Cameras',
          style: TextStyle(
            color: AppColors.textDark,
            fontWeight: FontWeight.bold,
            fontSize: 22,
          ),
        ),
      ),
      body: SafeArea(
        child: StreamBuilder<Map<String, dynamic>>(
          stream: socketService.stream,
          builder: (context, snapshot) {
            if (!snapshot.hasData) {
              return const Center(
                child: CircularProgressIndicator(),
              );
            }

            final data = snapshot.data!;
            final isFall = data["is_fall"] ?? false;

            // ====== THÊM CAMERA: chỉnh ở đây ======
            // WHY dùng GridView thay vì 1 _CameraCard đơn như bản cũ:
            // UI vẫn theo layout ảnh mock (lưới 2 cột), nhưng hiện tại backend
            // CHỈ CÓ 1 CAMERA THẬT (1 VideoSource trong FallDetectionApp).
            // Để không giả vờ 3 camera kia "đang sống" trong khi chúng không
            // có data thật, t tách rõ:
            //   - CAM-01: dùng _CameraCard thật (video MJPEG + status từ socket)
            //   - CAM-02..04: dùng _PlaceholderCameraCard (không gọi MjpegView,
            //     không tốn 1 connection MJPEG vô ích, hiển thị rõ "chưa kết nối"
            //     để không đánh lừa người dùng là đang giám sát)
            //
            // Khi nào có thêm camera thật (thêm VideoSource/endpoint /video2,
            // /video3... ở backend), chỉ cần thay từng _PlaceholderCameraCard
            // tương ứng bằng _CameraCard thật với url/label riêng — không cần
            // sửa lại cấu trúc GridView.
            return Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: 16,
                vertical: 8,
              ),
              child: ClipRRect(
                // WHY bo góc ở đây (toàn bộ lưới), không phải từng card:
                // khi spacing gần 0 và từng card không còn shadow để tách
                // biệt, bo góc riêng từng ô sẽ lộ "góc trắng" hở ra ở giữa
                // các ô liền kề, nhìn không sạch. Bo góc 1 lần ở khung ngoài
                // cùng cho cảm giác 1 lưới camera liền mạch, đúng kiểu
                // "sát nhau" mày muốn.
                borderRadius: BorderRadius.circular(16),
                child: GridView(
                  // WHY spacing 3px thay vì 12px như bản cũ:
                  // mày muốn các camera "sát nhau" — giữ khoảng cách rất nhỏ
                  // để phân biệt được ranh giới từng ô (không dính hẳn thành
                  // 1 khối, dễ nhận biết camera nào với camera nào) nhưng
                  // không còn gap rộng + shadow như layout "card rời" cũ.
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 2,
                    crossAxisSpacing: 3,
                    mainAxisSpacing: 3,
                    childAspectRatio: 0.78,
                  ),
                  children: [
                    // CAM-01: camera thật duy nhất hiện có
                    _CameraCard(
                      label: 'CAM-01 · Bedroom · Room 101',
                      videoUrl: 'http://127.0.0.1:8000/video',
                      statusText: isFall ? 'Fall Detected' : 'Normal',
                      statusColor: isFall ? Colors.red : Colors.green,
                      // WHY truyền callback onTap từ ngoài vào, không tự
                      // Navigator.push trong _CameraCard:
                      // _CameraCard là widget hiển thị thuần (dumb widget),
                      // không nên biết về navigation logic hay cách tạo
                      // CameraDetailScreen. HomeScreen (nơi nắm socketService)
                      // mới là nơi có đủ thông tin để build route — giữ
                      // _CameraCard tái dùng được cho mục đích khác sau này
                      // (ví dụ nhúng vào 1 dashboard không cần tap-to-detail).
                      onTap: () => _openCameraDetail(
                        label: 'CAM-01 · Bedroom · Room 101',
                        videoUrl: 'http://127.0.0.1:8000/video',
                      ),
                    ),
                    // CAM-02, 03, 04: placeholder, chờ gắn logic/camera thật sau
                    const _PlaceholderCameraCard(
                      label: 'CAM-02 · Bedroom · Room 102',
                    ),
                    const _PlaceholderCameraCard(
                      label: 'CAM-03 · Bedroom · Room 103',
                    ),
                    const _PlaceholderCameraCard(
                      label: 'CAM-04 · Bedroom · Room 104',
                    ),
                  ],
                ),
              ),
            );
            // ====== HẾT PHẦN THÊM CAMERA ======
          },
        ),
      ),
      bottomNavigationBar: _buildBottomNav(),
    );
  }

  // WHY tách thành method riêng thay vì viết inline trong onTap:
  // sau này CAM-02/03/04 có data thật, mày chỉ cần gọi lại đúng method
  // này với label/videoUrl khác, không phải copy-paste logic Navigator.push.
  void _openCameraDetail({
    required String label,
    required String videoUrl,
  }) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => CameraDetailScreen(
          label: label,
          videoUrl: videoUrl,
          // WHY truyền socketService.stream (instance hiện tại), không
          // socketService.channel.stream thô: .stream đã là broadcast
          // stream (xem socket_service.dart — .asBroadcastStream()), nghĩa
          // là Home và Detail có thể cùng listen() trên CÙNG 1 stream object
          // mà không tranh nhau dữ liệu hay làm hỏng StreamBuilder của Home.
          // Nếu dùng stream thường (single-subscription), Detail listen()
          // vào sẽ làm StreamBuilder ở Home mất khả năng nhận data (1 stream
          // chỉ cho phép 1 listener active).
          socketStream: socketService.stream,
        ),
      ),
    );
  }

  Widget _buildBottomNav() {
    return BottomNavigationBar(
      currentIndex: _currentTab,
      onTap: (index) => setState(() => _currentTab = index),
      type: BottomNavigationBarType.fixed,
      selectedItemColor: AppColors.primary,
      unselectedItemColor: AppColors.textGrey,
      showUnselectedLabels: true,
      items: const [
        BottomNavigationBarItem(
          icon: Icon(Icons.home_outlined),
          label: 'Home',
        ),
        BottomNavigationBarItem(
          icon: Icon(Icons.videocam_outlined),
          label: 'Cameras',
        ),
        BottomNavigationBarItem(
          icon: Icon(Icons.notifications_outlined),
          label: 'Alerts',
        ),
        BottomNavigationBarItem(
          icon: Icon(Icons.person_outline),
          label: 'Profile',
        ),
      ],
    );
  }
}

class _CameraCard extends StatelessWidget {
  final String label;
  final String videoUrl;
  final String statusText;
  final Color statusColor;
  final VoidCallback onTap;

  const _CameraCard({
    required this.label,
    required this.videoUrl,
    required this.statusText,
    required this.statusColor,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    // WHY bọc cả Container bằng InkWell (không phải GestureDetector):
    // InkWell cho ripple effect khi tap — feedback hình ảnh ngay lập tức
    // báo cho user biết "tap đã được nhận", quan trọng với app giám sát
    // y tế vì user (caregiver) cần chắc chắn họ vừa mở đúng camera, không
    // tap nhầm. GestureDetector không có visual feedback này.
    return InkWell(
      onTap: onTap,
      child: Container(
        // WHY bỏ borderRadius + boxShadow ở đây:
        // theo yêu cầu "sát nhau, bỏ shadow cho đỡ rối" — bo góc + shadow từng
        // card tạo cảm giác 4 card rời rạc, không hợp với spacing 3px. Bo góc
        // tổng thể đã chuyển ra ClipRRect bọc ngoài GridView (xem build() của
        // _HomeScreenState).
        color: Colors.white,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildVideoArea(),
            _buildFooterLabel(),
          ],
        ),
      ),
    );
  }

  Widget _buildVideoArea() {
    return AspectRatio(
      aspectRatio: 16 / 9,
      child: Stack(
        children: [
          // WHY bỏ ClipRRect bo góc top ở đây:
          // cùng lý do trên — card không còn bo góc riêng, video area chiếm
          // full góc vuông, ăn liền với card bên cạnh.
          MjpegView(
            url: videoUrl,
          ),

          Positioned(
            top: 12,
            left: 12,
            child: _Badge(
              text: 'LIVE',
              backgroundColor: Colors.red,
              textColor: Colors.white,
              dotColor: Colors.white,
            ),
          ),

          Positioned(
            top: 12,
            right: 12,
            child: _Badge(
              text: statusText,
              backgroundColor: Colors.black54,
              textColor: Colors.white,
              dotColor: statusColor,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFooterLabel() {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          // WHY Expanded đặt ở ĐÂY (Row cha), không phải trong Row con bên dưới:
          // Row cha có spaceBetween, được Padding/Container bên ngoài ép width
          // xác định (bounded) -> Expanded ở cấp này hợp lệ.
          // Bản lỗi trước đặt Expanded lồng trong Row con (chứa dot + label),
          // Row con đó không có gì ép width -> khi GridView co card nhỏ lại
          // (2 cột), trong 1 số layout pass nó nhận width constraint
          // unbounded -> "RenderFlex children have non-zero flex but
          // incoming width constraints are unbounded" + theo đó kéo theo
          // "Cannot hit test a render box with no size" vì render object
          // không có size hợp lệ để hit-test.
          Expanded(
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: const BoxDecoration(
                    color: Colors.green,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    label,
                    overflow: TextOverflow.ellipsis,
                    maxLines: 1,
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textDark,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 4),
          const Icon(
            Icons.chevron_right,
            color: AppColors.textGrey,
            size: 18,
          ),
        ],
      ),
    );
  }
}

// THÊM CAMERA: card placeholder cho camera chưa có backend/logic thật.
// WHY tách riêng, không tái dùng _CameraCard với url rỗng:
// _CameraCard luôn gọi MjpegView -> luôn mở 1 HtmlElementView + register
// platform view, kể cả khi url không trỏ tới server thật (sẽ chỉ hiện ảnh
// broken/đen, tốn tài nguyên vô ích). _PlaceholderCameraCard không đụng tới
// MjpegView/platform view nào cả, chỉ là 1 Container tĩnh — an toàn, rẻ, và
// nói rõ cho người dùng biết camera này CHƯA kết nối, tránh hiểu lầm là đang
// giám sát thật.
//
// WHY không có onTap: chưa có camera/route thật để mở -> tap vào không có
// gì xảy ra (không đăng ký InkWell) thay vì navigate tới 1 Detail screen
// với video URL rỗng/lỗi, gây trải nghiệm xấu hơn so với "không phản hồi".
//
// Khi gắn camera thật vào ô này (ví dụ thêm endpoint /video2 ở backend),
// thay lời gọi _PlaceholderCameraCard(label: ...) bằng _CameraCard(label:,
// videoUrl:, statusText:, statusColor:, onTap:) như CAM-01 phía trên.
class _PlaceholderCameraCard extends StatelessWidget {
  final String label;

  const _PlaceholderCameraCard({
    required this.label,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      // Đồng bộ với _CameraCard: bỏ shadow + bo góc riêng, card sát nhau
      // qua spacing 3px của GridView, bo góc tổng thể nằm ở ClipRRect ngoài.
      color: Colors.white,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AspectRatio(
            aspectRatio: 16 / 9,
            child: Container(
              color: const Color(0xFFE8EAF0),
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.videocam_off_outlined,
                      color: AppColors.textGrey,
                      size: 28,
                    ),
                    const SizedBox(height: 6),
                    Text(
                      'Chưa kết nối',
                      style: TextStyle(
                        color: AppColors.textGrey,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                // Cùng fix như _CameraCard: Expanded đặt ở Row cha (bounded),
                // không lồng trong Row con (unbounded) — tránh
                // "RenderFlex children have non-zero flex but incoming width
                // constraints are unbounded".
                Expanded(
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 8,
                        height: 8,
                        decoration: const BoxDecoration(
                          color: AppColors.textGrey,
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          label,
                          overflow: TextOverflow.ellipsis,
                          maxLines: 1,
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: AppColors.textGrey,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 4),
                const Icon(
                  Icons.chevron_right,
                  color: AppColors.textGrey,
                  size: 18,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  final String text;
  final Color backgroundColor;
  final Color textColor;
  final Color dotColor;

  const _Badge({
    required this.text,
    required this.backgroundColor,
    required this.textColor,
    required this.dotColor,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: 8,
        vertical: 4,
      ),
      decoration: BoxDecoration(
        color: backgroundColor,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(
              color: dotColor,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 4),
          Text(
            text,
            style: TextStyle(
              color: textColor,
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}