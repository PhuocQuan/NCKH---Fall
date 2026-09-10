"""
File: src/face/face_recognizer.py
Chức năng chính: Nhận diện khuôn mặt (Face Recognition) sử dụng thư viện face_recognition.
Phân loại người quen, người cần chú ý (ATTENTION), hoặc người lạ (STRANGER).

File liên kết:
- Load dữ liệu từ: data/known_faces/
- Được gọi bởi: app.py, pipeline.py
"""
from __future__ import annotations

import enum
import os
import re
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np

from src.core.config import FaceConfig


class PersonType(enum.Enum):
    FAMILY = "FAMILY"
    ATTENTION = "ATTENTION"
    STRANGER = "STRANGER"


@dataclass
class RecognizedFace:
    name: str
    person_type: PersonType
    box: tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float = 0.0


YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SFACE_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"


def _compute_iou(box1: tuple[int, int, int, int], box2: tuple[int, int, int, int]) -> float:
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    xi1 = max(x1, x2)
    yi1 = max(y1, y2)
    xi2 = min(x1 + w1, x2 + w2)
    yi2 = min(y1 + h1, y2 + h2)
    inter_w = max(0, xi2 - xi1)
    inter_h = max(0, yi2 - yi1)
    inter_area = inter_w * inter_h
    union_area = (w1 * h1) + (w2 * h2) - inter_area
    return inter_area / union_area if union_area > 0 else 0.0


class FaceRecognizer:
    """Class quản lý việc nhận diện khuôn mặt."""
    def __init__(self, config: FaceConfig, models_dir: str = "models") -> None:
        self.config = config
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self.known_faces_dir = Path(config.known_faces_dir)
        self.known_faces_dir.mkdir(parents=True, exist_ok=True)

        self.detector = None
        self.recognizer = None
        self.known_embeddings: list[tuple[str, PersonType, np.ndarray]] = []
        self._recent_known_tracks: list[tuple[float, str, PersonType, tuple[int, int, int, int]]] = []
        self._initialized = False

        self._init_models()
        self.reload_known_faces()

    def _download_file(self, url: str, target_path: Path) -> bool:
        if target_path.exists() and target_path.stat().st_size > 0:
            return True
        try:
            print(f"[FaceRecognizer] Downloading model from {url} ...")
            urllib.request.urlretrieve(url, str(target_path))
            print(f"[FaceRecognizer] Saved model to {target_path}")
            return True
        except Exception as e:
            print(f"[FaceRecognizer] Failed to download {url}: {e}")
            if target_path.exists():
                target_path.unlink()
            return False

    def _init_models(self) -> None:
        yunet_path = self.models_dir / "face_detection_yunet_2023mar.onnx"
        sface_path = self.models_dir / "face_recognition_sface_2021dec.onnx"

        # Tải ONNX YuNet và SFace nếu chưa có
        self._download_file(YUNET_URL, yunet_path)
        self._download_file(SFACE_URL, sface_path)

        if yunet_path.exists() and sface_path.exists():
            try:
                score_thresh = float(getattr(self.config, "score_threshold", 0.30))

                self.detector = cv2.FaceDetectorYN.create(
                    model=str(yunet_path),
                    config="",
                    input_size=(640, 640),
                    score_threshold=score_thresh,
                    nms_threshold=0.3,
                    top_k=50,
                )

                self.recognizer = cv2.FaceRecognizerSF.create(
                    model=str(sface_path),
                    config="",
                )
                self._initialized = True
                print("[FaceRecognizer] YuNet & SFace initialized successfully.")
                return
            except Exception as e:
                print(f"[FaceRecognizer] Error loading YuNet/SFace ONNX models: {e}")

        print("[FaceRecognizer] Fallback to OpenCV Haar Cascade face detector.")
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        if os.path.exists(cascade_path):
            self.detector = cv2.CascadeClassifier(cascade_path)

    def parse_filename(self, filename: str) -> tuple[str, PersonType]:
        """Tách tên và loại đối tượng từ tên file.
        Hỗ trợ nạp nhiều ảnh mẫu cho một người (ví dụ: 'An.jpg', 'An_1.jpg', 'An_2.jpg', 'An (1).jpg').
        Ví dụ: 'OngNoi_ATTENTION.jpg', 'OngNoi_ATTENTION_1.jpg' -> ('OngNoi', PersonType.ATTENTION)
               'Me_FAMILY.jpg', 'Me_FAMILY_2.jpg' -> ('Me', PersonType.FAMILY)
               'BaNoi.png' -> ('BaNoi', PersonType.FAMILY)
        """
        stem = Path(filename).stem
        cleaned_stem = re.sub(r'[\s_\-]+(?:\(\d+\)|\d+)$', '', stem)
        parts = cleaned_stem.split("_")
        if len(parts) >= 2:
            tag = parts[-1].upper()
            if tag in ("ATTENTION", "VIP"):
                name = "_".join(parts[:-1])
                return name, PersonType.ATTENTION
            elif tag == "FAMILY":
                name = "_".join(parts[:-1])
                return name, PersonType.FAMILY

        return cleaned_stem, PersonType.FAMILY

    def reload_known_faces(self) -> None:
        """Đọc toàn bộ ảnh mẫu trong thư mục known_faces_dir và trích xuất vector đặc trưng."""
        self.known_embeddings.clear()
        if not self.known_faces_dir.exists():
            return

        valid_exts = {".jpg", ".jpeg", ".png", ".bmp"}
        image_files = [f for f in self.known_faces_dir.iterdir() if f.suffix.lower() in valid_exts]

        print(f"[FaceRecognizer] Found {len(image_files)} sample image(s) in {self.known_faces_dir}")

        for img_path in image_files:
            name, person_type = self.parse_filename(img_path.name)
            img = cv2.imread(str(img_path))
            if img is None:
                continue

            feature = self._extract_feature(img)
            if feature is not None:
                self.known_embeddings.append((name, person_type, feature))
                print(f"  + Loaded face for: {name} ({person_type.value})")
            else:
                print(f"  - Warning: Could not detect face in {img_path.name}")

    def _extract_feature(self, image: np.ndarray) -> np.ndarray | None:
        """Trích xuất 128D SFace feature vector từ ảnh chứa khuôn mặt."""
        if not self._initialized or self.detector is None or self.recognizer is None:
            return None

        h, w = image.shape[:2]
        self.detector.setInputSize((w, h))
        
        # Dùng ngưỡng score_threshold thấp (0.20) khi đọc ảnh mẫu để đảm bảo đọc đủ tất cả các mặt
        orig_thresh = self.detector.getScoreThreshold() if hasattr(self.detector, "getScoreThreshold") else 0.58
        if hasattr(self.detector, "setScoreThreshold"):
            self.detector.setScoreThreshold(0.20)

        try:
            _, faces = self.detector.detect(image)
        finally:
            if hasattr(self.detector, "setScoreThreshold"):
                self.detector.setScoreThreshold(orig_thresh)

        if faces is not None and len(faces) > 0:
            face = faces[0]  # Lấy khuôn mặt đầu tiên
            aligned_face = self.recognizer.alignCrop(image, face)
            feature = self.recognizer.feature(aligned_face)
            return feature
        return None

    def recognize(self, frame: np.ndarray) -> list[RecognizedFace]:
        """Nhận diện tất cả khuôn mặt trong frame.
        Trả về danh sách RecognizedFace bao gồm tên, loại (FAMILY, ATTENTION, STRANGER) và box.
        """
        if not self.config.enabled:
            return []

        results: list[RecognizedFace] = []
        h, w = frame.shape[:2]

        current_time = time.time()
        # Dọn dẹp các track nhận diện cũ hơn 2.5 giây
        self._recent_known_tracks = [
            t for t in self._recent_known_tracks if (current_time - t[0]) <= 2.5
        ]

        if self._initialized and self.detector is not None and self.recognizer is None:
            # Haar Cascade fallback
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            for (fx, fy, fw, fh) in faces:
                results.append(
                    RecognizedFace(
                        name="Stranger",
                        person_type=PersonType.STRANGER,
                        box=(int(fx), int(fy), int(fw), int(fh)),
                        confidence=0.5,
                    )
                )
            return results

        # Tối ưu phát hiện khuôn mặt cho camera độ phân giải cao (1080p / 2K)
        scale = 1.0
        max_dim = max(h, w)
        if max_dim > 1024:
            scale = 1024.0 / max_dim
            det_w = int(w * scale)
            det_h = int(h * scale)
            det_frame = cv2.resize(frame, (det_w, det_h))
        else:
            det_frame = frame
            det_w, det_h = w, h

        self.detector.setInputSize((det_w, det_h))
        _, faces = self.detector.detect(det_frame)
        
        num_faces = len(faces) if faces is not None else 0
        print(f"[DEBUG] YuNet detected {num_faces} faces at threshold {self.detector.getScoreThreshold()}", flush=True)

        if faces is None or len(faces) == 0:
            return results

        if scale != 1.0:
            faces = faces.copy()
            faces[:, :14] = faces[:, :14] / scale

        for face in faces:
            bbox = face[:4].astype(int)
            fx, fy, fw, fh = bbox[0], bbox[1], bbox[2], bbox[3]
            
            print(f"[DEBUG] Face bbox: {bbox}, fw: {fw}, fh: {fh}", flush=True)

            # Bỏ qua các vật thể nhỏ hơn 35x35 pixel hoặc hình dạng dị dạng
            if fw < 35 or fh < 35:
                print(f"[DEBUG] Skipped due to small size: {fw}x{fh}", flush=True)
                continue
            aspect_ratio = fw / float(max(1, fh))
            # Nới lỏng tỷ lệ khung hình vì góc quay từ dưới lên (laptop) có thể làm bóp méo khung
            if aspect_ratio < 0.30 or aspect_ratio > 2.50:
                print(f"[DEBUG] Skipped due to aspect ratio: {aspect_ratio:.2f}", flush=True)
                continue

            aligned_face = self.recognizer.alignCrop(frame, face)

            query_feature = self.recognizer.feature(aligned_face)

            best_match_name = "Stranger"
            best_match_type = PersonType.STRANGER
            best_score = 0.0
            best_known = None

            # So sánh với database người thân đã lưu
            threshold = float(getattr(self.config, "similarity_threshold", 0.40))
            for known_name, person_type, known_feature in self.known_embeddings:
                score = float(self.recognizer.match(query_feature, known_feature, cv2.FaceRecognizerSF_FR_COSINE))
                if score > best_score:
                    best_score = score
                    best_known = (known_name, person_type)

            current_box = (max(0, fx), max(0, fy), max(0, fw), max(0, fh))

            if best_known and best_score >= threshold:
                best_match_name, best_match_type = best_known
                face_conf = min(0.99, max(0.50, float(best_score)))
                self._recent_known_tracks.append((current_time, best_match_name, best_match_type, current_box))
            else:
                # Kiểm tra cơ chế giữ nhận diện nếu người quen vừa ở vị trí này bị che một phần mặt (IoU cao)
                tracked_match = None
                for t_time, t_name, t_type, t_box in reversed(self._recent_known_tracks):
                    if _compute_iou(current_box, t_box) >= 0.30 and best_score >= (threshold * 0.70):
                        tracked_match = (t_name, t_type)
                        break

                if tracked_match:
                    best_match_name, best_match_type = tracked_match
                    face_conf = min(0.95, max(0.60, float(best_score + 0.15)))
                    self._recent_known_tracks.append((current_time, best_match_name, best_match_type, current_box))
                else:
                    best_match_name = "Stranger"
                    best_match_type = PersonType.STRANGER
                    det_score = float(face[14]) if len(face) > 14 else 0.90
                    stranger_divergence = max(0.0, 1.0 - best_score)
                    # Tính độ tin cậy phát hiện người lạ dựa trên 70% YuNet + 30% độ sai biệt
                    face_conf = min(0.99, max(0.70, det_score * 0.7 + stranger_divergence * 0.3))

            results.append(
                RecognizedFace(
                    name=best_match_name,
                    person_type=best_match_type,
                    box=current_box,
                    confidence=float(face_conf),
                )
            )

        return results
