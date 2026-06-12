from __future__ import annotations

import importlib.util
import platform
import sys
from pathlib import Path

from src.config import load_config
from src.video_source import probe_camera


REQUIRED_MODULES = [
    "cv2",
    "mediapipe",
    "numpy",
    "yaml",
    "sklearn",
    "joblib",
    "pandas",
]


def main() -> None:
    config = load_config()
    print(f"Python: {sys.version.split()[0]} ({platform.platform()})")
    _check_modules()
    _check_paths(config.ai.model_path)
    _check_camera()


def _check_modules() -> None:
    print("\nPackages:")
    for module_name in REQUIRED_MODULES:
        status = "OK" if importlib.util.find_spec(module_name) else "MISSING"
        print(f"- {module_name}: {status}")


def _check_paths(model_path: str) -> None:
    print("\nProject paths:")
    for path in [
        Path("configs/default.yaml"),
        Path("data/videos"),
        Path("data/features"),
        Path("models"),
    ]:
        status = "OK" if path.exists() else "MISSING"
        print(f"- {path}: {status}")

    model = Path(model_path)
    status = "OK" if model.exists() else "not trained yet"
    print(f"- {model}: {status}")


def _check_camera() -> None:
    print("\nCamera:")
    info = probe_camera(0)
    if info is None:
        print("- camera 0: unavailable")
        return
    print(f"- camera 0: OK ({info.width}x{info.height}, fps={info.fps:.1f})")


if __name__ == "__main__":
    main()
