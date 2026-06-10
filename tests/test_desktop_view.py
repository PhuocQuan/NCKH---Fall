from src.desktop_view import (
    UiRefreshGate,
    profile_from_combo,
    profile_to_combo,
)


def test_profile_combo_roundtrip():
    assert profile_from_combo("elderly - Nguoi gia") == "elderly"
    assert profile_to_combo("child").startswith("child - ")


def test_ui_refresh_gate_force_on_status_change():
    gate = UiRefreshGate(interval_ms=1000)
    assert gate.should_refresh("NORMAL", force=False) is True
    assert gate.should_refresh("NORMAL", force=False) is False
    assert gate.should_refresh("ALERT", force=False) is True
