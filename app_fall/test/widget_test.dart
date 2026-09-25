// This is a basic Flutter widget test for FallGuard AI app.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:app_fall/main.dart';

void main() {
  testWidgets('FallGuard app smoke test', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const FallGuardApp());

    // The app should render without crashing (shows login or home screen)
    expect(find.byType(MaterialApp), findsOneWidget);
  });
}
