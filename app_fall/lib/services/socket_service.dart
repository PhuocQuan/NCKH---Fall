import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';

class SocketService {
  late final WebSocketChannel channel;
  late final Stream<Map<String, dynamic>> stream;

  SocketService() {
    channel = WebSocketChannel.connect(
      Uri.parse('ws://127.0.0.1:8000/ws'),
    );

    stream = channel.stream
        .map((data) => jsonDecode(data) as Map<String, dynamic>)
        .asBroadcastStream();
  }

  void dispose() {
    channel.sink.close();
  }
}