// lib/core/api_client.dart
// HTTP client wrapper — tự gắn auth header, cấu hình base URL

import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;


class ApiClient {
  static final ApiClient _instance = ApiClient._internal();
  factory ApiClient() => _instance;
  ApiClient._internal();

  String baseUrl = 'https://repairs-outlined-scheduling-knowing.trycloudflare.com'; // Sử dụng Cloudflare Tunnel
  String? _token;

  void Function()? onUnauthorized;

  void setToken(String? token) => _token = token;
  void setBaseUrl(String url) => baseUrl = url.trimRight().replaceAll(RegExp(r'/$'), '');

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': 'true',
        if (_token != null && _token!.isNotEmpty)
          'Authorization': 'Bearer $_token',
      };

  Uri _uri(String path) => Uri.parse('$baseUrl$path');

  void _check401(http.Response res) {
    if (res.statusCode == 401) {
      onUnauthorized?.call();
      throw const ApiException('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
    }
  }

  // GET /api/health
  Future<Map<String, dynamic>> healthCheck() async {
    try {
      final res = await http.get(_uri('/api/health'), headers: _headers).timeout(const Duration(seconds: 120));
      if (res.statusCode == 200) {
        return jsonDecode(res.body) as Map<String, dynamic>;
      }
      return {'ok': false, 'db_connected': false};
    } catch (_) {
      return {'ok': false, 'db_connected': false};
    }
  }

  // POST /api/auth/login
  Future<Map<String, dynamic>> login(String username, String password) async {
    final res = await http
        .post(
          _uri('/api/auth/login'),
          headers: _headers,
          body: jsonEncode({'username': username, 'password': password}),
        )
        .timeout(const Duration(seconds: 120));
    final body = jsonDecode(res.body) as Map<String, dynamic>;
    if (res.statusCode != 200) {
      throw ApiException(body['detail'] ?? 'Đăng nhập thất bại.');
    }
    return body;
  }

  // POST /api/auth/logout
  Future<void> logout() async {
    try {
      final res = await http
          .post(_uri('/api/auth/logout'), headers: _headers)
          .timeout(const Duration(seconds: 120));
      _check401(res);
    } catch (_) {}
  }

  // GET /api/appstate
  Future<Map<String, dynamic>> getAppState() async {
    final res = await http
        .get(_uri('/api/appstate'), headers: _headers)
        .timeout(const Duration(seconds: 120));
    _check401(res);
    if (res.statusCode == 200) return jsonDecode(res.body) as Map<String, dynamic>;
    throw ApiException('Không lấy được appstate (${res.statusCode})');
  }

  // POST /api/appstate
  Future<void> postAppState(Map<String, dynamic> payload) async {
    final res = await http
        .post(
          _uri('/api/appstate'),
          headers: _headers,
          body: jsonEncode(payload),
        )
        .timeout(const Duration(seconds: 120));
    _check401(res);
  }

  // GET /api/alerts
  Future<List<dynamic>> getAlerts() async {
    try {
      final res = await http
          .get(_uri('/api/alerts'), headers: _headers)
          .timeout(const Duration(seconds: 120));
      _check401(res);
      if (res.statusCode == 200) {
        final body = jsonDecode(res.body) as Map<String, dynamic>;
        return body['alerts'] as List<dynamic>;
      }
    } catch (_) {}
    return [];
  }

  // GET /api/cameras
  Future<List<dynamic>> getCameras() async {
    try {
      final res = await http
          .get(_uri('/api/cameras'), headers: _headers)
          .timeout(const Duration(seconds: 120));
      _check401(res);
      if (res.statusCode == 200) return jsonDecode(res.body) as List<dynamic>;
    } catch (_) {}
    return [];
  }

  // GET /api/users (to get current user info)
  Future<List<dynamic>> getUsers() async {
    try {
      final res = await http
          .get(_uri('/api/users'), headers: _headers)
          .timeout(const Duration(seconds: 120));
      _check401(res);
      if (res.statusCode == 200) return jsonDecode(res.body) as List<dynamic>;
    } catch (_) {}
    return [];
  }

  // PUT /api/users/{email}
  Future<void> updateUser(String email, Map<String, dynamic> data) async {
    final res = await http
        .put(
          _uri('/api/users/${Uri.encodeComponent(email)}'),
          headers: _headers,
          body: jsonEncode(data),
        )
        .timeout(const Duration(seconds: 120));
    _check401(res);
    if (res.statusCode != 200) {
      final body = jsonDecode(res.body) as Map<String, dynamic>;
      throw ApiException(body['detail'] ?? 'Không thể cập nhật thông tin.');
    }
  }

  // POST /api/alerts/delete-multiple
  Future<void> deleteAlerts({List<String>? ids, bool deleteAll = false}) async {
    final payload = deleteAll ? {'delete_all': true} : {'ids': ids, 'delete_all': false};
    final res = await http
        .post(
          _uri('/api/alerts/delete-multiple'),
          headers: _headers,
          body: jsonEncode(payload),
        )
        .timeout(const Duration(seconds: 120));
    _check401(res);
    if (res.statusCode != 200) {
      final body = jsonDecode(res.body) as Map<String, dynamic>;
      throw ApiException(body['detail'] ?? 'Lỗi khi xóa cảnh báo.');
    }
  }

  // POST /api/camera/test-snapshot (Send manual SOS alert from mobile)
  Future<void> sendEmergencySOS(String contactName) async {
    try {
      final res = await http.post(
        _uri('/api/camera/test-snapshot'),
        headers: _headers,
        body: jsonEncode({'camera_id': 'SOS-$contactName'}),
      ).timeout(const Duration(seconds: 120));
      _check401(res);
    } catch (_) {}
  }

  // POST /api/control/start
  Future<void> startCamera(String source, String cameraId) async {
    try {
      final res = await http.post(
        _uri('/api/control/start'),
        headers: _headers,
        body: jsonEncode({'source': source, 'camera_id': cameraId}),
      ).timeout(const Duration(seconds: 5));
      _check401(res);
    } catch (_) {}
  }

  // POST /api/control/stop
  Future<void> stopCamera() async {
    try {
      final res = await http.post(
        _uri('/api/control/stop'),
        headers: _headers,
      ).timeout(const Duration(seconds: 5));
      _check401(res);
    } catch (_) {}
  }

  // MJPEG stream URL
  String mjpegUrl() {
    final token = _token ?? '';
    final ts = DateTime.now().millisecondsSinceEpoch;
    return '$baseUrl/api/camera/stream.mjpg?token=${Uri.encodeComponent(token)}&ts=$ts';
  }

  // Snapshot URL (for Web polling fallback)
  String snapshotUrl() {
    final token = _token ?? '';
    final ts = DateTime.now().millisecondsSinceEpoch;
    return '$baseUrl/api/camera/snapshot?token=${Uri.encodeComponent(token)}&ts=$ts';
  }

  // Fetch snapshot bytes directly using authorized client
  Future<Uint8List?> getSnapshotBytes() async {
    try {
      final res = await http.get(
        _uri('/api/camera/snapshot'),
        headers: _headers,
      ).timeout(const Duration(seconds: 3));
      _check401(res);
      if (res.statusCode == 200) return res.bodyBytes;
      throw Exception('HTTP ${res.statusCode}');
    } catch (e) {
      rethrow;
    }
  }

  // Media URL (for alert images/videos)
  String mediaUrl(String alertId, {bool isVideo = false}) {
    return '$baseUrl/media/$alertId.${isVideo ? 'mp4' : 'jpg'}';
  }
}

class ApiException implements Exception {
  final String message;
  const ApiException(this.message);

  @override
  String toString() => message;
}
