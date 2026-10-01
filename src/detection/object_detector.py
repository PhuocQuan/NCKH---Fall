"""
File: src/detection/object_detector.py
Chức năng chính: Nhận diện vật phẩm, đồ dùng hỗ trợ và nội thất (ghế, giường, sofa, xe lăn).
Sử dụng mô hình YOLOv8-nano thông qua OpenCV DNN (chạy native CPU siêu nhẹ, không cần PyTorch/Ultralytics).

File liên kết:
- Sử dụng cấu hình từ: src/core/config.py (ObjectDetectionConfig)
- Gọi bởi: src/web/shared/pipeline.py, src/core/app.py
- Phối hợp với: src/detection/fall_detector.py (Spatial Context Fusion - phân biệt nằm trên giường vs ngã sàn)
"""
from __future__ import annotations

import logging
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.core.config import ObjectDetectionConfig

logger = logging.getLogger(__name__)

# Danh sách 80 lớp chuẩn MS COCO (chỉ mục 0-79)
COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light",
    "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone",
    "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush"
]

# Tên hiển thị tiếng Việt cho các vật dụng nội thất & hỗ trợ y tế
LABEL_VIETNAMESE = {
    "person": "Nguoi",
    "chair": "Ghe",
    "couch": "Sofa",
    "bed": "Giuong",
    "wheelchair": "Xe lan",
    "bench": "Ghe dai",
    "dining table": "Ban",
    "laptop": "Laptop",
    "cell phone": "Dien thoai",
}

# Màu sắc hiển thị BGR cho từng loại vật dụng
OBJECT_COLORS = {
    "person": (80, 200, 120),     # Xanh lục sáng Mint
    "bed": (230, 140, 40),        # Xanh dương hoàng gia / Lam
    "couch": (40, 165, 245),      # Cam sáng / Amber
    "chair": (160, 210, 50),      # Xanh lục bảo ngọc / Emerald
    "wheelchair": (210, 50, 210), # Tím hồng Magenta
    "bench": (200, 190, 80),      # Cyan trầm
    "dining table": (120, 180, 220), # Vàng kem / Nâu gỗ bàn
    "laptop": (220, 160, 50),     # Xanh ngọc
    "default": (180, 180, 180),   # Xám bạc
}

# Danh sách các mirror tin cậy tải mô hình YOLOv8n ONNX chuẩn
YOLOV8N_ONNX_MIRRORS = [
    "https://huggingface.co/Kalray/yolov8/resolve/main/yolov8n.onnx",
    "https://huggingface.co/cabelo/yolov8/resolve/main/yolov8n.onnx",
    "https://huggingface.co/peterfryd/yolov8n/resolve/main/yolov8n.onnx",
]
YOLOV8N_ONNX_URL = YOLOV8N_ONNX_MIRRORS[0]

# Tập hợp các vật thể bối cảnh an toàn (giường, sofa, ghế, bàn, laptop)
SAFE_CONTEXT_CLASSES = {"chair", "couch", "bed", "dining table", "laptop", "bench"}


def is_safe_context(label: str) -> bool:
    """Kiểm tra xem nhãn vật thể có thuộc nhóm bối cảnh an toàn hay không."""
    return label.lower().strip() in SAFE_CONTEXT_CLASSES


@dataclass(frozen=True)
class DetectedObject:
    """Class chứa thông tin vật thể được phát hiện."""
    label: str
    confidence: float
    box: tuple[int, int, int, int]  # (x, y, w, h) tính theo pixel
    normalized_box: tuple[float, float, float, float]  # (x1, y1, x2, y2) chuẩn hóa [0.0, 1.0]

    @property
    def display_name(self) -> str:
        return LABEL_VIETNAMESE.get(self.label, self.label.title())


def compute_box_overlap(
    box1: tuple[float, float, float, float],
    box2: tuple[float, float, float, float],
) -> float:
    """
    Tính tỷ lệ diện tích giao nhau so với diện tích của box1 (Person-Object Overlap Ratio).
    box định dạng: (x1, y1, x2, y2).
    Trả về giá trị từ 0.0 (không giao nhau) đến 1.0 (box1 nằm trọn trong box2).
    """
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter_area = inter_w * inter_h

    box1_area = max(1e-6, (box1[2] - box1[0]) * (box1[3] - box1[1]))
    return inter_area / box1_area


class ObjectDetector:
    """
    Module nhận diện vật thể & nội thất bằng OpenCV DNN (YOLOv8-nano ONNX).
    Hoạt động độc lập, nhẹ nhàng và an toàn (tự fallback nếu không có model).
    """
    _download_failed = False

    def __init__(self, config: ObjectDetectionConfig | None = None) -> None:
        self.config = config or ObjectDetectionConfig()
        self._net: Any | None = None
        self._ready = False
        self._simulated_objects: list[DetectedObject] | None = None

        if self.config.enabled:
            self._init_network()

    def _init_network(self) -> None:
        model_path = Path(self.config.model_path)
        if not model_path.exists() and not ObjectDetector._download_failed:
            # Tự động tạo thư mục chứa model nếu chưa tồn tại
            model_path.parent.mkdir(parents=True, exist_ok=True)
            import socket
            orig_timeout = socket.getdefaulttimeout()
            download_success = False
            for url in YOLOV8N_ONNX_MIRRORS:
                temp_path = model_path.with_name(f"{model_path.stem}_{abs(hash(url)) % 100000}.tmp")
                try:
                    socket.setdefaulttimeout(25.0)
                    logger.info(f"Dang tai mo hinh {model_path.name} tu {url}...")
                    req = urllib.request.Request(
                        url,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                    )
                    with urllib.request.urlopen(req, timeout=25.0) as resp, open(temp_path, "wb") as out_f:
                        while True:
                            chunk = resp.read(65536)
                            if not chunk:
                                break
                            out_f.write(chunk)

                    if temp_path.exists() and temp_path.stat().st_size > 1_000_000:
                        temp_path.replace(model_path)
                        download_success = True
                        logger.info(f"Da tai thanh cong mo hinh {model_path.name} tu {url}")
                        break
                    else:
                        if temp_path.exists():
                            temp_path.unlink()
                except Exception as dl_err:
                    logger.warning(f"Khong the tu dong tai YOLOv8n ONNX tu {url}: {dl_err}")
                    if temp_path.exists():
                        try:
                            temp_path.unlink()
                        except Exception:
                            pass
                finally:
                    socket.setdefaulttimeout(orig_timeout)

            if not download_success and not model_path.exists():
                ObjectDetector._download_failed = True
                logger.warning("Khong the tu dong tai YOLOv8n ONNX tu cac mirror. He thong se chay che do phong thu.")

        if model_path.exists():
            try:
                self._net = cv2.dnn.readNetFromONNX(str(model_path))
                # Tận dụng CPU đa nhân tối ưu
                self._net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                self._net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                self._ready = True
                logger.info(f"Da nap thanh cong mo hinh Object Detection: {model_path}")
            except Exception as net_err:
                logger.error(f"Loi khi nap mo hinh ONNX {model_path}: {net_err}")
                self._ready = False
        else:
            self._ready = False

    def is_ready(self) -> bool:
        return self._ready or (self._simulated_objects is not None)

    def set_simulated_objects(self, objects: list[DetectedObject] | None) -> None:
        """Dùng cho kiểm thử mô phỏng kịch bản (Unit test / Simulation)."""
        self._simulated_objects = objects

    def detect(self, frame_bgr: np.ndarray) -> list[DetectedObject]:
        """
        Nhận diện các vật phẩm trong khung hình.
        Trả về danh sách DetectedObject thuộc các lớp trong target_classes.
        """
        if self._simulated_objects is not None:
            return list(self._simulated_objects)

        if not self.config.enabled or not self._ready or self._net is None or frame_bgr is None:
            return []

        h_img, w_img = frame_bgr.shape[:2]
        if h_img == 0 or w_img == 0:
            return []

        try:
            # YOLOv8 input size 640x640, scale 1/255.0, RGB format
            blob = cv2.dnn.blobFromImage(
                frame_bgr,
                scalefactor=1.0 / 255.0,
                size=(640, 640),
                mean=[0, 0, 0],
                swapRB=True,
                crop=False,
            )
            self._net.setInput(blob)
            preds = self._net.forward()

            # YOLOv8 output shape: (1, 84, 8400) -> reshape/transpose sang (8400, 84)
            if len(preds.shape) == 3:
                preds = np.transpose(preds[0], (1, 0))  # (8400, 84)

            boxes: list[list[int]] = []
            confidences: list[float] = []
            class_ids: list[int] = []

            x_scale = w_img / 640.0
            y_scale = h_img / 640.0

            target_class_set = set(self.config.target_classes)

            for i in range(preds.shape[0]):
                row = preds[i]
                scores = row[4:]
                class_id = int(np.argmax(scores))
                score = float(scores[class_id])

                if score < self.config.confidence_threshold:
                    continue

                if class_id >= len(COCO_CLASSES):
                    continue

                class_name = COCO_CLASSES[class_id]
                if class_name not in target_class_set and "all" not in target_class_set:
                    continue

                # Tọa độ bounding box từ YOLOv8: cx, cy, w, h trong không gian 640x640
                cx, cy, w, h = row[0], row[1], row[2], row[3]
                x1 = int((cx - 0.5 * w) * x_scale)
                y1 = int((cy - 0.5 * h) * y_scale)
                box_w = int(w * x_scale)
                box_h = int(h * y_scale)

                boxes.append([x1, y1, box_w, box_h])
                confidences.append(score)
                class_ids.append(class_id)

            if not boxes:
                return []

            indices = cv2.dnn.NMSBoxes(
                boxes,
                confidences,
                score_threshold=self.config.confidence_threshold,
                nms_threshold=self.config.nms_threshold,
            )

            results: list[DetectedObject] = []
            if len(indices) > 0:
                indices = indices.flatten()
                for idx in indices:
                    x, y, w, h = boxes[idx]
                    conf = confidences[idx]
                    c_id = class_ids[idx]
                    lbl = COCO_CLASSES[c_id]

                    nx1 = max(0.0, min(1.0, x / w_img))
                    ny1 = max(0.0, min(1.0, y / h_img))
                    nx2 = max(0.0, min(1.0, (x + w) / w_img))
                    ny2 = max(0.0, min(1.0, (y + h) / h_img))

                    results.append(
                        DetectedObject(
                            label=lbl,
                            confidence=round(conf, 3),
                            box=(x, y, w, h),
                            normalized_box=(nx1, ny1, nx2, ny2),
                        )
                    )

            return results
        except Exception as det_err:
            logger.error(f"Loi khi chay Object Detection: {det_err}")
            return []

    def draw(self, frame_bgr: np.ndarray, objects: list[DetectedObject], skip_labels: set[str] | None = None) -> None:
        """Vẽ bounding box và nhãn tên các vật thể lên khung hình."""
        if not objects or frame_bgr is None:
            return

        h_f, w_f = frame_bgr.shape[:2]

        for obj in objects:
            if skip_labels and obj.label in skip_labels:
                continue
            x, y, w, h = obj.box
            color = OBJECT_COLORS.get(obj.label, OBJECT_COLORS["default"])

            # Giới hạn bounding box trong khung hình
            x1 = max(0, x)
            y1 = max(0, y)
            x2 = min(w_f - 1, x + w)
            y2 = min(h_f - 1, y + h)

            # Vẽ khung viền
            cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), color, 2)

            # Vẽ nhãn tên có nền tối mờ
            label_text = f"{obj.display_name} {int(obj.confidence * 100)}%"
            (tw, th), baseline = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)

            lbl_y1 = max(0, y1 - th - 6)
            lbl_y2 = y1
            lbl_x2 = min(w_f - 1, x1 + tw + 8)

            cv2.rectangle(frame_bgr, (x1, lbl_y1), (lbl_x2, lbl_y2), color, -1)
            cv2.putText(
                frame_bgr,
                label_text,
                (x1 + 4, lbl_y2 - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
