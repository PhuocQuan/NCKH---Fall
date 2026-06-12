import pytest

from src.cloud_db import reset_engine_for_tests


@pytest.fixture(autouse=True)
def isolate_local_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests always use YAML/files — never production Supabase."""
    monkeypatch.setenv("AUTH_STORAGE", "yaml")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    reset_engine_for_tests()
