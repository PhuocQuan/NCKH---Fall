import 'package:flutter/material.dart';

class AppColors {
  // Gradient splash: xanh đậm dưới đáy -> xanh nhạt hơn ở giữa
  static const splashGradient = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [Color(0xFF3B6FE0), Color(0xFF2546B8)],
  );

  static const primary = Color(0xFF3D5CE6);   // màu nút Log In / icon shield
  static const background = Color(0xFFF4F6FB); // nền màn login
  static const textDark = Color(0xFF1A1F36);
  static const textGrey = Color(0xFF8A93A6);
  static const inputBorder = Color(0xFFE2E5EE);
}