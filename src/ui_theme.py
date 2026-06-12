from __future__ import annotations

from src.fall_detector import FallState

PROFILE_DISPLAY = {
    "default": "Mac dinh",
    "elderly": "Nguoi gia",
    "child": "Tre nho",
    "pregnant": "Phu nu mang thai",
    "disabled": "Nguoi khuyet tat",
}

STATUS_DISPLAY = {
    "READY": "San sang",
    "RUNNING": "Dang chay",
    "STOPPED": "Da dung",
    "CHO POSE": "Cho nhan dien",
    "NO POSE": "Khong thay nguoi",
    "TRACKING": "Dang theo doi",
    "NORMAL": "Binh thuong",
    "LYING": "Dang nam",
    "WARNING": "Canh bao nhe",
    "POSSIBLE_FALL": "Nghi nga",
    "FALLEN": "Da nga",
    "ALERT": "CANH BAO",
}

STATE_HELP = {
    FallState.NORMAL: "Khong co dau hieu te nga.",
    FallState.LYING: "Dang nam — khong canh bao neu khong co chuyen dong nga.",
    FallState.WARNING: "Co dau hieu bat thuong ngan.",
    FallState.POSSIBLE_FALL: "Nghi nga — he thong dang theo doi.",
    FallState.FALLEN: "Da phat hien nga — dang dem thoi gian nam.",
    FallState.ALERT: "CANH BAO: da nga va nam qua nguong.",
}

STATUS_THEME = {
    "READY": ("#e8eef7", "#16345f"),
    "RUNNING": ("#e8f5e9", "#1b5e20"),
    "STOPPED": ("#eeeeee", "#222222"),
    "CHO POSE": ("#e3f2fd", "#0d47a1"),
    "NO POSE": ("#fff8e1", "#7a4f00"),
    "TRACKING": ("#fff3e0", "#e65100"),
    FallState.NORMAL.value.upper(): ("#e8f5e9", "#1b5e20"),
    FallState.LYING.value.upper(): ("#eeeeee", "#333333"),
    FallState.WARNING.value.upper(): ("#fff3e0", "#8a4b00"),
    FallState.POSSIBLE_FALL.value.upper(): ("#fff3e0", "#a13b00"),
    FallState.FALLEN.value.upper(): ("#ffebee", "#b71c1c"),
    FallState.ALERT.value.upper(): ("#b71c1c", "#ffffff"),
}

SYSTEM_HELP = {
    "READY": "Nhan Start hoac phim Space de bat dau.",
    "RUNNING": "Dang giam sat realtime.",
    "STOPPED": "Nhan Start de chay lai.",
    "CHO POSE": "Lui ra xa, de toan than trong khung hinh.",
    "NO POSE": "Khong thay khung xuong — hay dung ro truoc camera.",
    "TRACKING": "Tam mat pose — giu trang thai trong thoi gian ngan.",
}


def profile_combo_values() -> list[str]:
    return [f"{key} - {PROFILE_DISPLAY[key]}" for key in PROFILE_DISPLAY]


def profile_from_combo(selection: str) -> str:
    token = selection.strip().split(" - ", 1)[0].strip().lower()
    return token if token in PROFILE_DISPLAY else "default"


def profile_to_combo(profile: str) -> str:
    key = profile if profile in PROFILE_DISPLAY else "default"
    return f"{key} - {PROFILE_DISPLAY[key]}"


def ui_config_payload() -> dict:
    return {
        "status_display": STATUS_DISPLAY,
        "status_theme": {
            key: {"bg": colors[0], "fg": colors[1]}
            for key, colors in STATUS_THEME.items()
        },
        "state_help": {key.value: value for key, value in STATE_HELP.items()},
        "system_help": SYSTEM_HELP,
        "profiles": [
            {"id": key, "label": PROFILE_DISPLAY[key]}
            for key in PROFILE_DISPLAY
        ],
    }
