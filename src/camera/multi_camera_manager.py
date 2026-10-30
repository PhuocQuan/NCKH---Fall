"""
File: src/camera/multi_camera_manager.py
Chức năng chính: Quản lý đa luồng camera (Multi-Camera RTSP Stream Manager).
- Tách biệt Primary AI Camera (chạy 24/7 AI detection) và Secondary Cameras (chỉ decode video khi xem, tiết kiệm CPU).
- Cung cấp luồng MJPEG và Snapshot cho từng camera theo ID: /api/cameras/{id}/stream.mjpg.
- Chẩn đoán kết nối RTSP tức thì: đo ping latency, độ phân giải thực, FPS, và thumbnail xem trước.
- Giám sát Watchdog & tự động kết nối lại khi camera mất mạng.
- Chuyển đổi 1-click Camera AI Giám sát Chính.
"""
from __future__ import annotations

import base64
import os
import re
import socket
import threading
import time
from typing import Any
from urllib.parse import urlparse

import cv2
import numpy as np

from src.camera.video_source import VideoSource, MockVideoCapture


class MultiCameraManager:
    """Singleton quản lý đa luồng camera RTSP và điều phối với AI Pipeline."""

    _instance: MultiCameraManager | None = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> MultiCameraManager:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self) -> None:
        self._lock = threading.RLock()
        self._secondary_sources: dict[str, dict[str, Any]] = {}
        self._subscribers: dict[str, int] = {}
        self._cached_jpegs: dict[str, bytes] = {}
        self._frame_counters: dict[str, int] = {}
        self._primary_camera_id: str = "CAM-011"
        self._running = True
        self._idle_timeout = 60.0  # Giải phóng secondary source sau 60s không ai xem

        # Luồng ngầm dọn dẹp camera phụ không có người xem để giải phóng CPU/RAM
        self._cleaner_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleaner_thread.start()

    @property
    def primary_camera_id(self) -> str:
        with self._lock:
            try:
                from src.web.shared.pipeline import pipeline
                if hasattr(pipeline, "camera_id") and pipeline.camera_id:
                    return str(pipeline.camera_id)
            except Exception:
                pass
            return self._primary_camera_id

    @primary_camera_id.setter
    def primary_camera_id(self, cam_id: str) -> None:
        with self._lock:
            self._primary_camera_id = cam_id

    def set_primary_camera(self, camera_id: str) -> dict[str, Any]:
        """Chuyển đổi Camera AI Giám sát Chính sang camera được chỉ định."""
        from src.web.shared.pipeline import pipeline
        from src.web.admin.repository import get_all_cameras_db

        cams = get_all_cameras_db()
        target_cam = None
        for c in cams:
            if c.get("id") == camera_id:
                target_cam = c
                break

        target_source: str | int = 0
        cam_name = camera_id
        if target_cam:
            cam_name = target_cam.get("name", camera_id)
            rtsp = str(target_cam.get("rtsp", "")).strip()
            if rtsp and rtsp != "0":
                target_source = rtsp
            else:
                target_source = 0

        with self._lock:
            # Nếu camera này trước đó đang chạy như một secondary source, dừng nó lại
            if camera_id in self._secondary_sources:
                self._stop_secondary_source_locked(camera_id)

            self.primary_camera_id = camera_id

        # Khởi động hoặc chuyển đổi pipeline AI sang camera mới
        pipeline.start(target_source, camera_id=camera_id)

        # Cập nhật state/status trong database nếu có
        try:
            from src.web.shared.db import get_db_client
            with get_db_client() as client:
                client.execute(
                    "UPDATE cameras SET status = 'online' WHERE id = ?",
                    [camera_id]
                )
        except Exception:
            pass

        return {
            "ok": True,
            "camera_id": camera_id,
            "name": cam_name,
            "source": str(target_source),
            "is_primary": True,
            "message": f"Đã chuyển camera giám sát sang: {cam_name} ({camera_id})"
        }

    def _get_secondary_source(self, camera_id: str) -> VideoSource | None:
        """Lấy hoặc khởi tạo VideoSource phụ cho một camera RTSP."""
        with self._lock:
            if camera_id in self._secondary_sources:
                info = self._secondary_sources[camera_id]
                info["last_accessed"] = time.time()
                return info["source"]

            # Tra cứu thông tin camera từ database
            from src.web.admin.repository import get_all_cameras_db
            cams = get_all_cameras_db()
            target_cam = next((c for c in cams if c.get("id") == camera_id), None)
            if not target_cam:
                return None

            rtsp = str(target_cam.get("rtsp", "")).strip()
            if not rtsp or rtsp == "0":
                source: str | int = 0
            else:
                source = rtsp

            fps = int(target_cam.get("fps", 25) or 25)
            # Khởi tạo VideoSource phụ
            try:
                vs = VideoSource(source=source, width=640, height=360)
                self._secondary_sources[camera_id] = {
                    "source": vs,
                    "last_accessed": time.time(),
                    "camera_info": target_cam,
                    "fps": fps
                }
                return vs
            except Exception as e:
                print(f"[MultiCameraManager] Không thể mở camera phụ {camera_id}: {e}")
                return None

    def _stop_secondary_source_locked(self, camera_id: str) -> None:
        if camera_id in self._secondary_sources:
            try:
                info = self._secondary_sources.pop(camera_id)
                vs = info.get("source")
                if vs and hasattr(vs, "release"):
                    vs.release()
            except Exception as e:
                print(f"[MultiCameraManager] Lỗi khi dừng secondary source {camera_id}: {e}")

    def subscribe(self, camera_id: str) -> None:
        with self._lock:
            self._subscribers[camera_id] = self._subscribers.get(camera_id, 0) + 1

    def unsubscribe(self, camera_id: str) -> None:
        with self._lock:
            if camera_id in self._subscribers:
                self._subscribers[camera_id] = max(0, self._subscribers[camera_id] - 1)

    def get_camera_jpeg(self, camera_id: str) -> bytes:
        """Lấy 1 khung hình JPEG mới nhất của camera chỉ định."""
        from src.web.shared.pipeline import pipeline

        # Nếu là camera đang được chọn, lấy từ pipeline toàn cục nếu đang chạy
        if camera_id == self.primary_camera_id or (pipeline.is_running() and str(getattr(pipeline, "camera_id", "")) == camera_id):
            if pipeline.is_running():
                jpeg = pipeline.get_jpeg_frame()
                if jpeg:
                    return jpeg

        # Ngược lại hoặc khi pipeline chưa sẵn sàng, lấy từ secondary source
        vs = self._get_secondary_source(camera_id)
        if not vs:
            return self._placeholder_frame(f"Camera {camera_id} Offline")

        ok, frame = vs.read(timeout=0.08)
        if ok and frame is not None:
            # Nén JPEG với chất lượng tối ưu (chất lượng 75, tốc độ nhanh)
            ok_encode, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if ok_encode:
                jpeg_bytes = buf.tobytes()
                with self._lock:
                    self._cached_jpegs[camera_id] = jpeg_bytes
                    self._frame_counters[camera_id] = self._frame_counters.get(camera_id, 0) + 1
                return jpeg_bytes

        # Nếu chưa đọc được frame mới, trả về cache gần nhất hoặc placeholder
        with self._lock:
            if camera_id in self._cached_jpegs:
                return self._cached_jpegs[camera_id]
        return self._placeholder_frame(f"Camera {camera_id} Mất tín hiệu")

    def get_next_camera_frame(self, camera_id: str, last_frame_id: int = -1, timeout: float = 0.04) -> tuple[int, bytes]:
        from src.web.shared.pipeline import pipeline

        if pipeline.is_running() and str(getattr(pipeline, "camera_id", "")) == camera_id:
            fid, jpeg = pipeline.get_next_jpeg_frame(last_frame_id=last_frame_id, timeout=timeout)
            return fid, jpeg

        time.sleep(timeout)
        jpeg = self.get_camera_jpeg(camera_id)
        with self._lock:
            fid = self._frame_counters.get(camera_id, 0)
        return fid, jpeg

    def _placeholder_frame(self, title: str = "Camera Offline", detail: str = "Không có tín hiệu RTSP") -> bytes:
        img = np.zeros((360, 640, 3), dtype=np.uint8)
        # Nền gradient xám tối sang xanh navy thanh lịch
        img[:, :] = (20, 24, 34)
        cv2.putText(img, "FallGuard AI", (210, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (148, 163, 184), 2)
        cv2.putText(img, title, (170, 205), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (239, 68, 68), 2)
        cv2.putText(img, detail, (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 116, 139), 1)
        ok, buf = cv2.imencode(".jpg", img)
        return buf.tobytes() if ok else b""

    def test_connection(self, rtsp_or_ip: str, port: int = 554, timeout: float = 3.0) -> dict[str, Any]:
        """
        Kiểm tra độ trễ (ping latency), độ phân giải thực, FPS và chụp thumbnail snapshot.
        Hỗ trợ: Chuỗi RTSP ('rtsp://...'), Địa chỉ IP, hoặc '0' (Webcam).
        """
        src = str(rtsp_or_ip).strip()
        t_start = time.perf_counter()

        # 1. Trường hợp Webcam cục bộ (0 hoặc int)
        if src.isdigit() or src == "0":
            try:
                cap = cv2.VideoCapture(int(src))
                if not cap.isOpened():
                    return {
                        "ok": False,
                        "connected": False,
                        "latency_ms": round((time.perf_counter() - t_start) * 1000, 1),
                        "error": f"Không thể mở Webcam ID {src}. Thiết bị đang bận hoặc không tồn tại."
                    }
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
                fps = round(float(cap.get(cv2.CAP_PROP_FPS) or 30.0), 1)
                ret, frame = cap.read()
                cap.release()

                thumb_b64 = ""
                if ret and frame is not None:
                    thumb_b64 = self._frame_to_thumb_b64(frame)

                return {
                    "ok": True,
                    "connected": True,
                    "latency_ms": round((time.perf_counter() - t_start) * 1000, 1),
                    "resolution": f"{w}x{h}",
                    "fps": fps,
                    "vendor": "Webcam Laptop / USB",
                    "thumbnail": thumb_b64,
                    "message": f"Kết nối Webcam thành công ({w}x{h} @ {fps}fps)"
                }
            except Exception as e:
                return {
                    "ok": False,
                    "connected": False,
                    "latency_ms": round((time.perf_counter() - t_start) * 1000, 1),
                    "error": f"Lỗi mở Webcam: {e}"
                }

        # 2. Trường hợp Camera RTSP / IP
        # Trích xuất IP và Port từ RTSP URL nếu có
        ip_addr = src
        rtsp_port = port
        if src.lower().startswith("rtsp://"):
            try:
                parsed = urlparse(src)
                ip_addr = parsed.hostname or src
                rtsp_port = parsed.port or 554
            except Exception:
                pass

        # Bước 2.1: Thăm dò socket TCP cực nhanh (Fast Socket Ping)
        sock_ok = False
        sock_time_ms = 0.0
        try:
            s_time = time.perf_counter()
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(min(timeout, 1.5))
                res = sock.connect_ex((ip_addr, rtsp_port))
                sock_time_ms = round((time.perf_counter() - s_time) * 1000, 1)
                sock_ok = (res == 0)
        except Exception:
            sock_ok = False

        if not sock_ok:
            return {
                "ok": False,
                "connected": False,
                "latency_ms": sock_time_ms or round((time.perf_counter() - t_start) * 1000, 1),
                "error": f"Không thể kết nối tới {ip_addr}:{rtsp_port}. Vui lòng kiểm tra địa chỉ IP và đảm bảo camera đã bật nguồn, cùng mạng Wi-Fi."
            }

        # Bước 2.2: Mở và đọc luồng video bằng OpenCV với thiết lập TCP low-delay
        prev_ffmpeg_opts = os.environ.get("OPENCV_FFMPEG_CAPTURE_OPTIONS", "")
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            "rtsp_transport;tcp|stimeout;3000000|max_delay;300000|flags;low_delay|fflags;nobuffer"
        )
        cap = None
        try:
            cap = cv2.VideoCapture(src)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if not cap.isOpened():
                return {
                    "ok": False,
                    "connected": False,
                    "latency_ms": round((time.perf_counter() - t_start) * 1000, 1),
                    "error": "Đã kết nối tới cổng camera nhưng không giải mã được luồng RTSP. Vui lòng kiểm tra lại Tên đăng nhập và Mật khẩu (Safety Code)."
                }

            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080
            fps = round(float(cap.get(cv2.CAP_PROP_FPS) or 25.0), 1)

            ret, frame = cap.read()
            latency_ms = round((time.perf_counter() - t_start) * 1000, 1)

            if not ret or frame is None:
                return {
                    "ok": False,
                    "connected": False,
                    "latency_ms": latency_ms,
                    "error": "Kết nối thành công nhưng không lấy được khung hình từ luồng RTSP (Timeout hoặc sai đường dẫn luồng)."
                }

            thumb_b64 = self._frame_to_thumb_b64(frame)
            return {
                "ok": True,
                "connected": True,
                "latency_ms": latency_ms,
                "resolution": f"{w}x{h}",
                "fps": fps,
                "vendor": "Camera IP RTSP (Imou / Ezviz / Dahua)",
                "thumbnail": thumb_b64,
                "message": f"Kết nối RTSP ổn định! Độ trễ: {latency_ms}ms ({w}x{h} @ {fps}fps)"
            }
        except Exception as e:
            return {
                "ok": False,
                "connected": False,
                "latency_ms": round((time.perf_counter() - t_start) * 1000, 1),
                "error": f"Lỗi ngoại lệ khi kiểm tra RTSP: {e}"
            }
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
            if prev_ffmpeg_opts:
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = prev_ffmpeg_opts
            else:
                os.environ.pop("OPENCV_FFMPEG_CAPTURE_OPTIONS", None)

    def _frame_to_thumb_b64(self, frame: np.ndarray) -> str:
        """Thu nhỏ frame về kích thước thumbnail 320x180 và chuyển thành Base64 Data URI."""
        try:
            h, w = frame.shape[:2]
            target_w = 320
            target_h = int(h * (target_w / max(1, w)))
            resized = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_AREA)
            ok, buf = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                b64_str = base64.b64encode(buf.tobytes()).decode("ascii")
                return f"data:image/jpeg;base64,{b64_str}"
        except Exception:
            pass
        return ""

    def get_all_cameras_status(self) -> list[dict[str, Any]]:
        """Lấy danh sách tất cả camera trong hệ thống kèm trạng thái hoạt động tức thời."""
        from src.web.admin.repository import get_all_cameras_db
        from src.web.shared.pipeline import pipeline

        cams = get_all_cameras_db()
        results = []
        cur_primary = self.primary_camera_id

        for c in cams:
            cam_id = c.get("id", "")
            is_primary = (cam_id == cur_primary)
            raw_status = c.get("status", "offline")

            if is_primary:
                # Nếu là camera đang chọn, kiểm tra trạng thái sống của pipeline
                online = pipeline.is_running()
                cur_status = "online" if online else raw_status
                fps = c.get("fps", 25)
            else:
                with self._lock:
                    if cam_id in self._secondary_sources:
                        vs = self._secondary_sources[cam_id].get("source")
                        online = bool(vs and not isinstance(vs, MockVideoCapture))
                        cur_status = "online" if online else "offline"
                    else:
                        cur_status = raw_status
                        online = (raw_status == "online")
                fps = c.get("fps", 25)

            results.append({
                "id": cam_id,
                "name": c.get("name", ""),
                "ip": c.get("ip", ""),
                "rtsp": c.get("rtsp", ""),
                "area": c.get("area", "Phòng chính"),
                "status": cur_status,
                "online": online,
                "is_primary": is_primary,
                "fps": fps,
                "resolution": c.get("resolution", "1920x1080"),
                "threshold": c.get("threshold", 80),
                "state": c.get("state", "normal")
            })

        return results

    def _cleanup_loop(self) -> None:
        """Định kỳ kiểm tra và tắt các camera phụ không còn subscriber hoặc không ai xem > 60s."""
        while self._running:
            time.sleep(15.0)
            now = time.time()
            to_stop = []
            with self._lock:
                for cid, info in list(self._secondary_sources.items()):
                    sub_count = self._subscribers.get(cid, 0)
                    last_acc = info.get("last_accessed", now)
                    if sub_count == 0 and (now - last_acc > self._idle_timeout):
                        to_stop.append(cid)

                for cid in to_stop:
                    self._stop_secondary_source_locked(cid)
                    print(f"[MultiCameraManager] Đã tạm dừng secondary camera {cid} (tiết kiệm CPU/mạng).")

    def close(self) -> None:
        self._running = False
        with self._lock:
            for cid in list(self._secondary_sources.keys()):
                self._stop_secondary_source_locked(cid)


# Khởi tạo singleton instance
multi_camera_manager = MultiCameraManager()
