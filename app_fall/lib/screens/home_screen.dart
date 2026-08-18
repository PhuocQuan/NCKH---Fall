// lib/screens/home_screen.dart
// Màn hình chính — Bottom Navigation + Drawer + 5 Tab views
// Thiết kế theo src/web/mobile/user.html + mobile_user.css

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';
import '../core/api_client.dart';
import '../core/auth_service.dart';
import '../core/app_state_service.dart';
import '../core/models.dart';
import '../widgets/status_pill.dart';
import '../widgets/mjpeg_view.dart';

// ─── Color tokens (matching web CSS variables) ────────────────────────────────
const kBlue = Color(0xFF4f46e5);
const kInk = Color(0xFF0f172a);
const kBg = Color(0xFFF1F5F9);
const kCard = Colors.white;
const kMuted = Color(0xFF64748b);
const kLine = Color(0xFFE2E8F0);
const kRed = Color(0xFFEF4444);
const kAmber = Color(0xFFF59E0B);
const kGreen = Color(0xFF10b981);
const kSidebarBg = Color(0xFF0f172a);

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _state = AppStateService();
  final _scaffoldKey = GlobalKey<ScaffoldState>();

  int _currentTab = 0; // 0=dashboard, 1=alerts, 2=notifications, 3=profile
  bool _isBackendOnline = false;
  bool _isViewingCamera = false;
  Timer? _statusTimer;



  @override
  void initState() {
    super.initState();
    _state.onStateChanged = () {
      if (mounted) setState(() {});
    };
    _initState();
  }

  Future<void> _initState() async {
    await _checkBackend();
    if (_isBackendOnline) await _state.syncFromBackend();
    _state.startAutoSync();
    _statusTimer = Timer.periodic(const Duration(seconds: 15), (_) async {
      final online = await AuthService().checkBackendOnline();
      if (mounted) setState(() => _isBackendOnline = online);
    });
    if (mounted) setState(() {});
  }

  Future<void> _checkBackend() async {
    final online = await AuthService().checkBackendOnline();
    if (mounted) setState(() => _isBackendOnline = online);
    _state.isBackendOnline = online;
  }

  @override
  void dispose() {
    _statusTimer?.cancel();
    _state.stopAutoSync();
    _state.onStateChanged = null;
    super.dispose();
  }

  Future<void> _performLogout() async {
    if (_isBackendOnline) await ApiClient().logout();
    await AuthService().clearSession();
    _state.stopAutoSync();
    if (!mounted) return;
    Navigator.of(context).pushReplacementNamed('/login');
  }

  // ─── SCAFFOLD ──────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.dark.copyWith(statusBarColor: Colors.transparent),
      child: Scaffold(
        key: _scaffoldKey,
        backgroundColor: kBg,
        drawer: _buildDrawer(),
        body: Column(
          children: [
            _buildHeader(),
            Expanded(child: _buildBody()),
          ],
        ),
        bottomNavigationBar: _buildBottomNav(),
      ),
    );
  }

  // ─── HEADER ────────────────────────────────────────────────────────────────

  Widget _buildHeader() {
    final user = _state.currentUser;
    final cams = _state.getVisibleCameras();
    
    String statusText;
    Color statusColor;
    Color statusBgColor;

    if (_isViewingCamera) {
      statusText = 'Đang mở cam';
      statusColor = const Color(0xFF16A34A);
      statusBgColor = const Color(0xFFDCFCE7);
    } else if (cams.isNotEmpty) {
      statusText = 'Camera On';
      statusColor = const Color(0xFF16A34A);
      statusBgColor = const Color(0xFFDCFCE7);
    } else {
      statusText = 'Camera Off';
      statusColor = kMuted;
      statusBgColor = const Color(0xFFF1F5F9);
    }

    return Container(
      padding: EdgeInsets.only(
        top: MediaQuery.of(context).padding.top + 8,
        left: 16,
        right: 16,
        bottom: 12,
      ),
      decoration: BoxDecoration(
        color: Colors.white.withAlpha(220),
        border: const Border(bottom: BorderSide(color: kLine)),
        boxShadow: [
          BoxShadow(color: Colors.black.withAlpha(8), blurRadius: 8, offset: const Offset(0, 2)),
        ],
      ),
      child: Row(
        children: [
          // Hamburger
          GestureDetector(
            onTap: () => _scaffoldKey.currentState?.openDrawer(),
            child: const Padding(
              padding: EdgeInsets.all(4),
              child: Icon(Icons.menu, color: kInk, size: 26),
            ),
          ),
          const SizedBox(width: 8),
          // Title
          const Text('FG Client', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: kBlue, letterSpacing: -0.3)),
          const SizedBox(width: 8),
          // Status pill
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: statusBgColor,
              borderRadius: BorderRadius.circular(100),
            ),
            child: Text(
              statusText,
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w600,
                color: statusColor,
              ),
            ),
          ),
          const Spacer(),
          // Username
          Text(
            user?.name ?? 'Khách hàng',
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: kInk),
          ),
          const SizedBox(width: 8),
          // Logout icon
          GestureDetector(
            onTap: () => _showLogoutConfirm(),
            child: const Padding(
              padding: EdgeInsets.all(4),
              child: Icon(Icons.logout, size: 20, color: kMuted),
            ),
          ),
        ],
      ),
    );
  }

  void _showLogoutConfirm() {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Đăng xuất'),
        content: const Text('Bạn có chắc muốn đăng xuất không?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Hủy')),
          ElevatedButton(
            onPressed: () { Navigator.pop(context); _performLogout(); },
            style: ElevatedButton.styleFrom(backgroundColor: kRed, foregroundColor: Colors.white),
            child: const Text('Đăng xuất'),
          ),
        ],
      ),
    );
  }

  // ─── DRAWER ────────────────────────────────────────────────────────────────

  Widget _buildDrawer() {
    final user = _state.currentUser;
    final initials = user?.initials ?? 'US';
    final name = user?.name ?? 'Khách hàng';
    final role = user?.displayRole ?? 'User (Khách hàng)';

    return Drawer(
      backgroundColor: kSidebarBg,
      child: Column(
        children: [
          // Header
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  ShaderMask(
                    shaderCallback: (b) => const LinearGradient(
                      colors: [Colors.white, Color(0xFFCBD5E1)],
                    ).createShader(b),
                    child: const Text('FallGuard AI', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: Colors.white)),
                  ),
                  GestureDetector(
                    onTap: () => Navigator.of(context).pop(),
                    child: const Icon(Icons.close, color: Color(0xFF94a3b8), size: 22),
                  ),
                ],
              ),
            ),
          ),
          const Divider(color: Color(0x14FFFFFF), height: 1),

          // Menu items
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _drawerGroupTitle('TỔNG QUAN'),
                  _drawerItem('🏠 Trang chủ', 0, () { Navigator.pop(context); _switchTab(0); }),
                  const SizedBox(height: 20),

                  _drawerGroupTitle('GIÁM SÁT'),
                  _drawerItem('⚠️ Danh sách cảnh báo', 1, () { Navigator.pop(context); _switchTab(1); }),
                  const SizedBox(height: 20),

                  _drawerGroupTitle('CÁ NHÂN & LIÊN HỆ'),
                  _drawerItem('🔔 Thông báo', 2, () { Navigator.pop(context); _switchTab(2); }),
                  _drawerItem('⚙️ Thông tin cá nhân', 3, () { Navigator.pop(context); _switchTab(3); }),
                ],
              ),
            ),
          ),

          // Footer
          const Divider(color: Color(0x14FFFFFF), height: 1),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 28),
            child: Row(
              children: [
                // Avatar
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: kBlue,
                    shape: BoxShape.circle,
                    boxShadow: [BoxShadow(color: kBlue.withAlpha(80), blurRadius: 10)],
                  ),
                  child: Center(child: Text(initials, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 15))),
                ),
                const SizedBox(width: 12),
                // Name + Role
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(name, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 14)),
                      Text(role, style: const TextStyle(color: Color(0xFF64748b), fontSize: 12)),
                    ],
                  ),
                ),
                // Logout button
                GestureDetector(
                  onTap: () { Navigator.pop(context); _performLogout(); },
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18)),
                    child: const Text('Đăng xuất', style: TextStyle(color: kInk, fontSize: 12, fontWeight: FontWeight.w600)),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _drawerGroupTitle(String text) {
    return Padding(
      padding: const EdgeInsets.only(left: 12, bottom: 8),
      child: Text(
        text,
        style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: Color(0xFF475569), letterSpacing: 1),
      ),
    );
  }

  Widget _drawerItem(String label, int tabIndex, VoidCallback onTap) {
    final isActive = _currentTab == tabIndex;
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 2),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: isActive ? const Color(0xFF4f46e5).withAlpha(38) : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
          border: isActive ? const Border(left: BorderSide(color: Color(0xFF818CF8), width: 3)) : null,
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isActive ? const Color(0xFF818CF8) : const Color(0xFF94a3b8),
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }

  // ─── BOTTOM NAV ─────────────────────────────────────────────────────────────

  Widget _buildBottomNav() {
    final items = [
      (Icons.grid_view_rounded, Icons.grid_view, 'Trang chủ'),
      (Icons.warning_amber_rounded, Icons.warning_amber_outlined, 'Cảnh báo'),
      (Icons.notifications_rounded, Icons.notifications_outlined, 'Thông báo'),
      (Icons.person_rounded, Icons.person_outline_rounded, 'Hồ sơ'),
    ];

    return Container(
      height: 68,
      decoration: BoxDecoration(
        color: Colors.white.withAlpha(230),
        border: const Border(top: BorderSide(color: kLine)),
        boxShadow: [BoxShadow(color: Colors.black.withAlpha(13), blurRadius: 12, offset: const Offset(0, -4))],
      ),
      child: Row(
        children: List.generate(items.length, (i) {
          final isActive = _currentTab == i;
          return Expanded(
            child: InkWell(
              onTap: () => _switchTab(i),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    isActive ? items[i].$1 : items[i].$2,
                    color: isActive ? kBlue : kMuted,
                    size: 22,
                  ),
                  const SizedBox(height: 3),
                  Text(
                    items[i].$3,
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: isActive ? FontWeight.w700 : FontWeight.w500,
                      color: isActive ? kBlue : kMuted,
                    ),
                  ),
                ],
              ),
            ),
          );
        }),
      ),
    );
  }

  void _switchTab(int idx) {
    setState(() {
      _currentTab = idx;
    });
  }

  // ─── BODY (IndexedStack equivalent) ─────────────────────────────────────────

  Widget _buildBody() {
    return switch (_currentTab) {
      0 => _buildDashboardView(),
      1 => _buildAlertsView(),
      2 => _buildNotificationsView(),
      3 => _buildProfileView(),
      _ => _buildDashboardView(),
    };
  }

  // ─── PAGE HEADER ──────────────────────────────────────────────────────────

  Widget _pageHeader(String title, String subtitle) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: kInk)),
          const SizedBox(height: 2),
          Text(subtitle, style: const TextStyle(fontSize: 12, color: kMuted)),
        ],
      ),
    );
  }

  // ─── TAB 0: DASHBOARD ─────────────────────────────────────────────────────

  Widget _buildDashboardView() {
    final cams = _state.getVisibleCameras();
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _pageHeader('Trang chủ', 'Trạng thái các thiết bị bảo vệ người thân'),
          _card(
            title: 'Camera trực tiếp',
            child: cams.isEmpty
                ? const _EmptyState(message: 'Bạn chưa được cấp quyền xem camera nào.')
                : Column(
                    children: cams.map((c) => _cameraDashCard(c)).toList(),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _cameraDashCard(CameraModel cam) {
    return GestureDetector(
      onTap: () => _openCameraStream(cam),
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: kCard,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: kLine),
          boxShadow: [BoxShadow(color: Colors.black.withAlpha(8), blurRadius: 10, offset: const Offset(0, 4))],
        ),
        child: Column(
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(cam.name, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13, color: kInk)),
                ),
                StatusPill.fromStatus(cam.status, small: true),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Nhãn AI: ${cam.state.toUpperCase()}',
                  style: TextStyle(
                    fontSize: 11,
                    color: cam.isFallen ? kRed : kMuted,
                    fontWeight: cam.isFallen ? FontWeight.w700 : FontWeight.w400,
                  ),
                ),
                const Text('Nhấn để xem live →', style: TextStyle(fontSize: 11, color: kBlue, fontWeight: FontWeight.w700)),
              ],
            ),
          ],
        ),
      ),
    );
  }

  void _openCameraStream(CameraModel cam) {
    if (cam.isMaintenance) {
      _showSnackbar('Camera "${cam.name}" đang trong thời gian bảo trì.', isError: false);
      return;
    }
    if (!cam.isOnline) {
      _showSnackbar('Camera "${cam.name}" đang không hoạt động.', isError: true);
      return;
    }
    setState(() {
      _currentTab = 0; // keep on dashboard but show stream modal
      _isViewingCamera = true;
    });
    _showStreamSheet(cam);
  }

  void _showStreamSheet(CameraModel cam) {
    // Tự động bật pipeline server khi User mở cam (không cần Admin)
    ApiClient().startCamera(cam.rtsp.isNotEmpty ? cam.rtsp : '0', cam.id);
    
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => _LiveStreamScreen(
          camera: cam,
          streamUrl: ApiClient().mjpegUrl(),
          isBackendOnline: _isBackendOnline,
        ),
      ),
    ).then((_) {
      // Khi đóng BottomSheet, tự động gửi lệnh stop camera lên server để tắt webcam
      ApiClient().stopCamera();
      if (mounted) setState(() => _isViewingCamera = false);
    });
  }

  // ─── TAB 1: ALERTS ────────────────────────────────────────────────────────

  Widget _buildAlertsView() {
    final visibleAlerts = _state.getVisibleAlerts();
    final selected = <String>{};

    return StatefulBuilder(
      builder: (context, setSt) => Column(
        children: [
          // Toolbar
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: const BoxDecoration(
              color: kCard,
              border: Border(bottom: BorderSide(color: kLine)),
            ),
            child: Row(
              children: [
                GestureDetector(
                  onTap: () {
                    setSt(() {
                      if (selected.length == visibleAlerts.length) {
                        selected.clear();
                      } else {
                        selected.addAll(visibleAlerts.map((a) => a.id));
                      }
                    });
                  },
                  child: Row(
                    children: [
                      Icon(
                        selected.length == visibleAlerts.length && visibleAlerts.isNotEmpty
                            ? Icons.check_box
                            : Icons.check_box_outline_blank,
                        size: 20,
                        color: kBlue,
                      ),
                      const SizedBox(width: 6),
                      const Text('Chọn tất cả', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: kInk)),
                    ],
                  ),
                ),
                const Spacer(),
                if (selected.isNotEmpty)
                  TextButton(
                    onPressed: () => _deleteSelectedAlerts(selected.toList(), setSt),
                    style: TextButton.styleFrom(foregroundColor: kRed),
                    child: const Text('Xóa đã chọn', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700)),
                  ),
                TextButton(
                  onPressed: () => _deleteAllAlerts(setSt),
                  style: TextButton.styleFrom(foregroundColor: kRed),
                  child: const Text('Xóa tất cả', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700)),
                ),
              ],
            ),
          ),

          Expanded(
            child: visibleAlerts.isEmpty
                ? const Center(child: _EmptyState(message: 'Chưa có cảnh báo nào được ghi nhận.', icon: Icons.check_circle_outline))
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: visibleAlerts.length,
                    itemBuilder: (_, i) {
                      final alert = visibleAlerts[i];
                      final isSelected = selected.contains(alert.id);
                      return _alertCard(alert, isSelected, () {
                        setSt(() {
                          if (isSelected) {
                            selected.remove(alert.id);
                          } else {
                            selected.add(alert.id);
                          }
                        });
                      });
                    },
                  ),
          ),
        ],
      ),
    );
  }

  Widget _alertCard(AlertModel alert, bool isSelected, VoidCallback onToggle) {
    final isStranger = alert.id.startsWith('STRANGER');
    final title = isStranger ? '👤 Người lạ xuất hiện' : '⚠️ Cảnh báo ngã';
    final titleColor = isStranger ? kBlue : kRed;

    return GestureDetector(
      onTap: () => _showAlertDetail(alert),
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(
          color: kCard,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: isSelected ? kBlue : kLine),
          boxShadow: [BoxShadow(color: Colors.black.withAlpha(8), blurRadius: 10, offset: const Offset(0, 4))],
        ),
        padding: const EdgeInsets.all(14),
        child: Column(
          children: [
            Row(
              children: [
                GestureDetector(
                  onTap: onToggle,
                  child: Padding(
                    padding: const EdgeInsets.only(right: 10),
                    child: Icon(
                      isSelected ? Icons.check_box : Icons.check_box_outline_blank,
                      size: 20,
                      color: kBlue,
                    ),
                  ),
                ),
                Text(title, style: TextStyle(color: titleColor, fontSize: 14, fontWeight: FontWeight.w700)),
                const Spacer(),
                Text(alert.time, style: const TextStyle(fontSize: 11, color: kMuted)),
              ],
            ),
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(color: const Color(0xFFF8FAFC), borderRadius: BorderRadius.circular(8)),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _alertRow('Vị trí', alert.camera),
                  _alertRow('Người thân', alert.person),
                  Row(
                    children: [
                      const Text('Trạng thái: ', style: TextStyle(fontSize: 12, color: kMuted)),
                      StatusPill.fromStatus(alert.status, small: true),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _alertRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        children: [
          Text('$label: ', style: const TextStyle(fontSize: 12, color: kMuted)),
          Text(value, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: kInk)),
        ],
      ),
    );
  }

  void _showAlertDetail(AlertModel alert) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _AlertDetailSheet(alert: alert, apiBaseUrl: ApiClient().baseUrl),
    );
  }

  Future<void> _deleteSelectedAlerts(List<String> ids, StateSetter setSt) async {
    final confirm = await _showConfirm('Xóa ${ids.length} cảnh báo đã chọn?');
    if (!confirm) return;
    try {
      if (_isBackendOnline) await ApiClient().deleteAlerts(ids: ids);
      _state.alerts.removeWhere((a) => ids.contains(a.id));
      await _state.saveToLocal();
      setSt(() {});
      if (mounted) setState(() {});
    } catch (e) {
      _showSnackbar('Lỗi khi xóa: $e', isError: true);
    }
  }

  Future<void> _deleteAllAlerts(StateSetter setSt) async {
    final confirm = await _showConfirm('Xóa tất cả cảnh báo của bạn?');
    if (!confirm) return;
    try {
      if (_isBackendOnline) await ApiClient().deleteAlerts(deleteAll: true);
      _state.alerts.clear();
      await _state.saveToLocal();
      setSt(() {});
      if (mounted) setState(() {});
    } catch (e) {
      _showSnackbar('Lỗi khi xóa: $e', isError: true);
    }
  }

  // ─── TAB 2: NOTIFICATIONS ─────────────────────────────────────────────────

  Widget _buildNotificationsView() {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 0),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _pageHeader('Thông báo', 'Thông báo từ hệ thống'),
              TextButton(
                onPressed: () {
                  for (final n in _state.notifications) { n.read = true; }
                  _state.saveToLocal();
                  _state.pushToBackend();
                  setState(() {});
                },
                child: const Text('Đọc tất cả', style: TextStyle(color: kBlue, fontSize: 13)),
              ),
            ],
          ),
        ),
        Expanded(
          child: _state.notifications.isEmpty
              ? const Center(child: _EmptyState(message: 'Không có thông báo nào.', icon: Icons.notifications_none))
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _state.notifications.length,
                  itemBuilder: (_, i) => _notificationCard(_state.notifications[i], i),
                ),
        ),
      ],
    );
  }

  Widget _notificationCard(AppNotification notif, int idx) {
    final borderColor = switch (notif.type) {
      'fall' => kRed,
      'disconnect' => kAmber,
      'stranger' => kBlue,
      _ => kBlue,
    };
    final icon = switch (notif.type) {
      'fall' => '🚨',
      'disconnect' => '⚠️',
      'stranger' => '👤',
      _ => '🔧',
    };

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: notif.read ? kCard : const Color(0xFFF0F5FF),
        borderRadius: BorderRadius.circular(16),
        border: Border(left: BorderSide(color: borderColor, width: 4)),
        boxShadow: [BoxShadow(color: Colors.black.withAlpha(8), blurRadius: 10, offset: const Offset(0, 4))],
      ),
      padding: const EdgeInsets.all(12),
      child: Column(
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(icon, style: const TextStyle(fontSize: 20)),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            notif.title,
                            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: kInk),
                          ),
                        ),
                        if (!notif.read)
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                            decoration: BoxDecoration(color: kBlue, borderRadius: BorderRadius.circular(100)),
                            child: const Text('Mới', style: TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.w700)),
                          ),
                      ],
                    ),
                    const SizedBox(height: 3),
                    Text(notif.content, style: const TextStyle(fontSize: 11, color: Color(0xFF4B5563), height: 1.4)),
                    const SizedBox(height: 3),
                    Text(notif.time, style: const TextStyle(fontSize: 9, color: kMuted)),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          const Divider(color: kLine, height: 1),
          const SizedBox(height: 6),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              _smallBtn(
                label: notif.read ? 'Chưa đọc' : 'Đã đọc',
                onTap: () {
                  _state.notifications[idx].read = !_state.notifications[idx].read;
                  _state.saveToLocal();
                  _state.pushToBackend();
                  setState(() {});
                },
              ),
              const SizedBox(width: 8),
              _smallBtn(
                label: 'Xóa',
                color: kRed,
                onTap: () {
                  _state.notifications.removeAt(idx);
                  _state.saveToLocal();
                  _state.pushToBackend();
                  setState(() {});
                },
              ),
            ],
          ),
        ],
      ),
    );
  }

  // ─── TAB 3: PROFILE ───────────────────────────────────────────────────────

  Widget _buildProfileView() {
    final user = _state.currentUser;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _pageHeader('Hồ sơ', 'Cập nhật hồ sơ bệnh nhân và liên hệ'),

          // Personal info card
          _card(
            title: 'Thông tin liên lạc cá nhân',
            child: _UserProfileForm(
              user: user,
              isBackendOnline: _isBackendOnline,
              onSaved: (updatedUser) {
                _state.currentUser = updatedUser;
                setState(() {});
                _showSnackbar('Đã lưu thông tin thành công!');
              },
            ),
          ),
          const SizedBox(height: 16),

          // Emergency contacts card
          _card(
            title: 'Người liên hệ khẩn cấp',
            action: TextButton.icon(
              onPressed: () => _showAddContactSheet(),
              icon: const Icon(Icons.add, size: 16),
              label: const Text('Thêm'),
              style: TextButton.styleFrom(foregroundColor: kBlue),
            ),
            child: _state.emergencyContacts.isEmpty
                ? const _EmptyState(message: 'Chưa có liên hệ khẩn cấp nào.', icon: Icons.contacts_outlined)
                : Column(
                    children: _state.emergencyContacts.asMap().entries.map((e) => _contactCard(e.key, e.value)).toList(),
                  ),
          ),
          const SizedBox(height: 16),

          // Change password card
          _card(
            title: 'Đổi mật khẩu',
            child: _ChangePasswordForm(
              isBackendOnline: _isBackendOnline,
              currentUser: user,
              onSaved: () => _showSnackbar('Đã đổi mật khẩu thành công!'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _contactCard(int idx, EmergencyContact contact) {
    final isSelf = _state.currentUser?.email.toLowerCase() == contact.email.toLowerCase() ||
        _state.currentUser?.name.toLowerCase() == contact.name.toLowerCase();
    final displayRelationship = isSelf ? 'Bản thân' : contact.relationship;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: kLine),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  '${contact.name} ($displayRelationship)',
                  style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13, color: kInk),
                ),
              ),
              _smallBtn(label: 'Sửa', color: kBlue, onTap: () => _showEditContactSheet(idx, contact)),
              const SizedBox(width: 8),
              _smallBtn(label: 'Xóa', color: kRed, onTap: () => _deleteContact(idx)),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              const Text('SĐT: ', style: TextStyle(fontSize: 12, color: kMuted)),
              Text(contact.phone, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: kInk)),
            ],
          ),
          const SizedBox(height: 4),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Expanded(
                child: GestureDetector(
                  onTap: () async {
                    final uri = Uri(scheme: 'tel', path: contact.phone);
                    if (await canLaunchUrl(uri)) launchUrl(uri);
                  },
                  child: Container(
                    height: 36,
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(colors: [Color(0xFF10b981), Color(0xFF059669)]),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Center(
                      child: Text('📞 Gọi ngay', style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w700)),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: GestureDetector(
                  onTap: () => _showSnackbar('💬 Đã gửi SMS cảnh báo khẩn cấp tới ${contact.phone}!'),
                  child: Container(
                    height: 36,
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(colors: [Color(0xFFEF4444), Color(0xFFDC2626)]),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Center(
                      child: Text('🚨 Gửi cảnh báo', style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w700)),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  void _showAddContactSheet() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _ContactFormSheet(
        onSave: (contact) {
          _state.emergencyContacts.add(contact);
          _state.saveToLocal();
          _state.pushToBackend();
          setState(() {});
        },
      ),
    );
  }

  void _showEditContactSheet(int idx, EmergencyContact contact) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _ContactFormSheet(
        initial: contact,
        onSave: (updated) {
          _state.emergencyContacts[idx] = updated;
          _state.saveToLocal();
          _state.pushToBackend();
          setState(() {});
        },
      ),
    );
  }

  Future<void> _deleteContact(int idx) async {
    final confirm = await _showConfirm('Xóa liên hệ khẩn cấp này?');
    if (!confirm) return;
    _state.emergencyContacts.removeAt(idx);
    _state.saveToLocal();
    _state.pushToBackend();
    setState(() {});
  }

  // ─── SHARED HELPERS ───────────────────────────────────────────────────────

  Widget _card({required String title, required Widget child, Widget? action}) {
    return Container(
      decoration: BoxDecoration(
        color: kCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: kLine),
        boxShadow: [BoxShadow(color: Colors.black.withAlpha(5), blurRadius: 6, offset: const Offset(0, 2))],
      ),
      padding: const EdgeInsets.all(16),
      margin: const EdgeInsets.only(bottom: 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(title, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: kMuted)),
              if (action != null) ...[const Spacer(), action],
            ],
          ),
          const SizedBox(height: 14),
          child,
        ],
      ),
    );
  }

  Widget _smallBtn({required String label, required VoidCallback onTap, Color color = kMuted}) {
    return GestureDetector(
      onTap: onTap,
      child: Text(
        label,
        style: TextStyle(color: color, fontSize: 13, fontWeight: FontWeight.w700),
      ),
    );
  }

  void _showSnackbar(String message, {bool isError = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError ? kRed : kGreen,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
    );
  }

  Future<bool> _showConfirm(String message) async {
    return await showDialog<bool>(
          context: context,
          builder: (_) => AlertDialog(
            title: const Text('Xác nhận'),
            content: Text(message),
            actions: [
              TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Hủy')),
              ElevatedButton(
                onPressed: () => Navigator.pop(context, true),
                style: ElevatedButton.styleFrom(backgroundColor: kRed, foregroundColor: Colors.white),
                child: const Text('Xóa'),
              ),
            ],
          ),
        ) ??
        false;
  }
}

// ─── LIVE STREAM FULL SCREEN ──────────────────────────────────────────────────

class _LiveStreamScreen extends StatelessWidget {
  final CameraModel camera;
  final String streamUrl;
  final bool isBackendOnline;

  const _LiveStreamScreen({required this.camera, required this.streamUrl, required this.isBackendOnline});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: Colors.white),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(camera.name, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 16)),
        actions: [
          Center(
            child: Container(
              margin: const EdgeInsets.only(right: 16),
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(color: kRed, borderRadius: BorderRadius.circular(4)),
              child: const Text('LIVE', style: TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w900, letterSpacing: 1)),
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: Center(
                child: AspectRatio(
                  aspectRatio: 16 / 9,
                  child: MjpegView(streamUrl: streamUrl, isBackendOnline: isBackendOnline),
                ),
              ),
            ),
            // Status badge
            Container(
              padding: const EdgeInsets.all(20),
              color: const Color(0xFF111111),
              child: Row(
                children: [
                  StatusPill.fromStatus(camera.status),
                  const SizedBox(width: 12),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: camera.isFallen ? kRed.withAlpha(30) : kGreen.withAlpha(30),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: camera.isFallen ? kRed : kGreen),
                    ),
                    child: Text(
                      camera.state.toUpperCase(),
                      style: TextStyle(
                        color: camera.isFallen ? kRed : kGreen,
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  const Spacer(),
                  Text(camera.id, style: const TextStyle(color: Colors.white54, fontSize: 12)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─── ALERT DETAIL BOTTOM SHEET ─────────────────────────────────────────────────

class _AlertDetailSheet extends StatelessWidget {
  final AlertModel alert;
  final String apiBaseUrl;

  const _AlertDetailSheet({required this.alert, required this.apiBaseUrl});

  @override
  Widget build(BuildContext context) {
    final imgSrc = alert.cloudImgUrl ?? '$apiBaseUrl/media/${alert.id}.jpg';
    final videoSrc = alert.cloudVideoUrl ?? '$apiBaseUrl/media/${alert.id}.mp4';
    final isStranger = alert.id.startsWith('STRANGER');
    final title = isStranger ? 'Chi tiết người lạ' : 'Chi tiết cảnh báo ngã';
    final titleColor = isStranger ? kBlue : kInk;

    return DraggableScrollableSheet(
      initialChildSize: 0.75,
      maxChildSize: 0.95,
      builder: (_, sc) => Container(
        decoration: const BoxDecoration(
          color: kCard,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: Column(
          children: [
            Center(
              child: Container(
                margin: const EdgeInsets.symmetric(vertical: 10),
                width: 40,
                height: 4,
                decoration: BoxDecoration(color: kLine, borderRadius: BorderRadius.circular(2)),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  Text(title, style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: titleColor)),
                  const Spacer(),
                  IconButton(onPressed: () => Navigator.pop(context), icon: const Icon(Icons.close, color: kMuted)),
                ],
              ),
            ),
            const Divider(color: kLine),
            Expanded(
              child: SingleChildScrollView(
                controller: sc,
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Image preview
                    Stack(
                      children: [
                        ClipRRect(
                          borderRadius: BorderRadius.circular(10),
                          child: AspectRatio(
                            aspectRatio: 16 / 9,
                            child: Image.network(
                              imgSrc,
                              fit: BoxFit.cover,
                              errorBuilder: (_, __, ___) => Container(
                                color: kBg,
                                child: const Center(child: Icon(Icons.broken_image, color: kMuted, size: 40)),
                              ),
                            ),
                          ),
                        ),
                        if (alert.cloudImgUrl != null)
                          Positioned(
                            top: 8,
                            right: 8,
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: Colors.black.withAlpha(150),
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: const Text('☁️ Cloudinary', style: TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.w700)),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    // Details
                    _detailRow('ID cảnh báo', alert.id),
                    _detailRow('Thời gian', alert.time),
                    _detailRow('Camera', alert.camera),
                    _detailRow('Người thân', alert.person),
                    _detailRow('Độ tin cậy AI', '${alert.confidence}%'),
                    _detailRow('Mức độ', alert.level),
                    _detailRow('Trạng thái', alert.status),
                    if (alert.cloudVideoUrl != null) ...[
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: kGreen.withAlpha(20),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: kGreen.withAlpha(50)),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('☁️ Lưu trữ Cloudinary', style: TextStyle(color: kGreen, fontWeight: FontWeight.w700, fontSize: 12)),
                            const SizedBox(height: 4),
                            GestureDetector(
                              onTap: () async {
                                final uri = Uri.parse(videoSrc);
                                if (await canLaunchUrl(uri)) launchUrl(uri);
                              },
                              child: Text(videoSrc, style: const TextStyle(color: kBlue, fontSize: 11, decoration: TextDecoration.underline)),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _detailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 120,
            child: Text(label, style: const TextStyle(fontSize: 12, color: kMuted)),
          ),
          Expanded(
            child: Text(value, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: kInk)),
          ),
        ],
      ),
    );
  }
}

// ─── CONTACT FORM BOTTOM SHEET ─────────────────────────────────────────────────

class _ContactFormSheet extends StatefulWidget {
  final EmergencyContact? initial;
  final void Function(EmergencyContact) onSave;

  const _ContactFormSheet({this.initial, required this.onSave});

  @override
  State<_ContactFormSheet> createState() => _ContactFormSheetState();
}

class _ContactFormSheetState extends State<_ContactFormSheet> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _name;
  late final TextEditingController _relationship;
  late final TextEditingController _phone;
  late final TextEditingController _email;

  @override
  void initState() {
    super.initState();
    final c = widget.initial;
    _name = TextEditingController(text: c?.name ?? '');
    _relationship = TextEditingController(text: c?.relationship ?? '');
    _phone = TextEditingController(text: c?.phone ?? '');
    _email = TextEditingController(text: c?.email ?? '');
  }

  @override
  void dispose() {
    _name.dispose(); _relationship.dispose(); _phone.dispose(); _email.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isEdit = widget.initial != null;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        decoration: const BoxDecoration(
          color: kCard,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: const EdgeInsets.all(20),
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(isEdit ? 'Sửa liên hệ khẩn cấp' : 'Thêm liên hệ khẩn cấp',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: kInk)),
                  const Spacer(),
                  IconButton(onPressed: () => Navigator.pop(context), icon: const Icon(Icons.close, color: kMuted)),
                ],
              ),
              const Divider(color: kLine),
              const SizedBox(height: 8),
              _formField('Họ và tên', _name, required: true),
              _formField('Mối quan hệ', _relationship, hint: 'Con gái, Bác sĩ...', required: true),
              _formField('Số điện thoại', _phone, keyboardType: TextInputType.phone, required: true),
              _formField('Email', _email, keyboardType: TextInputType.emailAddress, required: true),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text('Hủy'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () {
                        if (!_formKey.currentState!.validate()) return;
                        final contact = EmergencyContact(
                          name: _name.text.trim(),
                          relationship: _relationship.text.trim(),
                          phone: _phone.text.trim(),
                          email: _email.text.trim(),
                        );
                        widget.onSave(contact);
                        Navigator.pop(context);
                      },
                      style: ElevatedButton.styleFrom(backgroundColor: kBlue, foregroundColor: Colors.white),
                      child: Text(isEdit ? 'Lưu thay đổi' : 'Thêm'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _formField(String label, TextEditingController ctrl, {String? hint, TextInputType? keyboardType, bool required = false}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: kInk)),
          const SizedBox(height: 4),
          TextFormField(
            controller: ctrl,
            keyboardType: keyboardType,
            decoration: InputDecoration(
              hintText: hint,
              filled: true,
              fillColor: const Color(0xFFF8FAFC),
              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: kLine)),
              enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: kLine)),
              focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: kBlue, width: 2)),
            ),
            validator: required ? (v) => (v == null || v.trim().isEmpty) ? 'Bắt buộc' : null : null,
          ),
        ],
      ),
    );
  }
}

// ─── USER PROFILE FORM ─────────────────────────────────────────────────────────

class _UserProfileForm extends StatefulWidget {
  final UserModel? user;
  final bool isBackendOnline;
  final void Function(UserModel) onSaved;

  const _UserProfileForm({this.user, required this.isBackendOnline, required this.onSaved});

  @override
  State<_UserProfileForm> createState() => _UserProfileFormState();
}

class _UserProfileFormState extends State<_UserProfileForm> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _name;
  late final TextEditingController _phone;
  late final TextEditingController _email;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _name = TextEditingController(text: widget.user?.name ?? '');
    _phone = TextEditingController(text: widget.user?.phone ?? '');
    _email = TextEditingController(text: widget.user?.email ?? '');
  }

  @override
  void dispose() { _name.dispose(); _phone.dispose(); _email.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      child: Column(
        children: [
          _field('Họ và tên', _name, required: true),
          _field('Số điện thoại', _phone, keyboardType: TextInputType.phone),
          _field('Email tài khoản', _email, keyboardType: TextInputType.emailAddress, required: true),
          const SizedBox(height: 6),
          SizedBox(
            width: double.infinity,
            height: 42,
            child: ElevatedButton(
              onPressed: _saving ? null : _save,
              style: ElevatedButton.styleFrom(backgroundColor: kBlue, foregroundColor: Colors.white, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8))),
              child: _saving ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2)) : const Text('Lưu thay đổi', style: TextStyle(fontWeight: FontWeight.w700)),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      final updated = (widget.user ?? const UserModel(email: '', name: '', role: 'Khachhang')).copyWith(
        name: _name.text.trim(),
        phone: _phone.text.trim(),
        email: _email.text.trim().toLowerCase(),
      );
      if (widget.isBackendOnline) {
        await ApiClient().updateUser(widget.user?.email ?? updated.email, updated.toJson());
      }
      widget.onSaved(updated);
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message), backgroundColor: kRed));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Widget _field(String label, TextEditingController ctrl, {TextInputType? keyboardType, bool required = false}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: kInk)),
          const SizedBox(height: 4),
          TextFormField(
            controller: ctrl,
            keyboardType: keyboardType,
            decoration: InputDecoration(
              filled: true,
              fillColor: const Color(0xFFF8FAFC),
              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: kLine)),
              enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: kLine)),
              focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: kBlue, width: 2)),
            ),
            validator: required ? (v) => (v == null || v.trim().isEmpty) ? 'Bắt buộc' : null : null,
          ),
        ],
      ),
    );
  }
}

// ─── CHANGE PASSWORD FORM ──────────────────────────────────────────────────────

class _ChangePasswordForm extends StatefulWidget {
  final bool isBackendOnline;
  final UserModel? currentUser;
  final VoidCallback onSaved;

  const _ChangePasswordForm({required this.isBackendOnline, this.currentUser, required this.onSaved});

  @override
  State<_ChangePasswordForm> createState() => _ChangePasswordFormState();
}

class _ChangePasswordFormState extends State<_ChangePasswordForm> {
  final _formKey = GlobalKey<FormState>();
  final _old = TextEditingController();
  final _newPwd = TextEditingController();
  final _confirm = TextEditingController();
  bool _saving = false;

  @override
  void dispose() { _old.dispose(); _newPwd.dispose(); _confirm.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      child: Column(
        children: [
          _pwdField('Mật khẩu cũ', _old),
          _pwdField('Mật khẩu mới', _newPwd),
          _pwdField('Xác nhận mật khẩu mới', _confirm),
          const SizedBox(height: 6),
          SizedBox(
            width: double.infinity,
            height: 42,
            child: ElevatedButton(
              onPressed: _saving ? null : _save,
              style: ElevatedButton.styleFrom(backgroundColor: kBlue, foregroundColor: Colors.white, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8))),
              child: _saving ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2)) : const Text('Cập nhật mật khẩu', style: TextStyle(fontWeight: FontWeight.w700)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _pwdField(String label, TextEditingController ctrl) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: kInk)),
          const SizedBox(height: 4),
          TextFormField(
            controller: ctrl,
            obscureText: true,
            decoration: InputDecoration(
              filled: true,
              fillColor: const Color(0xFFF8FAFC),
              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: kLine)),
              enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: kLine)),
              focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: kBlue, width: 2)),
            ),
            validator: (v) => (v == null || v.isEmpty) ? 'Bắt buộc' : null,
          ),
        ],
      ),
    );
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    if (_newPwd.text != _confirm.text) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Xác nhận mật khẩu không khớp!'), backgroundColor: kRed));
      return;
    }
    setState(() => _saving = true);
    try {
      if (widget.isBackendOnline && widget.currentUser != null) {
        final payload = {...widget.currentUser!.toJson(), 'password': _newPwd.text};
        await ApiClient().updateUser(widget.currentUser!.email, payload);
      }
      _old.clear(); _newPwd.clear(); _confirm.clear();
      widget.onSaved();
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message), backgroundColor: kRed));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }
}

// ─── EMPTY STATE ──────────────────────────────────────────────────────────────

class _EmptyState extends StatelessWidget {
  final String message;
  final IconData icon;

  const _EmptyState({required this.message, this.icon = Icons.inbox_outlined});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 30),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: kMuted, size: 40),
            const SizedBox(height: 12),
            Text(message, style: const TextStyle(color: kMuted, fontSize: 13), textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}


