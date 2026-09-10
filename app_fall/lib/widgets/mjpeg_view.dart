// lib/widgets/mjpeg_view.dart
// Custom MJPEG stream viewer — dùng http ^1.2.2 để đọc multipart/x-mixed-replace
// Tương thích với endpoint: /api/camera/stream.mjpg?token=...

import 'dart:async';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:http/http.dart' as http;
import '../core/api_client.dart';

class MjpegView extends StatefulWidget {
  final String streamUrl;
  final bool isBackendOnline;

  const MjpegView({
    super.key,
    required this.streamUrl,
    this.isBackendOnline = true,
  });

  @override
  State<MjpegView> createState() => _MjpegViewState();
}

class _MjpegViewState extends State<MjpegView> {
  Uint8List? _frame;
  bool _loading = true;
  String? _error;
  StreamSubscription<List<int>>? _sub;
  http.Client? _client;
  Timer? _webPollTimer;
  final List<int> _buffer = [];

  @override
  void initState() {
    super.initState();
    if (widget.isBackendOnline && widget.streamUrl.isNotEmpty) {
      if (kIsWeb) {
        _startWebPolling();
      } else {
        _startStream();
      }
    }
  }

  @override
  void didUpdateWidget(MjpegView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.streamUrl != widget.streamUrl || oldWidget.isBackendOnline != widget.isBackendOnline) {
      _stopStream();
      if (widget.isBackendOnline && widget.streamUrl.isNotEmpty) {
        if (kIsWeb) {
          _startWebPolling();
        } else {
          _startStream();
        }
      }
    }
  }

  @override
  void dispose() {
    _stopStream();
    super.dispose();
  }

  void _stopStream() {
    _webPollTimer?.cancel();
    _webPollTimer = null;
    _sub?.cancel();
    _sub = null;
    _client?.close();
    _client = null;
    _buffer.clear();
  }

  bool _isRequesting = false;

  void _startWebPolling() {
    setState(() { _loading = true; _error = null; });
    _webPollTimer = Timer.periodic(const Duration(milliseconds: 100), (timer) async {
      if (_isRequesting) return;
      _isRequesting = true;
      try {
        final bytes = await ApiClient().getSnapshotBytes();
        if (bytes != null && mounted) {
          setState(() {
            _frame = bytes;
            _loading = false;
            _error = null;
          });
        }
      } catch (e) {
        if (mounted) {
          setState(() {
            _loading = false;
            _error = e.toString().replaceAll('Exception: ', '');
          });
        }
      } finally {
        _isRequesting = false;
      }
    });
  }

  Future<void> _startStream() async {
    setState(() { _loading = true; _error = null; });
    try {
      _client = http.Client();
      final request = http.Request('GET', Uri.parse(widget.streamUrl));
      final response = await _client!.send(request).timeout(const Duration(seconds: 15));

      if (response.statusCode != 200) {
        if (mounted) setState(() { _loading = false; _error = 'HTTP ${response.statusCode}'; });
        return;
      }

      _sub = response.stream.listen(
        (chunk) {
          _buffer.addAll(chunk);
          _extractFrames();
        },
        onError: (e) {
          if (mounted) setState(() { _loading = false; _error = e.toString(); });
        },
        onDone: () {
          if (mounted && _frame == null) {
            setState(() { _loading = false; _error = 'Stream ended'; });
          }
        },
        cancelOnError: true,
      );
    } catch (e) {
      if (mounted) setState(() { _loading = false; _error = e.toString(); });
    }
  }

  // JPEG magic bytes: start = 0xFF 0xD8, end = 0xFF 0xD9
  void _extractFrames() {
    const jpegStart0 = 0xFF;
    const jpegStart1 = 0xD8;
    const jpegEnd0 = 0xFF;
    const jpegEnd1 = 0xD9;

    Uint8List? latestFrame;

    while (true) {
      // Find JPEG start
      int startIdx = -1;
      final bufLen = _buffer.length;
      for (int i = 0; i < bufLen - 1; i++) {
        if (_buffer[i] == jpegStart0 && _buffer[i + 1] == jpegStart1) {
          startIdx = i;
          break;
        }
      }
      if (startIdx == -1) {
        if (_buffer.length > 2048) {
          _buffer.removeRange(0, _buffer.length - 2);
        }
        break;
      }

      // Drop any garbage before startIdx
      if (startIdx > 0) {
        _buffer.removeRange(0, startIdx);
        startIdx = 0;
      }

      // Find JPEG end after start
      int endIdx = -1;
      final curLen = _buffer.length;
      for (int i = 2; i < curLen - 1; i++) {
        if (_buffer[i] == jpegEnd0 && _buffer[i + 1] == jpegEnd1) {
          endIdx = i + 2;
          break;
        }
      }
      if (endIdx == -1) {
        // Prevent memory bloating if stream buffer grows without end marker
        if (_buffer.length > 256 * 1024) {
          _buffer.clear();
        }
        break;
      }

      // Extract complete JPEG frame, discarding any older frames in this batch
      latestFrame = Uint8List.fromList(_buffer.sublist(0, endIdx));
      _buffer.removeRange(0, endIdx);
    }

    // Only render the newest frame to eliminate stream lag
    if (latestFrame != null && mounted) {
      setState(() {
        _frame = latestFrame;
        _loading = false;
        _error = null;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.isBackendOnline || widget.streamUrl.isEmpty) {
      return _buildOfflinePlaceholder();
    }

    if (_loading && _frame == null) {
      return _buildLoadingWidget();
    }

    if (_error != null && _frame == null) {
      return _buildErrorWidget(_error!);
    }

    if (_frame != null) {
      return Image.memory(
        _frame!,
        gaplessPlayback: true,
        fit: BoxFit.cover,
        width: double.infinity,
        height: double.infinity,
      );
    }

    return _buildLoadingWidget();
  }

  Widget _buildOfflinePlaceholder() {
    return Container(
      color: const Color(0xFF0f172a),
      child: const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.videocam_off, color: Color(0xFF475569), size: 48),
            SizedBox(height: 12),
            Text('Server ngoại tuyến', style: TextStyle(color: Color(0xFF64748b), fontSize: 14)),
            SizedBox(height: 4),
            Text('Kiểm tra kết nối và thử lại', style: TextStyle(color: Color(0xFF475569), fontSize: 12)),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorWidget(String error) {
    return Container(
      color: const Color(0xFF0f172a),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, color: Color(0xFFEF4444), size: 40),
            const SizedBox(height: 10),
            Text(error, textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFFEF4444), fontSize: 13)),
            const SizedBox(height: 6),
            GestureDetector(
              onTap: () { 
                _stopStream(); 
                if (kIsWeb) {
                  _startWebPolling();
                } else {
                  _startStream(); 
                }
              },
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                decoration: BoxDecoration(
                  border: Border.all(color: const Color(0xFF4f46e5)),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Text('Thử lại', style: TextStyle(color: Color(0xFF4f46e5), fontSize: 12, fontWeight: FontWeight.w700)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLoadingWidget() {
    return Container(
      color: const Color(0xFF0f172a),
      child: const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            SizedBox(
              width: 32,
              height: 32,
              child: CircularProgressIndicator(color: Color(0xFF4f46e5), strokeWidth: 2.5),
            ),
            SizedBox(height: 12),
            Text('Đang kết nối stream...', style: TextStyle(color: Color(0xFF64748b), fontSize: 13)),
          ],
        ),
      ),
    );
  }
}
