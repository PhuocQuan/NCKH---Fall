import numpy as np

from src.feature_extractor import FEATURE_NAMES, LandmarkFeatureBuffer
from tests.test_fall_detector import lying_pose, standing_pose


def test_feature_extractor_returns_stable_vector_size():
    buffer = LandmarkFeatureBuffer(window_size=3)

    buffer.append(standing_pose())
    features = buffer.append(lying_pose())

    assert features.names == FEATURE_NAMES
    assert features.values.shape == (len(FEATURE_NAMES),)
    assert np.isfinite(features.values).all()
