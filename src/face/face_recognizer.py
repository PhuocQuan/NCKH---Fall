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


def _compute_box_center_dist(box1: tuple[int, int, int, int], box2: tuple[int, int, int, int]) -> float:
    cx1 = box1[0] + box1[2] / 2.0
    cy1 = box1[1] + box1[3] / 2.0
    cx2 = box2[0] + box2[2] / 2.0
    cy2 = box2[1] + box2[3] / 2.0
    return float(((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5)


def _is_duplicate_face(box1: tuple[int, int, int, int], box2: tuple[int, int, int, int]) -> bool:
    """Kiểm tra xem 2 bounding box có phải cùng 1 khuôn mặt bị phát hiện đúp (trán/cằm/lệch tâm) hay không."""
    iou = _compute_iou(box1, box2)
    if iou >= 0.22:
        return True
    dist = _compute_box_center_dist(box1, box2)
    ref_dim = min(box1[2], box1[3], box2[2], box2[3])
    if dist < ref_dim * 0.50:
        return True
    # Kiểm tra bao hàm (một box lọt vào trong box kia)
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    xi1, yi1 = max(x1, x2), max(y1, y2)
    xi2, yi2 = min(x1 + w1, x2 + w2), min(y1 + h1, y2 + h2)
    inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
    min_area = min(w1 * h1, w2 * h2)
    if min_area > 0 and (inter_area / min_area) >= 0.50:
        return True
    return False


@dataclass
class _TrackedFace:
    """Theo dõi danh tính khuôn mặt đa khung hình (Temporal Identity Tracking)."""
    track_id: int
    box: tuple[int, int, int, int]
    last_seen: float
    confirmed_name: str
    person_type: PersonType
    history: list[tuple[str, float]]
    consecutive_stranger_count: int = 0
    last_known_seen_time: float = 0.0


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
        self._active_face_tracks: list[_TrackedFace] = []
        self._next_track_id: int = 1
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
                score_thresh = max(0.58, float(getattr(self.config, "score_threshold", 0.58)))

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
        """Đọc toàn bộ ảnh mẫu trong thư mục known_faces_dir, lọc bỏ ảnh nhiễu/lẫn lộn và trích xuất vector đặc trưng."""
        self.known_embeddings.clear()
        if not self.known_faces_dir.exists():
            return

        valid_exts = {".jpg", ".jpeg", ".png", ".bmp"}
        image_files = [f for f in self.known_faces_dir.iterdir() if f.suffix.lower() in valid_exts]

        print(f"[FaceRecognizer] Found {len(image_files)} sample image(s) in {self.known_faces_dir}")

        candidates: list[tuple[str, PersonType, np.ndarray, str]] = []
        for img_path in image_files:
            name, person_type = self.parse_filename(img_path.name)
            img = cv2.imread(str(img_path))
            if img is None:
                continue

            feature = self._extract_feature(img)
            if feature is not None:
                candidates.append((name, person_type, feature, img_path.name))
            else:
                print(f"  - Warning: Could not detect face in {img_path.name}")

        # Kiểm tra xung đột chéo giữa các ảnh mẫu (Cross-identity conflict filtering)
        # Loại bỏ các ảnh mẫu bị lẫn người (ảnh có độ tương đồng với người khác >= 0.40 hoặc cao hơn chính người đó)
        clean_embeddings: list[tuple[str, PersonType, np.ndarray]] = []
        if self._initialized and self.recognizer is not None and len(candidates) > 2:
            for name, person_type, feature, fname in candidates:
                other_scores = [
                    (float(self.recognizer.match(feature, c[2], cv2.FaceRecognizerSF_FR_COSINE)), c[0], c[3])
                    for c in candidates if c[0] != name
                ]
                own_scores = [
                    float(self.recognizer.match(feature, c[2], cv2.FaceRecognizerSF_FR_COSINE))
                    for c in candidates if c[0] == name and c[3] != fname
                ]
                max_other = max((s for s, _, _ in other_scores), default=0.0)
                max_own = max(own_scores, default=1.0)

                if max_other > max_own or max_other >= 0.40:
                    conflict_name = next(c_name for s, c_name, _ in other_scores if s == max_other)
                    print(f"  [Dataset QC] Bo qua anh gay nhieu {fname} ({name}): xung dot voi {conflict_name} (sim={max_other:.3f})")
                    continue

                clean_embeddings.append((name, person_type, feature))
                print(f"  + Loaded verified face for: {name} ({person_type.value}) from {fname}")

            # Đảm bảo mỗi người có ít nhất 1 ảnh mẫu đại diện nếu bộ lọc quá chặt
            all_names = {c[0] for c in candidates}
            loaded_names = {c[0] for c in clean_embeddings}
            for missing_name in all_names - loaded_names:
                first_sample = next(c for c in candidates if c[0] == missing_name)
                clean_embeddings.append((first_sample[0], first_sample[1], first_sample[2]))
                print(f"  [Dataset QC] Fallback restored primary sample for: {missing_name} from {first_sample[3]}")
        else:
            clean_embeddings = [(c[0], c[1], c[2]) for c in candidates]

        self.known_embeddings = clean_embeddings

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
            # Lọc các khuôn mặt có độ tin cậy tốt (score >= 0.45) để loại bỏ các khối texture/vải áo giả mạo
            valid_faces = [f for f in faces if float(f[-1]) >= 0.45]
            if not valid_faces:
                valid_faces = [f for f in faces if float(f[-1]) >= 0.30]
            if not valid_faces:
                valid_faces = list(faces)

            # Chọn khuôn mặt có diện tích lớn nhất (chủ thể chính ở tiền cảnh gần ống kính)
            face = max(valid_faces, key=lambda f: float(f[2]) * float(f[3]))
            aligned_face = self.recognizer.alignCrop(image, face)
            feature = self.recognizer.feature(aligned_face)
            return feature
        return None

    def is_near_recent_known_face(self, box: tuple[int, int, int, int], max_seconds: float = 4.0) -> bool:
        """Kiểm tra xem vị trí box này có phải vị trí một người quen/VIP vừa xuất hiện gần đây không."""
        current_time = time.time()
        ref_size = max(box[2], box[3], 30)
        for t_time, t_name, t_type, t_box in reversed(self._recent_known_tracks):
            if (current_time - t_time) <= max_seconds:
                iou = _compute_iou(box, t_box)
                dist = _compute_box_center_dist(box, t_box)
                if iou >= 0.12 or dist <= (ref_size * 1.4):
                    return True
        return False

    def recognize(self, frame: np.ndarray) -> list[RecognizedFace]:
        """Nhận diện tất cả khuôn mặt trong frame.
        Trả về danh sách RecognizedFace bao gồm tên, loại (FAMILY, ATTENTION, STRANGER) và box.
        """
        if not self.config.enabled:
            return []

        results: list[RecognizedFace] = []
        h, w = frame.shape[:2]

        current_time = time.time()
        # Dọn dẹp các track nhận diện người quen cũ hơn 5.0 giây
        self._recent_known_tracks = [
            t for t in self._recent_known_tracks if (current_time - t[0]) <= 5.0
        ][-30:]
        # Dọn dẹp các tracklet khuôn mặt không nhìn thấy quá 3.0 giây
        self._active_face_tracks = [
            trk for trk in self._active_face_tracks if (current_time - trk.last_seen) <= 3.0
        ][-20:]

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

        if faces is None or len(faces) == 0:
            return results

        if scale != 1.0:
            faces = faces.copy()
            faces[:, :14] = faces[:, :14] / scale

        for face in faces:
            bbox = face[:4].astype(int)
            fx, fy, fw, fh = bbox[0], bbox[1], bbox[2], bbox[3]

            # Bỏ qua các vật thể quá nhỏ (dưới 34px) hoặc tỷ lệ khung không giống khuôn mặt người
            if fw < 34 or fh < 34:
                continue
            aspect_ratio = fw / float(max(1, fh))
            if aspect_ratio < 0.45 or aspect_ratio > 1.80:
                continue

            det_score = float(face[14]) if len(face) > 14 else 0.85
            if det_score < 0.55:
                continue

            try:
                aligned_face = self.recognizer.alignCrop(frame, face)
                if aligned_face is None or aligned_face.size == 0:
                    continue
                query_feature = self.recognizer.feature(aligned_face)
            except Exception:
                continue

            # Phân tích theo từng người (Person-Level Aggregation)
            # Gom nhóm điểm của các ảnh mẫu theo từng danh tính và tính điểm đại diện Top-2
            threshold = max(0.36, float(getattr(self.config, "similarity_threshold", 0.38)))
            person_scores: dict[str, list[float]] = {}
            person_types: dict[str, PersonType] = {}
            for known_name, p_type, known_feature in self.known_embeddings:
                score = float(self.recognizer.match(query_feature, known_feature, cv2.FaceRecognizerSF_FR_COSINE))
                person_scores.setdefault(known_name, []).append(score)
                person_types[known_name] = p_type

            best_match_name = "Stranger"
            best_match_type = PersonType.STRANGER
            best_score = 0.0
            second_best_score = 0.0

            if person_scores:
                # Tính điểm đại diện bằng trung bình top-2 ảnh mẫu tốt nhất (tránh ảnh cực đoan gây nhiễu)
                aggregated_scores = []
                for name, scs in person_scores.items():
                    scs_sorted = sorted(scs, reverse=True)
                    if len(scs_sorted) >= 2:
                        person_rep_score = scs_sorted[0] * 0.65 + scs_sorted[1] * 0.35
                    else:
                        person_rep_score = scs_sorted[0]
                    aggregated_scores.append((person_rep_score, name))

                ranked = sorted(aggregated_scores, key=lambda x: x[0], reverse=True)
                best_score, best_match_name = ranked[0]
                best_match_type = person_types.get(best_match_name, PersonType.FAMILY)
                if len(ranked) > 1:
                    second_best_score = ranked[1][0]

            score_margin = best_score - second_best_score
            current_box = (int(max(0, fx)), int(max(0, fy)), int(max(0, fw)), int(max(0, fh)))

            # Tìm kiếm Tracklet tương ứng theo toạ độ không gian (Temporal Face Tracker)
            ref_size = max(current_box[2], current_box[3], 30)
            matched_track: _TrackedFace | None = None
            min_track_dist = float("inf")
            for trk in self._active_face_tracks:
                iou = _compute_iou(current_box, trk.box)
                dist = _compute_box_center_dist(current_box, trk.box)
                if iou >= 0.18 or dist <= ref_size * 1.3:
                    if dist < min_track_dist:
                        min_track_dist = dist
                        matched_track = trk

            if matched_track is not None:
                matched_track.box = current_box
                matched_track.last_seen = current_time

                # Ghi nhận vote của frame hiện tại
                vote_name = best_match_name if best_score >= threshold else "Stranger"
                matched_track.history.append((vote_name, best_score))
                if len(matched_track.history) > 10:
                    matched_track.history.pop(0)

                if matched_track.confirmed_name in ("", "Stranger"):
                    # CHỐNG NHẢY TÊN TỪ NGƯỜI LẠ: Bắt buộc >= 3 frame trong 5 frame gần nhất cùng công nhận
                    # và có khoảng cách điểm (margin) >= 0.04 so với người thứ 2
                    recent_known_votes = [n for n, _ in matched_track.history[-5:] if n != "Stranger"]
                    if (
                        best_score >= threshold
                        and recent_known_votes.count(best_match_name) >= 3
                        and score_margin >= 0.04
                    ):
                        matched_track.confirmed_name = best_match_name
                        matched_track.person_type = best_match_type
                        matched_track.last_known_seen_time = current_time
                        matched_track.consecutive_stranger_count = 0
                    elif best_score >= threshold + 0.10 and score_margin >= 0.08:
                        # Điểm tương đồng cực cao (rất chắc chắn, ví dụ nhìn thẳng camera)
                        matched_track.confirmed_name = best_match_name
                        matched_track.person_type = best_match_type
                        matched_track.last_known_seen_time = current_time
                        matched_track.consecutive_stranger_count = 0

                    final_name = matched_track.confirmed_name
                    final_type = matched_track.person_type
                    if final_name != "Stranger":
                        face_conf = min(0.99, max(0.50, float(best_score)))
                    else:
                        stranger_divergence = max(0.0, 1.0 - best_score)
                        face_conf = min(0.99, max(0.40, det_score * 0.7 + stranger_divergence * 0.3))
                else:
                    # Đã có danh tính người quen (ví dụ "An")
                    if best_score >= threshold and best_match_name == matched_track.confirmed_name:
                        # Tiếp tục nhận diện đúng người này
                        matched_track.last_known_seen_time = current_time
                        matched_track.consecutive_stranger_count = 0
                        final_name = matched_track.confirmed_name
                        final_type = matched_track.person_type
                        face_conf = min(0.99, max(0.50, float(best_score)))
                    elif best_score >= threshold and best_match_name != matched_track.confirmed_name:
                        # Tên khác đòi đổi danh tính (ví dụ từ An sang Bao) -> cần đa số tuyệt đối >= 5 frames
                        recent_votes = [n for n, _ in matched_track.history[-7:]]
                        if recent_votes.count(best_match_name) >= 5 and score_margin >= 0.05:
                            matched_track.confirmed_name = best_match_name
                            matched_track.person_type = best_match_type
                            matched_track.last_known_seen_time = current_time
                            matched_track.consecutive_stranger_count = 0
                        final_name = matched_track.confirmed_name
                        final_type = matched_track.person_type
                        face_conf = min(0.99, max(0.50, float(best_score)))
                    else:
                        # Điểm tụt dưới ngưỡng (do quay mặt, cúi đầu gõ phím, uống nước, ánh sáng thay đổi)
                        # STICKY IDENTITY: Giữ nguyên danh tính người quen trong 5.0 giây!
                        if (current_time - matched_track.last_known_seen_time <= 5.0) and best_score >= 0.16:
                            final_name = matched_track.confirmed_name
                            final_type = matched_track.person_type
                            face_conf = min(0.95, max(0.50, float(best_score + 0.15)))
                            matched_track.consecutive_stranger_count = 0
                        else:
                            matched_track.consecutive_stranger_count += 1
                            if matched_track.consecutive_stranger_count >= 15:
                                matched_track.confirmed_name = "Stranger"
                                matched_track.person_type = PersonType.STRANGER
                            final_name = matched_track.confirmed_name
                            final_type = matched_track.person_type
                            stranger_divergence = max(0.0, 1.0 - best_score)
                            face_conf = min(0.99, max(0.40, det_score * 0.7 + stranger_divergence * 0.3))
            else:
                # Tạo Tracklet mới cho khuôn mặt vừa xuất hiện
                # Nếu lần đầu xuất hiện có điểm rất cao (>= threshold + 0.06), xác nhận ngay, ngược lại để Stranger theo dõi tiếp
                is_confident = (best_score >= threshold + 0.06) and (score_margin >= 0.04)
                init_name = best_match_name if is_confident else "Stranger"
                init_type = best_match_type if is_confident else PersonType.STRANGER
                new_trk = _TrackedFace(
                    track_id=self._next_track_id,
                    box=current_box,
                    last_seen=current_time,
                    confirmed_name=init_name,
                    person_type=init_type,
                    history=[(best_match_name if best_score >= threshold else "Stranger", best_score)],
                    consecutive_stranger_count=0 if is_confident else 1,
                    last_known_seen_time=current_time if is_confident else 0.0,
                )
                self._next_track_id += 1
                self._active_face_tracks.append(new_trk)
                final_name = init_name
                final_type = init_type
                if is_confident:
                    face_conf = min(0.99, max(0.50, float(best_score)))
                else:
                    stranger_divergence = max(0.0, 1.0 - best_score)
                    face_conf = min(0.99, max(0.40, det_score * 0.7 + stranger_divergence * 0.3))

            if final_type != PersonType.STRANGER:
                self._recent_known_tracks.append((current_time, final_name, final_type, current_box))

            # Bỏ qua khuôn mặt bị cắt cụt sát mép màn hình nếu là người lạ chưa xác thực
            is_touching_edge = (fx <= 2 or fy <= 2 or (fx + fw) >= (w - 2) or (fy + fh) >= (h - 2))
            if final_name == "Stranger" and is_touching_edge and fw < 36:
                continue

            results.append(
                RecognizedFace(
                    name=final_name,
                    person_type=final_type,
                    box=current_box,
                    confidence=float(face_conf),
                )
            )

        # Dọn dẹp các track không hoạt động quá 4.0 giây
        self._active_face_tracks = [t for t in self._active_face_tracks if (current_time - t.last_seen) <= 4.0]

        # NMS Deduplication cải tiến: Loại bỏ các box trùng lặp (trán/cằm/lệch tâm), chỉ giữ lại box tin cậy nhất
        if len(results) > 1:
            results.sort(key=lambda r: r.confidence, reverse=True)
            filtered_results: list[RecognizedFace] = []
            for r in results:
                if not any(_is_duplicate_face(r.box, kept.box) for kept in filtered_results):
                    filtered_results.append(r)
            results = filtered_results

        return results
