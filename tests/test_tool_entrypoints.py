import importlib


def test_evaluate_videos_module_imports():
    module = importlib.import_module("src.evaluate_videos")
    assert callable(module.main)


def test_build_feature_dataset_module_imports():
    module = importlib.import_module("src.build_feature_dataset")
    assert callable(module.main)


def test_api_server_module_imports():
    module = importlib.import_module("src.api_server")
    assert callable(module.main)
