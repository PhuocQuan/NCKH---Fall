// lib/core/app_state_service.dart
// Quản lý state in-memory: cameras, alerts, contacts, notifications, profile
// Sync lên/xuống backend tự động

import 'dart:async';
import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import 'models.dart';
import 'api_client.dart';
import 'auth_service.dart';

class AppStateService {
  static final AppStateService _instance = AppStateService._internal();
  factory AppStateService() => _instance;
  AppStateService._internal();

  // In-memory state
  List<CameraModel> cameras = [];
  List<AlertModel> alerts = [];
  List<EmergencyContact> emergencyContacts = [];
  List<AppNotification> notifications = [];
  MonitoredProfile? monitoredProfile;
  UserModel? currentUser;
  bool isBackendOnline = false;

  // Default demo data (fallback khi offline)
  static const _defaultCameras = [
    {'id': 'CAM-001', 'name': 'Camera phòng 101', 'area': 'Khu A', 'state': 'normal', 'status': 'online', 'fps': 30, 'resolution': '1920x1080', 'threshold': 78},
    {'id': 'CAM-002', 'name': 'Camera hành lang A', 'area': 'Khu A', 'state': 'walking', 'status': 'online', 'fps': 25, 'resolution': '1280x720', 'threshold': 76},
    {'id': 'CAM-003', 'name': 'Camera phòng 203', 'area': 'Khu B', 'state': 'fallen', 'status': 'online', 'fps': 30, 'resolution': '1920x1080', 'threshold': 82},
    {'id': 'CAM-004', 'name': 'Camera phòng phục hồi', 'area': 'Khu C', 'state': 'sitting', 'status': 'maintenance', 'fps': 20, 'resolution': '1280x720', 'threshold': 74},
    {'id': 'CAM-005', 'name': 'Camera phòng 305', 'area': 'Khu C', 'state': 'normal', 'status': 'offline', 'fps': 0, 'resolution': '1920x1080', 'threshold': 80},
  ];

  static const _defaultAlerts = [
    {'id': 'AL-20260615-001', 'time': '15/06/2026 16:22', 'camera': 'CAM-003', 'person': 'Nguyễn Văn Minh', 'confidence': 94, 'status': 'Chưa xử lý', 'level': 'Khẩn cấp', 'media': 'Ảnh + video 12s'},
    {'id': 'AL-20260615-002', 'time': '15/06/2026 14:10', 'camera': 'CAM-001', 'person': 'Lê Thị Hoa', 'confidence': 81, 'status': 'Đang xử lý', 'level': 'Cao', 'media': 'Ảnh'},
    {'id': 'AL-20260615-003', 'time': '15/06/2026 09:40', 'camera': 'CAM-002', 'person': 'Trần Văn An', 'confidence': 68, 'status': 'Báo động giả', 'level': 'Trung bình', 'media': 'Video 8s'},
  ];

  static const _defaultNotifications = [
    {'id': 'NT-001', 'type': 'fall', 'title': 'Cảnh báo ngã khẩn cấp', 'content': 'Phát hiện té ngã tại Camera phòng 203 lúc 16:22 ngày 15/06/2026.', 'time': '15/06/2026 16:22', 'read': false},
    {'id': 'NT-002', 'type': 'disconnect', 'title': 'Camera mất kết nối', 'content': 'Camera phòng 305 đã mất kết nối lúc 13:00 ngày 15/06/2026.', 'time': '15/06/2026 13:00', 'read': true},
    {'id': 'NT-003', 'type': 'maintenance', 'title': 'Bảo trì hệ thống', 'content': 'Hệ thống FallGuard AI sẽ tiến hành bảo trì từ 01:00 đến 03:00 ngày 20/06/2026.', 'time': '14/06/2026 18:00', 'read': true},
  ];

  Timer? _syncTimer;

  // Callbacks để notify UI
  VoidCallback? onStateChanged;

  // ─── Local persistence ───────────────────────────────────────────────────────

  Future<void> loadFromLocal() async {
    final prefs = await SharedPreferences.getInstance();

    // Cameras
    final camerasJson = prefs.getString('fg_cameras');
    if (camerasJson != null) {
      cameras = (jsonDecode(camerasJson) as List).map((e) => CameraModel.fromJson(e)).toList();
    } else {
      cameras = _defaultCameras.map((e) => CameraModel.fromJson(Map<String, dynamic>.from(e))).toList();
    }

    // Alerts
    final alertsJson = prefs.getString('fg_alerts');
    if (alertsJson != null) {
      alerts = (jsonDecode(alertsJson) as List).map((e) => AlertModel.fromJson(e)).toList();
    } else {
      alerts = _defaultAlerts.map((e) => AlertModel.fromJson(Map<String, dynamic>.from(e))).toList();
    }

    // Contacts
    final contactsJson = prefs.getString('fg_emergency_contacts');
    if (contactsJson != null) {
      emergencyContacts = (jsonDecode(contactsJson) as List).map((e) => EmergencyContact.fromJson(e)).toList();
    } else {
      emergencyContacts = [
        const EmergencyContact(name: 'Lê Thị Hoa', relationship: 'Con gái', phone: '0987654321', email: 'hoa@nckh.vn'),
      ];
    }

    // Notifications
    final notifJson = prefs.getString('fg_user_notifications');
    if (notifJson != null) {
      notifications = (jsonDecode(notifJson) as List).map((e) => AppNotification.fromJson(e)).toList();
    } else {
      notifications = _defaultNotifications.map((e) => AppNotification.fromJson(Map<String, dynamic>.from(e))).toList();
    }

    // Monitored profile
    final profileJson = prefs.getString('fg_monitored_profile');
    if (profileJson != null) {
      monitoredProfile = MonitoredProfile.fromJson(jsonDecode(profileJson));
    } else {
      monitoredProfile = const MonitoredProfile(
        name: 'Nguyễn Văn Minh',
        age: 72,
        gender: 'Nam',
        address: 'Phòng 203, Khu B',
        emergencyContact: 'Bảo (Con trai) - 0912345678',
      );
    }
  }

  Future<void> saveToLocal() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('fg_cameras', jsonEncode(cameras.map((e) => e.toJson()).toList()));
    await prefs.setString('fg_alerts', jsonEncode(alerts.map((e) => e.toJson()).toList()));
    await prefs.setString('fg_emergency_contacts', jsonEncode(emergencyContacts.map((e) => e.toJson()).toList()));
    await prefs.setString('fg_user_notifications', jsonEncode(notifications.map((e) => e.toJson()).toList()));
    if (monitoredProfile != null) {
      await prefs.setString('fg_monitored_profile', jsonEncode(monitoredProfile!.toJson()));
    }
  }

  // ─── Backend sync ─────────────────────────────────────────────────────────

  Future<void> syncFromBackend() async {
    if (!AuthService().isLoggedIn) return;
    try {
      final data = await ApiClient().getAppState();

      bool changed = false;

      if (data['monitored_profile_json'] != null) {
        final remote = MonitoredProfile.fromJson(jsonDecode(data['monitored_profile_json']));
        if (jsonEncode(remote.toJson()) != jsonEncode(monitoredProfile?.toJson())) {
          monitoredProfile = remote;
          changed = true;
        }
      }
      if (data['emergency_contacts_json'] != null) {
        final remote = (jsonDecode(data['emergency_contacts_json']) as List)
            .map((e) => EmergencyContact.fromJson(e))
            .toList();
        if (jsonEncode(remote.map((e) => e.toJson()).toList()) != jsonEncode(emergencyContacts.map((e) => e.toJson()).toList())) {
          emergencyContacts = remote;
          changed = true;
        }
      }
      if (data['user_notifications_json'] != null) {
        final remote = (jsonDecode(data['user_notifications_json']) as List)
            .map((e) => AppNotification.fromJson(e))
            .toList();
        if (jsonEncode(remote.map((e) => e.toJson()).toList()) != jsonEncode(notifications.map((e) => e.toJson()).toList())) {
          notifications = remote;
          changed = true;
        }
      }

      // Also fetch cameras and alerts from API
      final remoteCameras = await ApiClient().getCameras();
      if (remoteCameras.isNotEmpty) {
        cameras = remoteCameras.map((e) => CameraModel.fromJson(e)).toList();
        changed = true;
      }

      final remoteAlerts = await ApiClient().getAlerts();
      if (remoteAlerts.isNotEmpty) {
        alerts = remoteAlerts.map((e) => AlertModel.fromJson(e)).toList();
        changed = true;
      }

      if (changed) {
        await saveToLocal();
        onStateChanged?.call();
      }
    } catch (e) {
      // Silent fail — keep local data
    }
  }

  Future<void> pushToBackend() async {
    if (!AuthService().isLoggedIn) return;
    try {
      await ApiClient().postAppState({
        'monitored_profile_json': jsonEncode(monitoredProfile?.toJson()),
        'emergency_contacts_json': jsonEncode(emergencyContacts.map((e) => e.toJson()).toList()),
        'user_notifications_json': jsonEncode(notifications.map((e) => e.toJson()).toList()),
      });
    } catch (_) {}
  }

  void startAutoSync() {
    _syncTimer?.cancel();
    _syncTimer = Timer.periodic(const Duration(seconds: 30), (_) async {
      final online = await AuthService().checkBackendOnline();
      isBackendOnline = online;
      if (online) await syncFromBackend();
    });
  }

  void stopAutoSync() {
    _syncTimer?.cancel();
    _syncTimer = null;
  }

  // ─── Helper methods ───────────────────────────────────────────────────────

  List<CameraModel> getVisibleCameras() {
    final assigned = currentUser?.assignedCameras ?? [];
    if (assigned.isEmpty) return cameras;
    return cameras.where((c) => assigned.contains(c.id)).toList();
  }

  List<String> getUniqueAreas() {
    return getVisibleCameras().map((c) => c.area).toSet().toList();
  }

  List<AlertModel> getVisibleAlerts() {
    final visibleIds = getVisibleCameras().map((c) => c.id).toSet();
    return alerts.where((a) => visibleIds.contains(a.camera)).toList();
  }

  int get unreadNotificationsCount => notifications.where((n) => !n.read).length;
}

typedef VoidCallback = void Function();
