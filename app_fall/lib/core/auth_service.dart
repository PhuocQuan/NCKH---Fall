// lib/core/auth_service.dart
// Quản lý token, server URL, session trong SharedPreferences

import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'api_client.dart';
import 'navigator_key.dart';

class AuthService {
  static final AuthService _instance = AuthService._internal();
  factory AuthService() => _instance;
  AuthService._internal();

  static const _keyToken = 'nckh_auth_token';
  static const _keyEmail = 'nckh_current_user_email';
  static const _keyServerUrl = 'nckh_server_url';

  String? _token;
  String? _email;
  String _serverUrl = 'https://nckh-fall.onrender.com';

  String? get token => _token;
  String? get email => _email;
  String get serverUrl => _serverUrl;

  bool get isLoggedIn => _token != null && _token!.isNotEmpty;

  /// Khởi tạo từ SharedPreferences khi app start
  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString(_keyToken);
    _email = prefs.getString(_keyEmail);
    _serverUrl = prefs.getString(_keyServerUrl) ?? 'https://nckh-fall.onrender.com';
    
    // Fix cho bộ nhớ đệm: Nếu lỡ lưu URL local từ trước, hãy ép về lại Server Render
    if (_serverUrl == 'http://127.0.0.1:8000') {
      _serverUrl = 'https://nckh-fall.onrender.com';
      await prefs.setString(_keyServerUrl, _serverUrl);
    }

    // Sync vào ApiClient
    ApiClient().setBaseUrl(_serverUrl);
    ApiClient().setToken(_token);
    ApiClient().onUnauthorized = () {
      clearSession();
      globalNavigatorKey.currentState?.pushNamedAndRemoveUntil('/login', (route) => false);
    };
  }

  /// Lưu session sau khi đăng nhập thành công
  Future<void> saveSession({
    required String token,
    required String email,
    String? serverUrl,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    _token = token;
    _email = email;
    if (serverUrl != null) _serverUrl = serverUrl;

    await prefs.setString(_keyToken, token);
    await prefs.setString(_keyEmail, email);
    await prefs.setString(_keyServerUrl, _serverUrl);

    ApiClient().setToken(token);
    ApiClient().setBaseUrl(_serverUrl);
  }

  /// Cập nhật server URL (có thể gọi từ login screen)
  Future<void> setServerUrl(String url) async {
    _serverUrl = url;
    ApiClient().setBaseUrl(url);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyServerUrl, url);
  }

  /// Xóa toàn bộ session (logout)
  Future<void> clearSession() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_keyToken);
    await prefs.remove(_keyEmail);
    _token = null;
    _email = null;
    ApiClient().setToken(null);
  }

  /// Kiểm tra server có online không
  Future<bool> checkBackendOnline() async {
    final result = await ApiClient().healthCheck();
    return result['ok'] == true;
  }
}
