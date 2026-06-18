import 'dart:ui_web' as ui;
import 'package:flutter/material.dart';
import 'dart:html' as html;

class MjpegView extends StatelessWidget {
  final String url;

  const MjpegView({
    super.key,
    required this.url,
  });

  @override
  Widget build(BuildContext context) {
    // WHY viewType giờ phụ thuộc vào `url` thay vì hardcode 'mjpeg-view':
    // registerViewFactory ném exception nếu gọi 2 lần với cùng 1 viewType
    // ("There is already a platformViewFactory registered for viewType ...").
    // Trước đây chỉ có 1 MjpegView sống tại 1 thời điểm (Home -> push Detail
    // -> Home bị dispose) nên chưa lộ bug. Nhưng giờ thêm CameraDetailScreen,
    // nếu mai mốt mày đổi qua Hero animation (build cả 2 màn cùng lúc trong
    // lúc transition) hoặc thêm preview thumbnail, code cũ sẽ crash ngay.
    // Đặt theo url là đủ unique vì mỗi camera có 1 endpoint riêng
    // (http://.../video, http://.../video2, ...).
    final viewType = 'mjpeg-view-${url.hashCode}';

    ui.platformViewRegistry.registerViewFactory(
      viewType,
      (int viewId) {
        final img = html.ImageElement()
          ..src = url
          ..style.width = '100%'
          ..style.height = '100%'
          ..style.objectFit = 'cover';

        return img;
      },
    );

    return HtmlElementView(
      viewType: viewType,
    );
  }
}