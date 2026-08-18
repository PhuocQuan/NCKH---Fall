// lib/widgets/status_pill.dart
// Status badge pill — giống web CSS .pill classes

import 'package:flutter/material.dart';

enum PillColor { green, amber, red, blue, grey }

class StatusPill extends StatelessWidget {
  final String text;
  final PillColor color;
  final bool small;

  const StatusPill({super.key, required this.text, this.color = PillColor.grey, this.small = false});

  factory StatusPill.fromStatus(String status, {bool small = false}) {
    PillColor c;
    final s = status.toLowerCase();
    if (s == 'online' || s == 'đang hoạt động' || s == 'hoạt động' || s == 'normal' || s == 'walking' || s == 'sitting') {
      c = PillColor.green;
    } else if (s == 'maintenance' || s == 'bảo trì' || s == 'đang xử lý' || s == 'warning') {
      c = PillColor.amber;
    } else if (s == 'offline' || s == 'fallen' || s == 'alert' || s == 'chưa xử lý' || s == 'khẩn cấp') {
      c = PillColor.red;
    } else if (s == 'lying' || s == 'possible_fall') {
      c = PillColor.amber;
    } else {
      c = PillColor.grey;
    }
    return StatusPill(text: status, color: c, small: small);
  }

  @override
  Widget build(BuildContext context) {
    final (bg, fg) = switch (color) {
      PillColor.green => (const Color(0xFFDCFCE7), const Color(0xFF16A34A)),
      PillColor.amber => (const Color(0xFFFEF9C3), const Color(0xFFCA8A04)),
      PillColor.red => (const Color(0xFFFEE2E2), const Color(0xFFDC2626)),
      PillColor.blue => (const Color(0xFFEFF6FF), const Color(0xFF2563EB)),
      PillColor.grey => (const Color(0xFFF1F5F9), const Color(0xFF64748B)),
    };

    return Container(
      padding: EdgeInsets.symmetric(horizontal: small ? 6 : 8, vertical: small ? 2 : 3),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(100)),
      child: Text(
        text,
        style: TextStyle(
          color: fg,
          fontSize: small ? 10 : 12,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.2,
        ),
      ),
    );
  }
}
