// lib/core/models.dart
// Data models cho FallGuard AI client app

class UserModel {
  final String email;
  final String name;
  final String role;
  final String? phone;
  final List<String> assignedCameras;
  final String status;

  const UserModel({
    required this.email,
    required this.name,
    required this.role,
    this.phone,
    this.assignedCameras = const [],
    this.status = 'Đang hoạt động',
  });

  factory UserModel.fromJson(Map<String, dynamic> json) => UserModel(
        email: json['email'] ?? '',
        name: json['name'] ?? '',
        role: json['role'] ?? 'Khachhang',
        phone: json['phone'],
        assignedCameras: List<String>.from(json['assignedCameras'] ?? []),
        status: json['status'] ?? 'Đang hoạt động',
      );

  Map<String, dynamic> toJson() => {
        'email': email,
        'name': name,
        'role': role,
        'phone': phone,
        'assignedCameras': assignedCameras,
        'status': status,
      };

  UserModel copyWith({
    String? email,
    String? name,
    String? role,
    String? phone,
    List<String>? assignedCameras,
    String? status,
  }) =>
      UserModel(
        email: email ?? this.email,
        name: name ?? this.name,
        role: role ?? this.role,
        phone: phone ?? this.phone,
        assignedCameras: assignedCameras ?? this.assignedCameras,
        status: status ?? this.status,
      );

  String get displayRole {
    switch (role.toLowerCase()) {
      case 'admin':
        return 'Quản trị viên';
      case 'khachhang':
      case 'user':
        return 'User (Khách hàng)';
      default:
        return role;
    }
  }

  String get initials {
    final words = name.trim().split(RegExp(r'\s+'));
    if (words.isEmpty) return 'US';
    if (words.length == 1) return words[0].substring(0, words[0].length.clamp(0, 2)).toUpperCase();
    return '${words.first[0]}${words.last[0]}'.toUpperCase();
  }
}

class CameraModel {
  final String id;
  final String name;
  final String area;
  final String state; // normal, walking, sitting, lying, fallen, alert
  final String status; // online, offline, maintenance
  final int fps;
  final String resolution;
  final int threshold;
  final String rtsp;

  const CameraModel({
    required this.id,
    required this.name,
    required this.area,
    this.state = 'normal',
    this.status = 'offline',
    this.fps = 0,
    this.resolution = '1280x720',
    this.threshold = 80,
    this.rtsp = '',
  });

  factory CameraModel.fromJson(Map<String, dynamic> json) => CameraModel(
        id: json['id'] ?? '',
        name: json['name'] ?? '',
        area: json['area'] ?? 'Khác',
        state: json['state'] ?? 'normal',
        status: json['status'] ?? 'offline',
        fps: json['fps'] ?? 0,
        resolution: json['resolution'] ?? '1280x720',
        threshold: json['threshold'] ?? 80,
        rtsp: json['rtsp'] ?? '',
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'area': area,
        'state': state,
        'status': status,
        'fps': fps,
        'resolution': resolution,
        'threshold': threshold,
        'rtsp': rtsp,
      };

  bool get isOnline => status == 'online';
  bool get isMaintenance => status == 'maintenance' || status == 'Bảo trì';
  bool get isFallen => state == 'fallen' || state == 'alert';
}

class AlertModel {
  final String id;
  final String time;
  final String camera;
  final String person;
  final int confidence;
  final String status;
  final String level;
  final String? media;
  final String? cloudImgUrl;
  final String? cloudVideoUrl;

  const AlertModel({
    required this.id,
    required this.time,
    required this.camera,
    required this.person,
    this.confidence = 0,
    this.status = 'Chưa xử lý',
    this.level = 'Cao',
    this.media,
    this.cloudImgUrl,
    this.cloudVideoUrl,
  });

  factory AlertModel.fromJson(Map<String, dynamic> json) => AlertModel(
        id: json['id'] ?? '',
        time: json['time'] ?? '',
        camera: json['camera'] ?? '',
        person: json['person'] ?? '',
        confidence: json['confidence'] ?? 0,
        status: json['status'] ?? 'Chưa xử lý',
        level: json['level'] ?? 'Cao',
        media: json['media'],
        cloudImgUrl: json['cloud_img_url'],
        cloudVideoUrl: json['cloud_video_url'],
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'time': time,
        'camera': camera,
        'person': person,
        'confidence': confidence,
        'status': status,
        'level': level,
        'media': media,
        'cloud_img_url': cloudImgUrl,
        'cloud_video_url': cloudVideoUrl,
      };

  bool get hasVideo =>
      (cloudVideoUrl != null && cloudVideoUrl!.isNotEmpty) ||
      (media != null && media!.toLowerCase().contains('video'));
}

class EmergencyContact {
  final String name;
  final String relationship;
  final String phone;
  final String email;

  const EmergencyContact({
    required this.name,
    required this.relationship,
    required this.phone,
    required this.email,
  });

  factory EmergencyContact.fromJson(Map<String, dynamic> json) => EmergencyContact(
        name: json['name'] ?? '',
        relationship: json['relationship'] ?? '',
        phone: json['phone'] ?? '',
        email: json['email'] ?? '',
      );

  Map<String, dynamic> toJson() => {
        'name': name,
        'relationship': relationship,
        'phone': phone,
        'email': email,
      };

  EmergencyContact copyWith({
    String? name,
    String? relationship,
    String? phone,
    String? email,
  }) =>
      EmergencyContact(
        name: name ?? this.name,
        relationship: relationship ?? this.relationship,
        phone: phone ?? this.phone,
        email: email ?? this.email,
      );
}

class AppNotification {
  final String id;
  final String type; // fall, disconnect, maintenance, update
  final String title;
  final String content;
  final String time;
  bool read;
  final String? actionUrl;

  AppNotification({
    required this.id,
    required this.type,
    required this.title,
    required this.content,
    required this.time,
    this.read = false,
    this.actionUrl,
  });

  factory AppNotification.fromJson(Map<String, dynamic> json) => AppNotification(
        id: json['id'] ?? '',
        type: json['type'] ?? 'maintenance',
        title: json['title'] ?? '',
        content: json['content'] ?? '',
        time: json['time'] ?? '',
        read: json['read'] ?? false,
        actionUrl: json['actionUrl'],
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'type': type,
        'title': title,
        'content': content,
        'time': time,
        'read': read,
        if (actionUrl != null) 'actionUrl': actionUrl,
      };
}

class MonitoredProfile {
  final String name;
  final int age;
  final String gender;
  final String address;
  final String emergencyContact;

  const MonitoredProfile({
    required this.name,
    required this.age,
    required this.gender,
    required this.address,
    required this.emergencyContact,
  });

  factory MonitoredProfile.fromJson(Map<String, dynamic> json) => MonitoredProfile(
        name: json['name'] ?? '',
        age: json['age'] ?? 0,
        gender: json['gender'] ?? 'Nam',
        address: json['address'] ?? '',
        emergencyContact: json['emergencyContact'] ?? '',
      );

  Map<String, dynamic> toJson() => {
        'name': name,
        'age': age,
        'gender': gender,
        'address': address,
        'emergencyContact': emergencyContact,
      };

  MonitoredProfile copyWith({
    String? name,
    int? age,
    String? gender,
    String? address,
    String? emergencyContact,
  }) =>
      MonitoredProfile(
        name: name ?? this.name,
        age: age ?? this.age,
        gender: gender ?? this.gender,
        address: address ?? this.address,
        emergencyContact: emergencyContact ?? this.emergencyContact,
      );
}
