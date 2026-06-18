import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../theme/app_colors.dart';
import '../widgets/mjpeg_view.dart';

class CameraDetailScreen extends StatefulWidget {
  final String label;
  final String videoUrl;
  // WHY nhận thẳng Stream từ ngoài vào, không tự tạo SocketService mới:
  // SocketService đang sống ở HomeScreen.State (1 connection WebSocket
  // duy nhất cho toàn app). Nếu Detail tự new SocketService() riêng, mày
  // sẽ có 2 connection cùng bắn request lên server, tốn tài nguyên server
  // vô ích và 2 stream có thể lệch nhau vài trăm ms -> Home hiện "Normal"
  // nhưng Detail hiện "Fall Detected" cùng lúc, nhìn vào không tin được
  // app. Truyền thẳng instance stream xuống đảm bảo single source of truth.
  final Stream<Map<String, dynamic>> socketStream;

  const CameraDetailScreen({
    super.key,
    required this.label,
    required this.videoUrl,
    required this.socketStream,
  });

  @override
  State<CameraDetailScreen> createState() => _CameraDetailScreenState();
}

class _CameraDetailScreenState extends State<CameraDetailScreen> {
  bool _isFall = false;
  String _lastUpdated = '';
  StreamSubscription<Map<String, dynamic>>? _subscription;

  @override
  void initState() {
    super.initState();

    // WHY cho phép landscape ở ĐÂY (initState của Detail), không phải global
    // ở main.dart: setPreferredOrientations là side-effect toàn app, set 1
    // lần là áp dụng cho MỌI screen đang sống, không tự giới hạn theo route.
    // Nếu set ở main.dart, Home cũng bị xoay theo -> vỡ GridView 2 cột.
    // Set ở đây, kèm restore ở dispose() bên dưới, đảm bảo CHỈ Detail mới
    // được landscape, Home luôn portrait-only.
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.portraitUp,
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);

    // Lắng nghe stream được truyền từ Home để cập nhật status real-time,
    // không tạo connection riêng (xem comment ở field socketStream).
    _subscription = widget.socketStream.listen((data) {
      if (!mounted) return;
      setState(() {
        _isFall = data['is_fall'] ?? false;
        _lastUpdated = DateTime.now().toIso8601String().substring(11, 19);
      });
    });
  }

  @override
  void dispose() {
    // WHY bắt buộc restore về portrait-only khi rời Detail:
    // đây là phần dễ bị quên nhất. Không restore -> user back về Home,
    // nếu họ đang cầm máy ngang sẵn (vì vừa xem video landscape), Home sẽ
    // bị render landscape theo, vỡ layout GridView đã build cho portrait.
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.portraitUp,
    ]);
    _subscription?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      // WHY dùng OrientationBuilder thay vì MediaQuery.orientation trực tiếp:
      // OrientationBuilder rebuild đúng phần con của nó mỗi khi orientation
      // đổi, tách biệt rõ ràng UI portrait vs landscape thành 2 method riêng
      // -> dễ đọc, dễ maintain hơn so với nhồi if/else dày đặc trong 1 build().
      body: OrientationBuilder(
        builder: (context, orientation) {
          return orientation == Orientation.landscape
              ? _buildLandscapeLayout()
              : _buildPortraitLayout();
        },
      ),
    );
  }

  // ===== PORTRAIT: video trên, info card dưới =====
  Widget _buildPortraitLayout() {
    return SafeArea(
      child: Column(
        children: [
          _buildAppBar(),
          AspectRatio(
            aspectRatio: 16 / 9,
            child: Stack(
              children: [
                MjpegView(url: widget.videoUrl),
                Positioned(
                  top: 12,
                  left: 12,
                  child: _buildLiveBadge(),
                ),
              ],
            ),
          ),
          Expanded(
            child: _buildInfoPanel(),
          ),
        ],
      ),
    );
  }

  // ===== LANDSCAPE: video full-screen, info/back đè overlay lên trên =====
  Widget _buildLandscapeLayout() {
    return Stack(
      children: [
        // WHY video chiếm Positioned.fill (full screen thật, không SafeArea):
        // mục tiêu landscape là xem video full-screen sát viền, SafeArea sẽ
        // chèn padding 2 bên (notch/status bar) làm video bị "thụt" vào,
        // mất cảm giác full-screen. Các control phía trên mới cần SafeArea
        // để không bị notch/camera che mất nút back.
        Positioned.fill(
          child: MjpegView(url: widget.videoUrl),
        ),

        // Overlay top: back button + status, đè lên video
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                _buildBackButton(),
                _buildLiveBadge(),
                _buildStatusBadge(),
              ],
            ),
          ),
        ),

        // Overlay bottom: label + timestamp, đè lên video
        Positioned(
          left: 0,
          right: 0,
          bottom: 0,
          child: SafeArea(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              // WHY gradient đen mờ dần lên trên thay vì màu đặc:
              // text trắng đè trực tiếp lên video (có thể là nền sáng) sẽ
              // khó đọc. Gradient cho chữ luôn đọc được mà không che hẳn
              // hình ảnh phía dưới như 1 thanh đen đặc.
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.bottomCenter,
                  end: Alignment.topCenter,
                  colors: [Colors.black54, Colors.transparent],
                ),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    widget.label,
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w600,
                      fontSize: 13,
                    ),
                  ),
                  if (_lastUpdated.isNotEmpty)
                    Text(
                      _lastUpdated,
                      style: const TextStyle(
                        color: Colors.white70,
                        fontSize: 12,
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildAppBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      child: Row(
        children: [
          _buildBackButton(),
          const SizedBox(width: 4),
          Expanded(
            child: Text(
              widget.label,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w600,
                fontSize: 16,
              ),
            ),
          ),
          _buildStatusBadge(),
        ],
      ),
    );
  }

  Widget _buildBackButton() {
    return IconButton(
      // WHY pop() thường, không Navigator.pushReplacement:
      // route này được push vào, back phải trả về đúng HomeScreen ở dưới
      // stack, giữ lại state của Home (scroll position, _currentTab...)
      // thay vì tạo lại Home từ đầu.
      onPressed: () => Navigator.of(context).pop(),
      icon: Container(
        padding: const EdgeInsets.all(6),
        decoration: BoxDecoration(
          color: Colors.black45,
          borderRadius: BorderRadius.circular(8),
        ),
        child: const Icon(Icons.arrow_back, color: Colors.white, size: 20),
      ),
    );
  }

  Widget _buildLiveBadge() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.red,
        borderRadius: BorderRadius.circular(6),
      ),
      child: const Text(
        'LIVE',
        style: TextStyle(
          color: Colors.white,
          fontSize: 11,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }

  Widget _buildStatusBadge() {
    final color = _isFall ? Colors.red : Colors.green;
    final text = _isFall ? 'Fall Detected' : 'Normal';

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.black45,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Text(
            text,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  // Info panel chỉ hiện ở Portrait (landscape đã có overlay riêng phía trên)
  Widget _buildInfoPanel() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: const BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            widget.label,
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: AppColors.textDark,
            ),
          ),
          const SizedBox(height: 16),
          _buildInfoRow(
            icon: Icons.warning_amber_rounded,
            label: 'Status',
            value: _isFall ? 'Fall Detected' : 'Normal',
            valueColor: _isFall ? Colors.red : Colors.green,
          ),
          const SizedBox(height: 12),
          _buildInfoRow(
            icon: Icons.access_time,
            label: 'Last updated',
            value: _lastUpdated.isEmpty ? '—' : _lastUpdated,
            valueColor: AppColors.textDark,
          ),
          const Spacer(),
          // Gợi nhẹ cho user biết có thể xoay ngang để xem full-screen,
          // không bắt buộc nhưng giúp họ discover feature.
          Center(
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: const [
                Icon(Icons.screen_rotation, size: 16, color: AppColors.textGrey),
                SizedBox(width: 6),
                Text(
                  'Xoay ngang để xem full-screen',
                  style: TextStyle(color: AppColors.textGrey, fontSize: 12),
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),
        ],
      ),
    );
  }

  Widget _buildInfoRow({
    required IconData icon,
    required String label,
    required String value,
    required Color valueColor,
  }) {
    return Row(
      children: [
        Icon(icon, size: 18, color: AppColors.textGrey),
        const SizedBox(width: 10),
        Text(
          label,
          style: const TextStyle(color: AppColors.textGrey, fontSize: 14),
        ),
        const Spacer(),
        Text(
          value,
          style: TextStyle(
            color: valueColor,
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}