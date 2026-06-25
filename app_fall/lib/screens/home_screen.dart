import 'package:flutter/material.dart';
import '../theme/app_colors.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentTab = 1; // Cameras tab active theo ảnh mẫu

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        automaticallyImplyLeading: false,
        title: const Text(
          'Cameras',
          style: TextStyle(
            color: AppColors.textDark,
            fontWeight: FontWeight.bold,
            fontSize: 22,
          ),
        ),
      ),
      body: const SafeArea(
        child: Padding(
          padding: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: _CameraCard(
            label: 'CAM-01 · Bedroom · Room 101',
            statusText: 'Normal',
            statusColor: Colors.green,
          ),
        ),
      ),
      bottomNavigationBar: _buildBottomNav(),
    );
  }

  Widget _buildBottomNav() {
    return BottomNavigationBar(
      currentIndex: _currentTab,
      onTap: (index) => setState(() => _currentTab = index),
      type: BottomNavigationBarType.fixed,
      selectedItemColor: AppColors.primary,
      unselectedItemColor: AppColors.textGrey,
      showUnselectedLabels: true,
      items: const [
        BottomNavigationBarItem(icon: Icon(Icons.home_outlined), label: 'Home'),
        BottomNavigationBarItem(icon: Icon(Icons.videocam_outlined), label: 'Cameras'),
        BottomNavigationBarItem(icon: Icon(Icons.notifications_outlined), label: 'Alerts'),
        BottomNavigationBarItem(icon: Icon(Icons.person_outline), label: 'Profile'),
      ],
    );
  }
}

class _CameraCard extends StatelessWidget {
  final String label;
  final String statusText;
  final Color statusColor;

  const _CameraCard({
    required this.label,
    required this.statusText,
    required this.statusColor,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildVideoArea(),
          _buildFooterLabel(),
        ],
      ),
    );
  }

  Widget _buildVideoArea() {
    return AspectRatio(
      aspectRatio: 16 / 9,
      child: Stack(
        children: [
          // Placeholder cho video feed — sau này thay bằng Image stream từ server
          ClipRRect(
            borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
            child: Container(
              width: double.infinity,
              height: double.infinity,
              color: const Color(0xFF2A2E3A),
              child: const Center(
                child: Icon(Icons.videocam_off_outlined, color: Colors.white38, size: 40),
              ),
            ),
          ),

          // Badge LIVE góc trên trái
          Positioned(
            top: 12,
            left: 12,
            child: _Badge(
              text: 'LIVE',
              backgroundColor: Colors.red,
              textColor: Colors.white,
              dotColor: Colors.white,
            ),
          ),

          // Badge trạng thái góc trên phải
          Positioned(
            top: 12,
            right: 12,
            child: _Badge(
              text: statusText,
              backgroundColor: Colors.black.withOpacity(0.45),
              textColor: Colors.white,
              dotColor: statusColor,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFooterLabel() {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: const BoxDecoration(
                  color: Colors.green,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                label,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textDark,
                ),
              ),
            ],
          ),
          const Icon(Icons.chevron_right, color: AppColors.textGrey, size: 20),
        ],
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  final String text;
  final Color backgroundColor;
  final Color textColor;
  final Color dotColor;

  const _Badge({
    required this.text,
    required this.backgroundColor,
    required this.textColor,
    required this.dotColor,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: backgroundColor,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(color: dotColor, shape: BoxShape.circle),
          ),
          const SizedBox(width: 4),
          Text(
            text,
            style: TextStyle(
              color: textColor,
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}