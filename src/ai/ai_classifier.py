"""
File: src/ai/ai_classifier.py
Chức năng chính: Chạy mô hình Học máy (Machine Learning/ONNX) để phân loại hành động.
Nhận chuỗi toạ độ xương và dự đoán xem có phải là "fall" (té ngã) hay không.

File liên kết:
- Load model từ: data/models/fall_model.onnx
- Được gọi bởi: app.py, pipeline.py
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from src.core.config import AIConfig
from src.detection.feature_extractor import PoseFeatures


@dataclass(frozen=True)
class AIPrediction:
    label: str
    probability: float
    enabled: bool


class FallAIClassifier:
    """Class quản lý việc dự đoán té ngã bằng mô hình Học máy (ONNX/Scikit-learn)."""
    def __init__(self, config: AIConfig) -> None:
        self.config = config
        self.model = None
        self._recent_probabilities: deque[float] = deque(maxlen=max(1, config.smoothing_frames))

        model_path = Path(config.model_path)
        if config.enabled and model_path.exists():
            import joblib

            self.model = joblib.load(model_path)

    @property
    def ready(self) -> bool:
        return self.config.enabled and self.model is not None

    def predict(self, features: PoseFeatures) -> AIPrediction:
        """
        Nhận vào bộ đặc trưng (PoseFeatures) trích xuất từ 30 frame.
        Sử dụng mô hình AI (RandomForest/SVM/LSTM) để dự đoán nhãn (fall / adl).
        """
        if not self.ready:
            return AIPrediction(label="disabled", probability=0.0, enabled=False)

        x = features.values.reshape(1, -1)
        probability = _fall_probability(self.model, x)
        self._recent_probabilities.append(probability)
        smoothed = float(np.mean(self._recent_probabilities))
        label = "fall" if smoothed >= self.config.alert_probability else "non_fall"
        return AIPrediction(label=label, probability=smoothed, enabled=True)


def _fall_probability(model, x) -> float:
    if hasattr(model, "predict_proba"):
        classes = list(model.classes_)
        probabilities = model.predict_proba(x)[0]
        if "fall" in classes:
            return float(probabilities[classes.index("fall")])
        if 1 in classes:
            return float(probabilities[classes.index(1)])
    prediction = model.predict(x)[0]
    return 1.0 if prediction in {"fall", 1, True} else 0.0
