from src.ui_theme import STATUS_DISPLAY, ui_config_payload


def test_ui_config_has_alert_theme():
    payload = ui_config_payload()
    assert payload["status_display"]["READY"] == "San sang"
    assert payload["status_theme"]["ALERT"]["bg"] == "#b71c1c"
