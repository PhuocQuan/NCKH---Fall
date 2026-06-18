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
    ui.platformViewRegistry.registerViewFactory(
      'mjpeg-view',
      (int viewId) {
        final img = html.ImageElement()
          ..src = url
          ..style.width = '100%'
          ..style.height = '100%'
          ..style.objectFit = 'cover';

        return img;
      },
    );

    return const HtmlElementView(
      viewType: 'mjpeg-view',
    );
  }
}