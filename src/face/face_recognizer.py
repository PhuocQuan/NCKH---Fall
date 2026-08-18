from __future__ import annotations

import enum
import os
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


class FaceRecognizer:
    def __init__(self, config: FaceConfig, models_dir: str = "models") -> None:
        self.config = config
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self.known_faces_dir = Path(config.known_faces_dir)
        self.known_faces_dir.mkdir(parents=True, exist_ok=True)

        self.detector = None
        self.recognizer = None
        self.known_embeddings: list[tuple[str, PersonType, np.ndarray]] = []
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
                score_thresh = float(getattr(self.config, "score_threshold", 0.58))
                self.detector = cv2.FaceDetectorYN.create(
                    model=str(yunet_path),
                    config="",
                    input_size=(640, 640),
                    score_threshold=score_thresh,
                    nms_threshold=0.3,
                    top_k=5000,
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
        Ví dụ: 'OngNoi_ATTENTION.jpg' -> ('OngNoi', PersonType.ATTENTION)
               'Me_FAMILY.jpg' -> ('Me', PersonType.FAMILY)
               'BaNoi.png' -> ('BaNoi', PersonType.FAMILY)
        """
        stem = Path(filename).stem
        parts = stem.split("_")
        if len(parts) >= 2:
            tag = parts[-1].upper()
            if tag == "ATTENTION" or tag == "VIP":
                name = "_".join(parts[:-1])
                return name, PersonType.ATTENTION
            elif tag == "FAMILY":
                name = "_".join(parts[:-1])
                return name, PersonType.FAMILY

        return stem, PersonType.FAMILY

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
        _, faces = self.detector.detect(image)

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

        if not self._initialized or self.detector is None or self.recognizer is None:
            return results

        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(frame)

        if faces is None or len(faces) == 0:
            return results

        for face in faces:
            bbox = face[:4].astype(int)
            fx, fy, fw, fh = bbox[0], bbox[1], bbox[2], bbox[3]

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

            if best_known and best_score >= threshold:
                best_match_name, best_match_type = best_known
            else:
                best_match_name = "Stranger"
                best_match_type = PersonType.STRANGER

            results.append(
                RecognizedFace(
                    name=best_match_name,
                    person_type=best_match_type,
                    box=(max(0, fx), max(0, fy), max(0, fw), max(0, fh)),
                    confidence=float(best_score),
                )
            )

        return results
