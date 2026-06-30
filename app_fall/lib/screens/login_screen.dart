// lib/screens/login_screen.dart
// Màn hình đăng nhập — thiết kế theo src/web/mobile/index.html

import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import '../core/api_client.dart';
import '../core/auth_service.dart';
import '../core/app_state_service.dart';
import '../core/models.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _usernameCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController(text: 'nckh2025');
  final _serverUrlCtrl = TextEditingController();

  bool _obscurePassword = true;
  bool _rememberMe = true;
  bool _loading = false;
  bool _showServerConfig = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _serverUrlCtrl.text = AuthService().serverUrl;
  }

  @override
  void dispose() {
    _usernameCtrl.dispose();
    _passwordCtrl.dispose();
    _serverUrlCtrl.dispose();
    super.dispose();
  }

  String _normalizeUsername(String input) {
    final lower = input.trim().toLowerCase();
    if (lower.contains('@')) return lower;
    switch (lower) {
      case 'admin': return 'admin@nckh.vn';
      case 'bao': case 'manager': return 'bao@nckh.vn';
      case 'nurse': return 'nurse@nckh.vn';
      case 'family': return 'family@nckh.vn';
      case 'guest': return 'guest@nckh.vn';
      default: return '$lower@nckh.vn';
    }
  }

  Future<void> _handleLogin() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _loading = true;
      _errorMessage = null;
    });

    try {
      // Update server URL if changed
      final serverUrl = _serverUrlCtrl.text.trim().isNotEmpty
          ? _serverUrlCtrl.text.trim()
          : (kIsWeb ? 'http://127.0.0.1:8000' : 'https://repairs-outlined-scheduling-knowing.trycloudflare.com');
      await AuthService().setServerUrl(serverUrl);

      final username = _normalizeUsername(_usernameCtrl.text);
      final password = _passwordCtrl.text;

      // Check health
      final isOnline = await AuthService().checkBackendOnline();
      AppStateService().isBackendOnline = isOnline;

      String token = '';

      if (isOnline) {
        // Authenticate with backend
        final result = await ApiClient().login(username, password);
        token = result['token'] ?? '';
      } else {
        // Offline fallback — local check
        if (password != 'nckh2025') {
          throw ApiException('Server ngoại tuyến. Mật khẩu offline mặc định là nckh2025.');
        }
        token = 'offline_token';
      }

      await AuthService().saveSession(
        token: token,
        email: username,
        serverUrl: serverUrl,
      );

      // Load initial state
      await AppStateService().loadFromLocal();
      AppStateService().currentUser = UserModel(
        email: username,
        name: username.split('@').first,
        role: 'Khachhang',
        assignedCameras: const [],
      );

      if (isOnline) {
        // Fetch user info from backend
        try {
          final users = await ApiClient().getUsers();
          final found = users.cast<Map<String, dynamic>>().firstWhere(
            (u) => (u['email'] ?? '').toString().toLowerCase() == username.toLowerCase(),
            orElse: () => <String, dynamic>{},
          );
          if (found.isNotEmpty) {
            final userRole = (found['role'] ?? '').toString().toLowerCase();
            if (userRole == 'admin') {
              await AuthService().clearSession();
              throw const ApiException('Tài khoản Admin không được hỗ trợ trên ứng dụng di động.');
            }
            AppStateService().currentUser = UserModel.fromJson(found);
          }
        } catch (e) {
          if (e is ApiException) rethrow;
        }
        await AppStateService().syncFromBackend();
      }

      if (!mounted) return;
      Navigator.of(context).pushReplacementNamed('/home');
    } on ApiException catch (e) {
      setState(() => _errorMessage = e.message);
    } catch (e) {
      setState(() => _errorMessage = 'Lỗi kết nối. Kiểm tra địa chỉ server.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0f172a),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
            child: Form(
              key: _formKey,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // ── Brand ──
                  _buildBrand(),
                  const SizedBox(height: 36),

                  // ── Card ──
                  Container(
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(24),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withAlpha(25),
                          blurRadius: 32,
                          offset: const Offset(0, 12),
                        ),
                      ],
                    ),
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Email field
                        _buildLabel('Email đăng nhập'),
                        const SizedBox(height: 6),
                        _buildTextField(
                          controller: _usernameCtrl,
                          hint: 'Ví dụ: admin@nckh.vn',
                          keyboardType: TextInputType.emailAddress,
                          validator: (v) => (v == null || v.trim().isEmpty) ? 'Vui lòng nhập email' : null,
                        ),
                        const SizedBox(height: 16),

                        // Password field
                        _buildLabel('Mật khẩu'),
                        const SizedBox(height: 6),
                        TextFormField(
                          controller: _passwordCtrl,
                          obscureText: _obscurePassword,
                          decoration: InputDecoration(
                            hintText: 'Nhập mật khẩu',
                            hintStyle: TextStyle(color: Colors.grey.shade400, fontSize: 14),
                            filled: true,
                            fillColor: const Color(0xFFF8FAFC),
                            contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(14),
                              borderSide: const BorderSide(color: Color(0xFFE2E8F0)),
                            ),
                            enabledBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(14),
                              borderSide: const BorderSide(color: Color(0xFFE2E8F0)),
                            ),
                            focusedBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(14),
                              borderSide: const BorderSide(color: Color(0xFF4f46e5), width: 2),
                            ),
                            suffixIcon: IconButton(
                              icon: Icon(
                                _obscurePassword ? Icons.visibility_off : Icons.visibility,
                                color: Colors.grey.shade500,
                                size: 20,
                              ),
                              onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
                            ),
                          ),
                          validator: (v) => (v == null || v.isEmpty) ? 'Vui lòng nhập mật khẩu' : null,
                        ),
                        const SizedBox(height: 14),

                        // Remember me + Forgot password
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Row(
                              children: [
                                SizedBox(
                                  width: 20,
                                  height: 20,
                                  child: Checkbox(
                                    value: _rememberMe,
                                    onChanged: (v) => setState(() => _rememberMe = v ?? true),
                                    activeColor: const Color(0xFF4f46e5),
                                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
                                  ),
                                ),
                                const SizedBox(width: 6),
                                const Text('Ghi nhớ', style: TextStyle(fontSize: 13, color: Color(0xFF64748b))),
                              ],
                            ),
                            GestureDetector(
                              onTap: () {
                                showDialog(
                                  context: context,
                                  builder: (_) => AlertDialog(
                                    title: const Text('Quên mật khẩu'),
                                    content: const Text(
                                        'Vui lòng liên hệ quản trị viên qua email admin@nckh.vn để được hỗ trợ cấp lại mật khẩu.'),
                                    actions: [
                                      TextButton(
                                        onPressed: () => Navigator.pop(context),
                                        child: const Text('Đóng'),
                                      ),
                                    ],
                                  ),
                                );
                              },
                              child: const Text(
                                'Quên mật khẩu',
                                style: TextStyle(fontSize: 13, color: Color(0xFF94a3b8), decoration: TextDecoration.underline),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 20),

                        // Error message
                        if (_errorMessage != null) ...[
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: const Color(0xFFFEF2F2),
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: const Color(0xFFFECACA)),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.error_outline, color: Color(0xFFEF4444), size: 18),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    _errorMessage!,
                                    style: const TextStyle(color: Color(0xFFDC2626), fontSize: 13),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 14),
                        ],

                        // Login button
                        SizedBox(
                          width: double.infinity,
                          height: 52,
                          child: ElevatedButton(
                            onPressed: _loading ? null : _handleLogin,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: const Color(0xFF4f46e5),
                              foregroundColor: Colors.white,
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                              elevation: 0,
                            ),
                            child: _loading
                                ? const SizedBox(
                                    width: 22,
                                    height: 22,
                                    child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2.5),
                                  )
                                : const Text('Đăng nhập', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                          ),
                        ),
                        const SizedBox(height: 16),

                        // Server config toggle
                        GestureDetector(
                          onTap: () => setState(() => _showServerConfig = !_showServerConfig),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(
                                _showServerConfig ? Icons.settings : Icons.settings_outlined,
                                size: 16,
                                color: Colors.grey.shade500,
                              ),
                              const SizedBox(width: 4),
                              Text(
                                'Cấu hình máy chủ',
                                style: TextStyle(fontSize: 12, color: Colors.grey.shade500),
                              ),
                            ],
                          ),
                        ),

                        if (_showServerConfig) ...[
                          const SizedBox(height: 12),
                          _buildLabel('Server URL'),
                          const SizedBox(height: 6),
                          _buildTextField(
                            controller: _serverUrlCtrl,
                            hint: kIsWeb ? 'http://127.0.0.1:8000' : 'https://repairs-outlined-scheduling-knowing.trycloudflare.com',
                            keyboardType: TextInputType.url,
                          ),
                          const SizedBox(height: 6),
                          const Text(
                            '• Web (Chrome): http://127.0.0.1:8000\n• Emulator Android: https://repairs-outlined-scheduling-knowing.trycloudflare.com\n• Thiết bị thật: https://repairs-outlined-scheduling-knowing.trycloudflare.com',
                            style: TextStyle(fontSize: 11, color: Color(0xFF94a3b8), height: 1.5),
                          ),
                        ],
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),
                  const Text(
                    'Giao diện tối ưu cho thiết bị di động.',
                    style: TextStyle(fontSize: 11, color: Color(0xFF475569)),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildBrand() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Container(
          width: 56,
          height: 56,
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF4f46e5), Color(0xFF7c3aed)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF4f46e5).withAlpha(100),
                blurRadius: 16,
                offset: const Offset(0, 6),
              ),
            ],
          ),
          child: const Center(
            child: Text('FG', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w900, fontSize: 22, letterSpacing: -0.5)),
          ),
        ),
        const SizedBox(width: 14),
        const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'FallGuard AI',
              style: TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.w900, letterSpacing: -0.5),
            ),
            Text(
              'Hệ thống phát hiện té ngã',
              style: TextStyle(color: Color(0xFF94a3b8), fontSize: 13),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildLabel(String text) {
    return Text(
      text,
      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Color(0xFF374151)),
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String hint,
    TextInputType? keyboardType,
    String? Function(String?)? validator,
  }) {
    return TextFormField(
      controller: controller,
      keyboardType: keyboardType,
      style: const TextStyle(fontSize: 14, color: Color(0xFF0f172a)),
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: TextStyle(color: Colors.grey.shade400, fontSize: 14),
        filled: true,
        fillColor: const Color(0xFFF8FAFC),
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: Color(0xFFE2E8F0)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: Color(0xFFE2E8F0)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: Color(0xFF4f46e5), width: 2),
        ),
      ),
      validator: validator,
    );
  }
}
