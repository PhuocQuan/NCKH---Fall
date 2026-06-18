// // lib/services/fall_alert_service.dart

// import 'dart:async';
// import 'dart:convert';
// import 'package:audioplayers/audioplayers.dart';
// import 'package:flutter_local_notifications/flutter_local_notifications.dart';
// import 'package:web_socket_channel/web_socket_channel.dart';

// class FallEvent {
//   final double confidence;
//   final String timestamp;
//   const FallEvent({required this.confidence, required this.timestamp});
// }

// class FallAlertService {
//   final String wsUrl;

//   WebSocketChannel? _channel;
//   StreamSubscription? _subscription;
//   final _player = AudioPlayer();
//   final _notifications = FlutterLocalNotificationsPlugin();
//   final _fallController = StreamController<FallEvent>.broadcast();
//   Timer? _reconnectTimer;

//   // WHY flag riêng thay vì dùng _isConnected:
//   // tránh gọi dispose() sau khi service đã bị destroy
//   bool _disposed = false;

//   Stream<FallEvent> get fallEvents => _fallController.stream;

//   FallAlertService({this.wsUrl = 'ws://192.168.1.x:8000/ws'});

//   Future<void> init() async {
//     await _initNotifications();
//     _connect();
//   }

//   Future<void> _initNotifications() async {
//     const android = AndroidInitializationSettings('@mipmap/ic_launcher');
//     const ios = DarwinInitializationSettings(
//       requestAlertPermission: true,
//       requestSoundPermission: true,
//     );
//     await _notifications.initialize(
//       const InitializationSettings(android: android, iOS: ios),
//     );
//   }

//   void _connect() {
//     if (_disposed) return;

//     // WHY cancel subscription trước: tránh listener cũ của channel cũ vẫn còn sống
//     _subscription?.cancel();
//     _channel?.sink.close();

//     try {
//       _channel = WebSocketChannel.connect(Uri.parse(wsUrl));
//       _subscription = _channel!.stream.listen(
//         _onMessage,
//         onError: (_) => _scheduleReconnect(),
//         onDone: _scheduleReconnect,
//         // WHY cancelOnError: false — giữ subscription sống để onDone vẫn fire
//         cancelOnError: false,
//       );
//     } catch (_) {
//       _scheduleReconnect();
//     }
//   }

//   void _onMessage(dynamic raw) {
//     try {
//       final data = jsonDecode(raw as String) as Map<String, dynamic>;
//       final isFall = data['is_fall'] as bool? ?? false;
//       if (!isFall) return;

//       final event = FallEvent(
//         confidence: (data['confidence'] as num?)?.toDouble() ?? 0.0,
//         timestamp: data['timestamp'] as String? ?? '',
//       );

//       // Thứ tự quan trọng: push UI trước, rồi mới side effects
//       _fallController.add(event);
//       _playAlarm();
//       _showNotification(event);
//     } catch (_) {
//       // Bỏ qua message lỗi format, không crash service
//     }
//   }

//   Future<void> _playAlarm() async {
//     await _player.stop();
//     await _player.play(AssetSource('sounds/alarm.mp3'));
//   }

//   Future<void> _showNotification(FallEvent event) async {
//     const androidDetails = AndroidNotificationDetails(
//       'fall_alert',
//       'Fall Alerts',
//       channelDescription: 'Cảnh báo phát hiện té ngã',
//       importance: Importance.max,
//       priority: Priority.high,
//       enableVibration: true,
//     );
//     const iosDetails = DarwinNotificationDetails(
//       presentAlert: true,
//       presentSound: true,
//       presentBadge: true,
//     );
//     await _notifications.show(
//       0,
//       '⚠️ Phát hiện té ngã!',
//       'Độ tin cậy: ${(event.confidence * 100).toStringAsFixed(0)}%'
//       '  ·  ${event.timestamp}',
//       const NotificationDetails(android: androidDetails, iOS: iosDetails),
//     );
//   }

//   void _scheduleReconnect() {
//     if (_disposed) return;

//     // WHY cancel trước: tránh double-timer nếu onError + onDone cùng fire
//     _reconnectTimer?.cancel();
//     _reconnectTimer = Timer(const Duration(seconds: 3), _connect);
//   }

//   void dispose() {
//     _disposed = true;
//     _reconnectTimer?.cancel();
//     _subscription?.cancel();
//     _channel?.sink.close();
//     _player.dispose();
//     _fallController.close();
//   }
// }