// File: lib/main.dart
// Entry point — FallGuard AI Flutter Client

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'core/auth_service.dart';
import 'core/app_state_service.dart';
import 'core/navigator_key.dart';
import 'screens/login_screen.dart';
import 'screens/home_screen.dart';

/// Hàm main: Chạy đầu tiên khi mở App.
void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Lock to portrait mode
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  // Init auth from saved session
  await AuthService().init();

  // Load local cached state
  await AppStateService().loadFromLocal();

  runApp(const FallGuardApp());
}

/// Widget gốc của toàn bộ ứng dụng. Quản lý Theme và Routing (chuyển trang).
class FallGuardApp extends StatelessWidget {
  const FallGuardApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      navigatorKey: globalNavigatorKey,
      title: 'FallGuard AI',
      debugShowCheckedModeBanner: false,
      theme: _buildTheme(),
      initialRoute: AuthService().isLoggedIn ? '/home' : '/login',
      routes: {
        '/login': (_) => const LoginScreen(),
        '/home': (_) => const HomeScreen(),
      },
    );
  }

  ThemeData _buildTheme() {
    return ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xFF4f46e5),
        brightness: Brightness.light,
        surface: const Color(0xFFF1F5F9),
      ),
      fontFamily: 'Roboto',
      scaffoldBackgroundColor: const Color(0xFFF1F5F9),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.white,
        foregroundColor: Color(0xFF0f172a),
        elevation: 0,
        surfaceTintColor: Colors.transparent,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: const Color(0xFFF8FAFC),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: Color(0xFFE2E8F0)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: Color(0xFFE2E8F0)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: Color(0xFF4f46e5), width: 2),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
      ),
      cardTheme: CardThemeData(
        color: Colors.white,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: const BorderSide(color: Color(0xFFE2E8F0)),
        ),
      ),
    );
  }
}