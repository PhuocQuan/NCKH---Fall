import numpy as np

from src.core.config import FaceConfig
from src.face.face_recognizer import FaceRecognizer, PersonType


def test_filename_parsing(tmp_path):
    config = FaceConfig(enabled=True, known_faces_dir=str(tmp_path))
    recognizer = FaceRecognizer(config)

    name, ptype = recognizer.parse_filename("OngNoi_ATTENTION.jpg")
    assert name == "OngNoi"
    assert ptype == PersonType.ATTENTION

    name, ptype = recognizer.parse_filename("Me_FAMILY.png")
    assert name == "Me"
    assert ptype == PersonType.FAMILY

    name, ptype = recognizer.parse_filename("BaNoi.jpeg")
    assert name == "BaNoi"
    assert ptype == PersonType.FAMILY


def test_recognize_empty_frame(tmp_path):
    config = FaceConfig(enabled=True, known_faces_dir=str(tmp_path))
    recognizer = FaceRecognizer(config)

    blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = recognizer.recognize(blank_frame)
    assert isinstance(results, list)
    assert len(results) == 0
