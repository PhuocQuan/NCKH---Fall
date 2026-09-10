// lib/screens/home_screen.dart
// Màn hình chính — Bottom Navigation + Drawer + 5 Tab views
// Thiết kế theo src/web/mobile/user.html + mobile_user.css

import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:video_player/video_player.dart';
import 'package:http/http.dart' as http;
import 'package:package_info_plus/package_info_plus.dart';
import 'package:intl/intl.dart';
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
  int _alertsPage = 0;
  int _alertFilter = 0; // 0=all, 1=fall, 2=stranger
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
    
    // Check for app updates
    _checkForUpdates();
  }

  Future<void> _checkForUpdates() async {
    try {
      final packageInfo = await PackageInfo.fromPlatform();
      final currentVersion = packageInfo.version; 
      
      // GitHub Repo details
      const githubUrl = 'https://api.github.com/repos/PhuocQuan/NCKH---Fall/releases/latest';
      
      final response = await http.get(Uri.parse(githubUrl));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final latestTagName = data['tag_name'] as String;
        final latestVersion = latestTagName.replaceAll('v', '');
        
        if (_isNewerVersion(currentVersion, latestVersion)) {
          if (!mounted) return;
          final url = data['html_url'] ?? 'https://github.com/PhuocQuan/NCKH---Fall/releases';
          _state.notifications.removeWhere((n) => n.type == 'update');
          _state.notifications.insert(0, AppNotification(
             id: 'UPDATE_$latestTagName',
             title: '🌟 Cập nhật ứng dụng',
             content: 'Đã có phiên bản FallGuard mới ($latestTagName). Vui lòng tải và cài đặt để trải nghiệm tính năng mới nhất!',
             time: DateFormat('dd/MM/yyyy HH:mm').format(DateTime.now()),
             read: false,
             type: 'update',
          ));
          _state.saveToLocal();
          if (mounted) {
            setState(() {});
            _showUpdateDialog(latestTagName, url);
          }
        }
      }
    } catch (e) {
      debugPrint("Update check failed: $e");
    }
  }

  bool _isNewerVersion(String current, String latest) {
    try {
      final v1 = current.split('.').map(int.parse).toList();
      final v2 = latest.split('.').map(int.parse).toList();
      for (int i = 0; i < 3; i++) {
        final part1 = i < v1.length ? v1[i] : 0;
        final part2 = i < v2.length ? v2[i] : 0;
        if (part2 > part1) return true;
        if (part2 < part1) return false;
      }
    } catch (_) {}
    return false;
  }

  void _showUpdateDialog(String version, String url) {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        backgroundColor: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Row(
          children: [
            Text('🌟', style: TextStyle(fontSize: 24)),
            SizedBox(width: 8),
            Text('Cập nhật ứng dụng', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
          ],
        ),
        content: Text(
          'Đã có phiên bản FallGuard mới ($version).\n\nVui lòng tải và cài đặt để trải nghiệm tính năng mới nhất và sửa lỗi!',
          style: const TextStyle(fontSize: 15, color: Color(0xFF334155), height: 1.5),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Để sau', style: TextStyle(color: Color(0xFF64748b), fontWeight: FontWeight.bold)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF4f46e5),
              foregroundColor: Colors.white,
              elevation: 0,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: () {
              Navigator.pop(ctx);
              launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
            },
            child: const Text('Tải ngay (APK)', style: TextStyle(fontWeight: FontWeight.bold)),
          )
        ],
      ),
    );
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

    if (!_isBackendOnline) {
      statusText = 'Offline';
      statusColor = const Color(0xFFEF4444); // Red
      statusBgColor = const Color(0xFFFEE2E2); // Light Red
    } else if (_isViewingCamera) {
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
                  _drawerItem(
                    '🚨 Cảnh báo té ngã',
                    1,
                    () {
                      Navigator.pop(context);
                      setState(() {
                        _alertFilter = 1;
                        _alertsPage = 0;
                        _currentTab = 1;
                      });
                    },
                    badgeCount: _state.getVisibleAlerts().where((a) => a.isFall && a.status == 'Chưa xử lý').length,
                    badgeColor: kRed,
                    isActive: _currentTab == 1 && _alertFilter == 1,
                  ),
                  _drawerItem(
                    '👤 Cảnh báo người lạ',
                    1,
                    () {
                      Navigator.pop(context);
                      setState(() {
                        _alertFilter = 2;
                        _alertsPage = 0;
                        _currentTab = 1;
                      });
                    },
                    badgeCount: _state.getVisibleAlerts().where((a) => a.isStranger && a.status == 'Chưa xử lý').length,
                    badgeColor: kAmber,
                    isActive: _currentTab == 1 && _alertFilter == 2,
                  ),
                  const SizedBox(height: 20),

                  _drawerGroupTitle('CÁ NHÂN & LIÊN HỆ'),
                  _drawerItem(
                    '🔔 Thông báo',
                    2,
                    () { Navigator.pop(context); _switchTab(2); },
                    badgeCount: _state.notifications.where((n) => !n.read).length,
                    badgeColor: kBlue,
                    isActive: _currentTab == 2,
                  ),
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

  Widget _drawerItem(
    String label,
    int tabIndex,
    VoidCallback onTap, {
    int? badgeCount,
    Color? badgeColor,
    bool? isActive,
  }) {
    final active = isActive ?? (_currentTab == tabIndex);
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 2),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: active ? const Color(0xFF4f46e5).withAlpha(38) : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
          border: active ? const Border(left: BorderSide(color: Color(0xFF818CF8), width: 3)) : null,
        ),
        child: Row(
          children: [
            Expanded(
              child: Text(
                label,
                style: TextStyle(
                  color: active ? const Color(0xFF818CF8) : const Color(0xFF94a3b8),
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            if (badgeCount != null && badgeCount > 0)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                decoration: BoxDecoration(
                  color: badgeColor ?? kRed,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '$badgeCount',
                  style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                ),
              ),
          ],
        ),
      ),
    );
  }

  // ─── BOTTOM NAV ─────────────────────────────────────────────────────────────

  Widget _buildBottomNav() {
    final visibleAlerts = _state.getVisibleAlerts();
    final pendingCount = visibleAlerts.where((a) => a.status == 'Chưa xử lý').length;
    final unreadNotifs = _state.notifications.where((n) => !n.read).length;

    final items = [
      (Icons.grid_view_rounded, Icons.grid_view, 'Trang chủ', 0),
      (Icons.warning_amber_rounded, Icons.warning_amber_outlined, 'Cảnh báo', pendingCount),
      (Icons.notifications_rounded, Icons.notifications_outlined, 'Thông báo', unreadNotifs),
      (Icons.person_rounded, Icons.person_outline_rounded, 'Hồ sơ', 0),
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
          final badge = items[i].$4;
          return Expanded(
            child: InkWell(
              onTap: () => _switchTab(i),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Stack(
                    clipBehavior: Clip.none,
                    children: [
                      Icon(
                        isActive ? items[i].$1 : items[i].$2,
                        color: isActive ? kBlue : kMuted,
                        size: 22,
                      ),
                      if (badge > 0)
                        Positioned(
                          top: -4,
                          right: -8,
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                            decoration: BoxDecoration(
                              color: i == 1 ? kRed : kBlue,
                              borderRadius: BorderRadius.circular(10),
                            ),
                            constraints: const BoxConstraints(minWidth: 16, minHeight: 16),
                            child: Text(
                              badge > 99 ? '99+' : '$badge',
                              style: const TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.bold),
                              textAlign: TextAlign.center,
                            ),
                          ),
                        ),
                    ],
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
    final allVisibleAlerts = _state.getVisibleAlerts();
    final fallCount = allVisibleAlerts.where((a) => a.isFall).length;
    final strangerCount = allVisibleAlerts.where((a) => a.isStranger).length;

    final visibleAlerts = switch (_alertFilter) {
      1 => allVisibleAlerts.where((a) => a.isFall).toList(),
      2 => allVisibleAlerts.where((a) => a.isStranger).toList(),
      _ => allVisibleAlerts,
    };
    final selected = <String>{};
    const int alertsPerPage = 10;

    return StatefulBuilder(
      builder: (context, setSt) {
        final totalPages = (visibleAlerts.length / alertsPerPage).ceil();
        if (_alertsPage >= totalPages && totalPages > 0) {
          _alertsPage = totalPages - 1;
        } else if (_alertsPage < 0) {
          _alertsPage = 0;
        }

        final startIndex = _alertsPage * alertsPerPage;
        final endIndex = (startIndex + alertsPerPage < visibleAlerts.length) ? startIndex + alertsPerPage : visibleAlerts.length;
        final pagedAlerts = visibleAlerts.isEmpty ? <AlertModel>[] : visibleAlerts.sublist(startIndex, endIndex);

        return Column(
          children: [
            // Filter segmented chips
            Container(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
              color: kCard,
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: [
                    _alertFilterChip('Tất cả (${allVisibleAlerts.length})', 0, setSt),
                    const SizedBox(width: 8),
                    _alertFilterChip('🚨 Té ngã ($fallCount)', 1, setSt, color: kRed),
                    const SizedBox(width: 8),
                    _alertFilterChip('👤 Người lạ ($strangerCount)', 2, setSt, color: const Color(0xFFD97706)),
                  ],
                ),
              ),
            ),

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
              child: pagedAlerts.isEmpty
                  ? Center(
                      child: _EmptyState(
                        message: _alertFilter == 1
                            ? 'Chưa có sự cố té ngã nào được ghi nhận.'
                            : _alertFilter == 2
                                ? 'Chưa có người lạ nào xuất hiện.'
                                : 'Chưa có cảnh báo nào được ghi nhận.',
                        icon: Icons.check_circle_outline,
                      ),
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.all(16),
                      itemCount: pagedAlerts.length,
                      itemBuilder: (_, i) {
                        final alert = pagedAlerts[i];
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
            
            if (totalPages > 1)
              Container(
                padding: const EdgeInsets.symmetric(vertical: 8),
                decoration: const BoxDecoration(
                  color: kCard,
                  border: Border(top: BorderSide(color: kLine)),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    IconButton(
                      icon: const Icon(Icons.chevron_left),
                      onPressed: _alertsPage > 0 ? () => setSt(() => _alertsPage--) : null,
                    ),
                    Text('Trang ${_alertsPage + 1} / $totalPages', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                    IconButton(
                      icon: const Icon(Icons.chevron_right),
                      onPressed: _alertsPage < totalPages - 1 ? () => setSt(() => _alertsPage++) : null,
                    ),
                  ],
                ),
              ),
          ],
        );
      },
    );
  }

  Widget _alertFilterChip(String label, int filterIndex, StateSetter setSt, {Color color = kBlue}) {
    final isSelected = _alertFilter == filterIndex;
    return GestureDetector(
      onTap: () {
        setSt(() {
          _alertFilter = filterIndex;
          _alertsPage = 0;
        });
        setState(() {});
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? color : const Color(0xFFF1F5F9),
          borderRadius: BorderRadius.circular(100),
          border: Border.all(
            color: isSelected ? color : const Color(0xFFCBD5E1),
            width: 1,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? Colors.white : const Color(0xFF475569),
            fontSize: 12,
            fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
          ),
        ),
      ),
    );
  }

  Widget _alertCard(AlertModel alert, bool isSelected, VoidCallback onToggle) {
    final isStranger = alert.isStranger;
    final title = isStranger ? '👤 Phát hiện người lạ' : '🚨 Cảnh báo té ngã';
    final titleColor = isStranger ? const Color(0xFFD97706) : kRed;
    final pillBg = isStranger ? const Color(0xFFFEF3C7) : const Color(0xFFFEE2E2);
    final pillBorder = isStranger ? const Color(0xFFFDE68A) : const Color(0xFFFECACA);
    final tagText = isStranger ? 'Người lạ' : 'Té ngã';

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
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  margin: const EdgeInsets.only(right: 8),
                  decoration: BoxDecoration(
                    color: pillBg,
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: pillBorder),
                  ),
                  child: Text(tagText, style: TextStyle(color: titleColor, fontSize: 10, fontWeight: FontWeight.bold)),
                ),
                Expanded(
                  child: Text(title, style: TextStyle(color: titleColor, fontSize: 13, fontWeight: FontWeight.w700), overflow: TextOverflow.ellipsis),
                ),
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
                  _alertRow(isStranger ? 'Đối tượng' : 'Người thân', alert.person),
                  _alertRow('Độ tin cậy', '${alert.confidence}% ${isStranger ? '(YuNet)' : '(MediaPipe)'}'),
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
              Row(
                children: [
                  TextButton(
                    onPressed: () {
                      for (final n in _state.notifications) { n.read = true; }
                      _state.saveToLocal();
                      _state.pushToBackend();
                      setState(() {});
                    },
                    child: const Text('Đọc tất cả', style: TextStyle(color: kBlue, fontSize: 13)),
                  ),
                  TextButton(
                    onPressed: () async {
                      final confirm = await _showConfirm('Xóa tất cả thông báo?');
                      if (confirm && mounted) {
                        _state.notifications.removeWhere((n) => n.type != 'update');
                        _state.saveToLocal();
                        _state.pushToBackend();
                        setState(() {});
                      }
                    },
                    child: const Text('Xóa tất cả', style: TextStyle(color: kRed, fontSize: 13)),
                  ),
                ],
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
      'update' => kGreen,
      _ => kBlue,
    };
    final icon = switch (notif.type) {
      'fall' => '🚨',
      'disconnect' => '⚠️',
      'stranger' => '👤',
      'update' => '🌟',
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
              if (notif.type == 'update') ...[
                _smallBtn(
                  label: 'Tải bản cập nhật mới nhất',
                  onTap: () {
                    launchUrl(Uri.parse('https://github.com/PhuocQuan/NCKH---Fall/releases/latest'), mode: LaunchMode.externalApplication);
                  },
                ),
                const SizedBox(width: 8),
              ],
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
              if (notif.type == 'update' && notif.actionUrl != null) ...[
                const SizedBox(width: 8),
                _smallBtn(
                  label: 'Tải bản mới',
                  color: kBlue,
                  onTap: () async {
                    final uri = Uri.parse(notif.actionUrl!);
                    if (await canLaunchUrl(uri)) {
                      await launchUrl(uri, mode: LaunchMode.externalApplication);
                    }
                  },
                ),
              ],
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
    final isStranger = alert.isStranger;
    final title = isStranger ? '👤 Chi tiết người lạ xuất hiện' : '🚨 Chi tiết sự cố té ngã';
    final titleColor = isStranger ? const Color(0xFFD97706) : kRed;

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
                    _detailRow(isStranger ? 'Đối tượng' : 'Người thân', alert.person),
                    _detailRow('Độ tin cậy AI', '${alert.confidence}% ${isStranger ? '(YuNet / SFace)' : '(MediaPipe Pose)'}'),
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
                            const Text('☁️ Video Cloudinary', style: TextStyle(color: kGreen, fontWeight: FontWeight.w700, fontSize: 12)),
                            const SizedBox(height: 8),
                            _VideoPlayerWidget(url: videoSrc),
                            const SizedBox(height: 8),
                            GestureDetector(
                              onTap: () async {
                                final uri = Uri.parse(videoSrc);
                                if (await canLaunchUrl(uri)) launchUrl(uri, mode: LaunchMode.externalApplication);
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

// ─── VIDEO PLAYER WIDGET ───────────────────────────────────────────────────────

class _VideoPlayerWidget extends StatefulWidget {
  final String url;
  const _VideoPlayerWidget({required this.url});

  @override
  State<_VideoPlayerWidget> createState() => _VideoPlayerWidgetState();
}

class _VideoPlayerWidgetState extends State<_VideoPlayerWidget> {
  late VideoPlayerController _controller;
  bool _initialized = false;
  bool _error = false;
  String _errorMsg = '';

  @override
  void initState() {
    super.initState();
    _controller = VideoPlayerController.networkUrl(Uri.parse(widget.url))
      ..initialize().then((_) {
        if (mounted) setState(() => _initialized = true);
      }).catchError((e) {
        debugPrint('Video error: $e');
        if (mounted) setState(() { _error = true; _errorMsg = e.toString(); });
      });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_error) {
      return Container(
        padding: const EdgeInsets.all(8),
        color: kRed.withAlpha(20),
        child: Column(
          children: [
            const Text('Lỗi tải video', style: TextStyle(color: kRed, fontWeight: FontWeight.bold, fontSize: 13)),
            Text(_errorMsg, style: const TextStyle(color: kRed, fontSize: 11), textAlign: TextAlign.center),
          ],
        ),
      );
    }
    if (!_initialized) return const SizedBox(height: 150, child: Center(child: CircularProgressIndicator()));
    
    return Column(
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: AspectRatio(
            aspectRatio: _controller.value.aspectRatio,
            child: VideoPlayer(_controller),
          ),
        ),
        const SizedBox(height: 4),
        IconButton(
          icon: Icon(
            _controller.value.isPlaying ? Icons.pause_circle_filled : Icons.play_circle_fill,
            color: kGreen,
            size: 32,
          ),
          onPressed: () {
            setState(() {
              _controller.value.isPlaying ? _controller.pause() : _controller.play();
            });
          },
        ),
      ],
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
  String? _relationship;
  late final TextEditingController _phone;
  late final TextEditingController _email;
  
  final List<String> _relationshipOptions = [
    'Con trai', 'Con gái', 'Vợ', 'Chồng', 'Bố', 'Mẹ', 'Anh/Chị/Em', 'Họ hàng', 'Bác sĩ', 'Y tá', 'Bạn bè', 'Khác'
  ];

  @override
  void initState() {
    super.initState();
    final c = widget.initial;
    _name = TextEditingController(text: c?.name ?? '');
    _phone = TextEditingController(text: c?.phone ?? '');
    _email = TextEditingController(text: c?.email ?? '');
    
    _relationship = c?.relationship;
    if (_relationship != null && _relationship!.isNotEmpty && !_relationshipOptions.contains(_relationship)) {
      _relationshipOptions.add(_relationship!); // Keep existing values
    }
  }

  @override
  void dispose() {
    _name.dispose(); _phone.dispose(); _email.dispose();
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
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Mối quan hệ', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: kInk)),
                    const SizedBox(height: 4),
                    DropdownButtonFormField<String>(
                      initialValue: _relationship,
                      decoration: InputDecoration(
                        filled: true,
                        fillColor: const Color(0xFFF8FAFC),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: kLine)),
                        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: kLine)),
                        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: kBlue, width: 2)),
                      ),
                      hint: const Text('Chọn mối quan hệ'),
                      items: _relationshipOptions.map((e) => DropdownMenuItem(value: e, child: Text(e))).toList(),
                      onChanged: (v) {
                        setState(() {
                          _relationship = v;
                        });
                      },
                      validator: (v) => (v == null || v.isEmpty) ? 'Bắt buộc' : null,
                    ),
                  ],
                ),
              ),
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
                          relationship: _relationship ?? '',
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
  bool _isEditing = false;

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
    if (!_isEditing) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _infoRow('Họ và tên', widget.user?.name ?? 'Chưa cập nhật'),
          _infoRow('Số điện thoại', (widget.user?.phone?.isEmpty ?? true) ? 'Chưa cập nhật' : widget.user!.phone!),
          _infoRow('Email tài khoản', widget.user?.email ?? 'Chưa cập nhật'),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            height: 42,
            child: OutlinedButton.icon(
              onPressed: () => setState(() => _isEditing = true),
              icon: const Icon(Icons.edit, size: 16),
              label: const Text('Chỉnh sửa thông tin'),
              style: OutlinedButton.styleFrom(
                foregroundColor: kBlue,
                side: const BorderSide(color: kBlue),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
            ),
          ),
        ],
      );
    }

    return Form(
      key: _formKey,
      child: Column(
        children: [
          _field('Họ và tên', _name, required: true),
          _field('Số điện thoại', _phone, keyboardType: TextInputType.phone),
          _field('Email tài khoản', _email, keyboardType: TextInputType.emailAddress, required: true, isEmail: true),
          const SizedBox(height: 6),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: _saving ? null : () {
                    _name.text = widget.user?.name ?? '';
                    _phone.text = widget.user?.phone ?? '';
                    _email.text = widget.user?.email ?? '';
                    setState(() => _isEditing = false);
                  },
                  style: OutlinedButton.styleFrom(
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    padding: const EdgeInsets.symmetric(vertical: 11),
                  ),
                  child: const Text('Hủy'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                flex: 2,
                child: ElevatedButton(
                  onPressed: _saving ? null : _save,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: kBlue,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    padding: const EdgeInsets.symmetric(vertical: 11),
                  ),
                  child: _saving ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2)) : const Text('Lưu thay đổi', style: TextStyle(fontWeight: FontWeight.w700)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _infoRow(String label, String value) {
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

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      String newEmail = _email.text.trim().toLowerCase();
      if (newEmail.endsWith('@nckh')) {
        newEmail = '$newEmail.vn';
      } else if (newEmail.isNotEmpty && !newEmail.contains('@')) {
        newEmail = '$newEmail@nckh.vn';
      }

      final updated = (widget.user ?? const UserModel(email: '', name: '', role: 'Khachhang')).copyWith(
        name: _name.text.trim(),
        phone: _phone.text.trim(),
        email: newEmail,
      );
      
      final bool emailChanged = widget.user != null && widget.user!.email.toLowerCase() != newEmail;

      if (emailChanged && mounted) {
        final confirm = await showDialog<bool>(
          context: context,
          builder: (_) => AlertDialog(
            title: const Text('Xác nhận đổi Email'),
            content: const Text('Đổi email sẽ thay đổi tài khoản đăng nhập của bạn. Bạn sẽ bị đăng xuất và phải đăng nhập lại. Bạn có chắc chắn muốn đổi không?'),
            actions: [
              TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Hủy')),
              ElevatedButton(
                onPressed: () => Navigator.pop(context, true),
                style: ElevatedButton.styleFrom(backgroundColor: kBlue, foregroundColor: Colors.white),
                child: const Text('Đồng ý'),
              ),
            ],
          ),
        );
        if (confirm != true) {
          if (mounted) setState(() => _saving = false);
          return;
        }
      }

      if (widget.isBackendOnline) {
        await ApiClient().updateUser(widget.user?.email ?? updated.email, updated.toJson());
      }
      widget.onSaved(updated);
      if (mounted) setState(() => _isEditing = false);
      
      if (emailChanged) {
        await AuthService().clearSession();
        if (!mounted) return;
        Navigator.of(context).pushReplacementNamed('/login');
      }
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message), backgroundColor: kRed));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Widget _field(String label, TextEditingController ctrl, {TextInputType? keyboardType, bool required = false, bool isEmail = false}) {
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
            inputFormatters: isEmail ? [
              TextInputFormatter.withFunction((oldValue, newValue) {
                return TextEditingValue(text: newValue.text.toLowerCase(), selection: newValue.selection);
              })
            ] : null,
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
  bool _isEditing = false;

  @override
  void dispose() { _old.dispose(); _newPwd.dispose(); _confirm.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    if (!_isEditing) {
      return SizedBox(
        width: double.infinity,
        height: 42,
        child: OutlinedButton.icon(
          onPressed: () => setState(() => _isEditing = true),
          icon: const Icon(Icons.lock_reset, size: 16),
          label: const Text('Đổi mật khẩu'),
          style: OutlinedButton.styleFrom(
            foregroundColor: kBlue,
            side: const BorderSide(color: kBlue),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          ),
        ),
      );
    }

    return Form(
      key: _formKey,
      child: Column(
        children: [
          _pwdField('Mật khẩu cũ', _old),
          _pwdField('Mật khẩu mới', _newPwd),
          _pwdField('Xác nhận mật khẩu mới', _confirm),
          const SizedBox(height: 6),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: _saving ? null : () {
                    _old.clear(); _newPwd.clear(); _confirm.clear();
                    setState(() => _isEditing = false);
                  },
                  style: OutlinedButton.styleFrom(
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    padding: const EdgeInsets.symmetric(vertical: 11),
                  ),
                  child: const Text('Hủy'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                flex: 2,
                child: ElevatedButton(
                  onPressed: _saving ? null : _save,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: kBlue,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    padding: const EdgeInsets.symmetric(vertical: 11),
                  ),
                  child: _saving ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2)) : const Text('Cập nhật', style: TextStyle(fontWeight: FontWeight.w700)),
                ),
              ),
            ],
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
      if (mounted) setState(() => _isEditing = false);
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


