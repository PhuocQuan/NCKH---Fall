from __future__ import annotations

import os
import tkinter as tk
from datetime import datetime
from pathlib import Path
from time import perf_counter
from tkinter import filedialog, messagebox, ttk

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

from src.alert_sound import FallAlarmTracker
from src.config import load_config
from src.desktop_view import (
    FramePresenter,
    UiRefreshGate,
    profile_combo_values,
    profile_from_combo,
    profile_to_combo,
    STATUS_DISPLAY,
)
from src.event_logger import EventLogger
from src.fall_detector import FallState
from src.pipeline import FallDetectionPipeline, build_pipeline_config
from src.snapshot import save_alert_snapshot
from src.ui_overlay import draw_no_pose, draw_status
from src.user_settings import (
    UserSettings,
    apply_user_settings,
    load_user_settings,
    save_user_settings,
)
from src.video_source import VideoSource, format_camera_label, scan_cameras

FALLEN_PROGRESS_STATES = frozenset(
    {FallState.POSSIBLE_FALL, FallState.FALLEN, FallState.ALERT}
)
DISPLAY_MIN_INTERVAL_SEC = 1.0 / 30.0

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


class FallDetectionDesktopApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("NCKH — Phat hien te nga")
        self.root.geometry("1240x780")
        self.root.minsize(980, 680)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        saved_settings = load_user_settings()
        self.source_var = tk.StringVar(value="0")
        self.config_var = tk.StringVar(value="configs/default.yaml")
        self.show_advanced_var = tk.BooleanVar(value=False)
        self.alert_long_lying_var = tk.BooleanVar(value=False)
        self.profile_var = tk.StringVar(value=profile_to_combo(saved_settings.profile))
        self.alert_seconds_var = tk.DoubleVar(value=saved_settings.alert_after_seconds)
        self.draw_landmarks_var = tk.BooleanVar(value=saved_settings.draw_landmarks)
        self.snapshot_on_alert_var = tk.BooleanVar(value=saved_settings.snapshot_on_alert)
        self.status_var = tk.StringVar(value=STATUS_DISPLAY["READY"])
        self.detail_var = tk.StringVar(value="San sang bat dau giam sat.")
        self.metrics_var = tk.StringVar(value="FPS: -- | Pose: -- ms")
        self.progress_label_var = tk.StringVar(value="")
        self.state_help_var = tk.StringVar(value="Nhan Start hoac phim Space de bat dau.")

        self.pipeline: FallDetectionPipeline | None = None
        self.video: VideoSource | None = None
        self.alarm: FallAlarmTracker | None = None
        self._presenter = FramePresenter()
        self._ui_gate = UiRefreshGate(interval_ms=120)
        self._last_render_at = 0.0
        self._running = False
        self._after_id: str | None = None
        self._input_widgets: list[tk.Widget] = []

        self._configure_style()
        self._build_layout()
        self._bind_shortcuts()
        self._show_video_placeholder()
        self._scan_cameras(silent=True)
        self._load_event_history()

    def _configure_style(self) -> None:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("Status.TLabel", font=("Segoe UI", 10))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        main.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        video_frame = ttk.Frame(main, padding=4)
        video_frame.columnconfigure(0, weight=1)
        video_frame.rowconfigure(1, weight=1)
        main.add(video_frame, weight=3)

        ttk.Label(video_frame, text="Camera giam sat", style="Title.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        self.video_label = tk.Label(
            video_frame,
            anchor="center",
            bg="#121212",
            fg="#bdbdbd",
            font=("Segoe UI", 11),
        )
        self.video_label.grid(row=1, column=0, sticky="nsew")

        side = ttk.Frame(main, padding=(8, 0, 0, 0))
        side.columnconfigure(0, weight=1)
        main.add(side, weight=1)

        self.notebook = ttk.Notebook(side)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        side.rowconfigure(0, weight=1)

        monitor_tab = ttk.Frame(self.notebook, padding=8)
        settings_tab = ttk.Frame(self.notebook, padding=8)
        log_tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(monitor_tab, text="Giam sat")
        self.notebook.add(settings_tab, text="Cai dat")
        self.notebook.add(log_tab, text="Nhat ky")

        self._build_monitor_tab(monitor_tab)
        self._build_settings_tab(settings_tab)
        self._build_log_tab(log_tab)
        self._set_status("READY", "Nhan Start hoac phim Space de bat dau.")

    def _build_monitor_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)

        source_row = ttk.Frame(parent)
        source_row.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        source_row.columnconfigure(0, weight=1)
        self.source_entry = ttk.Entry(source_row, textvariable=self.source_var)
        self.source_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.video_button = ttk.Button(source_row, text="Video", command=self._choose_video)
        self.video_button.grid(row=0, column=1)

        camera_row = ttk.Frame(parent)
        camera_row.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        camera_row.columnconfigure(0, weight=1)
        self.camera_combo = ttk.Combobox(camera_row, state="readonly")
        self.camera_combo.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.camera_combo.bind("<<ComboboxSelected>>", self._on_camera_selected)
        self.scan_camera_button = ttk.Button(
            camera_row, text="Quet", command=lambda: self._scan_cameras(silent=False)
        )
        self.scan_camera_button.grid(row=0, column=1)

        buttons = ttk.Frame(parent)
        buttons.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        buttons.columnconfigure((0, 1, 2), weight=1)
        self.start_button = ttk.Button(
            buttons, text="Start", style="Accent.TButton", command=self.start
        )
        self.start_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.stop_button = ttk.Button(buttons, text="Stop", command=self.stop, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, sticky="ew", padx=4)
        self.reset_button = ttk.Button(
            buttons, text="Reset (R)", command=self.reset, state=tk.DISABLED
        )
        self.reset_button.grid(row=0, column=2, sticky="ew", padx=(4, 0))

        ttk.Label(parent, text="Trang thai", style="Title.TLabel").grid(
            row=3, column=0, sticky="w"
        )
        self.status_label = tk.Label(
            parent,
            textvariable=self.status_var,
            font=("Segoe UI", 20, "bold"),
            bg="#eeeeee",
            fg="#222222",
            anchor="w",
            padx=12,
            pady=10,
        )
        self.status_label.grid(row=4, column=0, sticky="ew", pady=(6, 4))

        ttk.Label(parent, textvariable=self.state_help_var, wraplength=300).grid(
            row=5, column=0, sticky="w"
        )
        ttk.Label(parent, textvariable=self.detail_var, wraplength=300).grid(
            row=6, column=0, sticky="w", pady=(2, 8)
        )

        self.alert_progress = ttk.Progressbar(parent, maximum=100, mode="determinate")
        self.alert_progress.grid(row=7, column=0, sticky="ew", pady=(0, 4))
        ttk.Label(parent, textvariable=self.progress_label_var, wraplength=300).grid(
            row=8, column=0, sticky="w", pady=(0, 10)
        )

        metrics_frame = ttk.LabelFrame(parent, text="Hieu nang", padding=8)
        metrics_frame.grid(row=9, column=0, sticky="ew")
        ttk.Label(metrics_frame, textvariable=self.metrics_var, wraplength=280).grid(
            row=0, column=0, sticky="w"
        )

        self._input_widgets.extend(
            [
                self.source_entry,
                self.video_button,
                self.camera_combo,
                self.scan_camera_button,
            ]
        )

    def _build_settings_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)

        ttk.Label(parent, text="Profile").grid(row=0, column=0, sticky="w", pady=4)
        self.profile_combo = ttk.Combobox(
            parent,
            textvariable=self.profile_var,
            values=profile_combo_values(),
            state="readonly",
        )
        self.profile_combo.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=4)

        ttk.Label(parent, text="Canh bao sau").grid(row=1, column=0, sticky="w", pady=4)
        self.alert_seconds_spin = ttk.Spinbox(
            parent,
            from_=5,
            to=30,
            increment=1,
            textvariable=self.alert_seconds_var,
            width=8,
        )
        self.alert_seconds_spin.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=4)
        ttk.Label(parent, text="giay").grid(row=1, column=2, sticky="w", padx=(6, 0))

        self.landmarks_checkbox = ttk.Checkbutton(
            parent, text="Hien khung xuong", variable=self.draw_landmarks_var
        )
        self.landmarks_checkbox.grid(row=2, column=0, columnspan=3, sticky="w", pady=4)

        self.snapshot_checkbox = ttk.Checkbutton(
            parent, text="Luu anh khi canh bao", variable=self.snapshot_on_alert_var
        )
        self.snapshot_checkbox.grid(row=3, column=0, columnspan=3, sticky="w", pady=4)

        self.demo_checkbox = ttk.Checkbutton(
            parent,
            text="Demo: canh bao khi nam lau (chi de test)",
            variable=self.alert_long_lying_var,
        )
        self.demo_checkbox.grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 4))

        self.save_settings_button = ttk.Button(
            parent, text="Luu cai dat", command=self._save_current_settings
        )
        self.save_settings_button.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(10, 8))

        self.advanced_toggle = ttk.Checkbutton(
            parent,
            text="Hien cau hinh nang cao (YAML)",
            variable=self.show_advanced_var,
            command=self._toggle_advanced_config,
        )
        self.advanced_toggle.grid(row=6, column=0, columnspan=3, sticky="w")

        self.advanced_frame = ttk.Frame(parent)
        self.advanced_frame.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        self.advanced_frame.columnconfigure(0, weight=1)
        config_row = ttk.Frame(self.advanced_frame)
        config_row.grid(row=0, column=0, sticky="ew")
        config_row.columnconfigure(0, weight=1)
        self.config_entry = ttk.Entry(config_row, textvariable=self.config_var)
        self.config_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.config_button = ttk.Button(config_row, text="Chon", command=self._choose_config)
        self.config_button.grid(row=0, column=1)
        self.advanced_frame.grid_remove()

        self._settings_widgets = [
            self.profile_combo,
            self.alert_seconds_spin,
            self.landmarks_checkbox,
            self.snapshot_checkbox,
            self.demo_checkbox,
            self.save_settings_button,
            self.advanced_toggle,
            self.config_entry,
            self.config_button,
        ]
        self._input_widgets.extend(self._settings_widgets)

    def _build_log_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        log_header = ttk.Frame(parent)
        log_header.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        log_header.columnconfigure(0, weight=1)
        ttk.Label(log_header, text="Su kien gan day", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(log_header, text="Tai lai", command=self._reload_event_history).grid(
            row=0, column=1, padx=(4, 0)
        )
        ttk.Button(log_header, text="Xoa", command=self._clear_event_log).grid(
            row=0, column=2, padx=(4, 0)
        )
        ttk.Button(log_header, text="CSV", command=self._open_event_log).grid(
            row=0, column=3, padx=(4, 0)
        )

        self.event_text = tk.Text(parent, height=22, width=38, state=tk.DISABLED, wrap=tk.WORD)
        scroll = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.event_text.yview)
        self.event_text.configure(yscrollcommand=scroll.set)
        self.event_text.grid(row=1, column=0, sticky="nsew")
        scroll.grid(row=1, column=1, sticky="ns")

    def _bind_shortcuts(self) -> None:
        self.root.bind("<space>", self._on_space_key)
        self.root.bind("r", self._on_reset_key)
        self.root.bind("R", self._on_reset_key)

    def _on_space_key(self, _event: object = None) -> None:
        if self._running:
            self.stop()
        else:
            self.start()

    def _on_reset_key(self, _event: object = None) -> None:
        if self._running:
            self.reset()

    def _toggle_advanced_config(self) -> None:
        if self.show_advanced_var.get():
            self.advanced_frame.grid()
        else:
            self.advanced_frame.grid_remove()

    def _show_video_placeholder(self) -> None:
        self._presenter.show_placeholder(
            self.video_label,
            "Chua co luong video\nNhan Start de bat dau giam sat",
        )

    def _display_status_key(self, status: str) -> str:
        return STATUS_DISPLAY.get(status, status)

    def start(self) -> None:
        if self._running:
            return

        try:
            save_user_settings(self._current_user_settings())
            config = apply_user_settings(
                load_config(self.config_var.get()),
                self._current_user_settings(),
            )
            config = build_pipeline_config(
                config,
                alert_on_long_lying=self.alert_long_lying_var.get(),
            )
            source = self.source_var.get().strip()
            self.pipeline = FallDetectionPipeline(config, source=source)
            self.video = VideoSource(
                source=source,
                width=config.app.camera_width,
                height=config.app.camera_height,
            )
            self.alarm = FallAlarmTracker(
                beep_interval_frames=max(1, round(config.detector.assumed_fps * 2)),
                alarm_callback=self.root.bell,
            )
        except Exception as exc:
            self._release_runtime()
            messagebox.showerror("Loi khoi dong", str(exc))
            return

        self._running = True
        self._ui_gate = UiRefreshGate(interval_ms=120)
        self._last_render_at = 0.0
        self._set_inputs_enabled(False)
        self.start_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)
        self.reset_button.configure(state=tk.NORMAL)
        self._set_status("RUNNING", "Dang giam sat realtime.")
        self._append_event(f"Start nguon={source}")
        self._schedule_next_frame()

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        self._release_runtime()
        self._set_inputs_enabled(True)
        self.start_button.configure(state=tk.NORMAL)
        self.stop_button.configure(state=tk.DISABLED)
        self.reset_button.configure(state=tk.DISABLED)
        self._set_status("STOPPED", "Da dung. Nhan Start de chay lai.")
        self.detail_var.set("He thong da dung.")
        self.metrics_var.set("FPS: -- | Pose: -- ms")
        self._reset_alert_progress()
        self._show_video_placeholder()
        self._append_event("Stop")

    def reset(self) -> None:
        if self.pipeline is not None:
            self.pipeline.reset()
        if self.alarm is not None:
            self.alarm.reset()
        self._reset_alert_progress()
        self._append_event("Reset bo dem")

    def close(self) -> None:
        self.stop()
        self.root.destroy()

    def _schedule_next_frame(self) -> None:
        self._after_id = self.root.after(10, self._process_frame)

    def _process_frame(self) -> None:
        if not self._running or self.pipeline is None or self.video is None or self.alarm is None:
            return

        ok, frame = self.video.read()
        if not ok:
            self._append_event("Mat nguon video")
            self.stop()
            return

        pipeline_result = self.pipeline.process_frame(frame)
        config = self.pipeline.config
        status_key = self._current_status_key(pipeline_result)
        force_ui = pipeline_result.event_logged

        if pipeline_result.has_pose:
            assert pipeline_result.detection is not None
            if config.app.draw_landmarks:
                self.pipeline.estimator.draw(frame, pipeline_result.pose_results)
            self._draw_overlay(frame, pipeline_result)
            self.alarm.update(pipeline_result.detection.state)
        elif pipeline_result.pose_lost_grace and pipeline_result.detection is not None:
            self._draw_overlay(frame, pipeline_result)
            draw_no_pose(
                frame,
                pipeline_result.fps,
                grace=True,
                pose_ms=pipeline_result.pose_ms,
            )
            self.alarm.update(pipeline_result.detection.state)
        else:
            waiting_first_pose = self.pipeline.waiting_first_pose
            draw_no_pose(
                frame,
                pipeline_result.fps,
                waiting_first_pose=waiting_first_pose,
                pose_ms=pipeline_result.pose_ms,
            )
            self.alarm.reset()

        now = perf_counter()
        if now - self._last_render_at >= DISPLAY_MIN_INTERVAL_SEC:
            self._presenter.render(frame, self.video_label)
            self._last_render_at = now

        if self._ui_gate.should_refresh(status_key, force=force_ui):
            self._refresh_sidebar(pipeline_result, status_key)

        self._schedule_next_frame()

    def _current_status_key(self, pipeline_result) -> str:
        if pipeline_result.has_pose and pipeline_result.detection is not None:
            return pipeline_result.detection.state.value.upper()
        if pipeline_result.pose_lost_grace:
            return "TRACKING"
        if self.pipeline is not None and self.pipeline.waiting_first_pose:
            return "CHO POSE"
        return "NO POSE"

    def _refresh_sidebar(self, pipeline_result, status_key: str) -> None:
        if pipeline_result.has_pose and pipeline_result.detection is not None:
            detection = pipeline_result.detection
            self._set_status(
                detection.state.value.upper(),
                STATE_HELP[detection.state],
            )
            self._update_alert_progress(detection)
            self._update_detail(pipeline_result)
            return

        if pipeline_result.pose_lost_grace and pipeline_result.detection is not None:
            self._set_status("TRACKING", "Tam mat pose — giu trang thai trong thoi gian ngan.")
            self._update_alert_progress(pipeline_result.detection)
            self._update_detail(pipeline_result)
            return

        if status_key == "CHO POSE":
            self._set_status("CHO POSE", "Lui ra xa, de toan than trong khung hinh.")
            self.detail_var.set("Chua nhan dien duoc nguoi.")
        else:
            self._set_status("NO POSE", "Khong thay khung xuong — hay dung ro truoc camera.")
            self.detail_var.set("Mat pose.")
        self._update_metrics(pipeline_result)
        self._reset_alert_progress()

    def _release_runtime(self) -> None:
        if self.pipeline is not None:
            self.pipeline.close()
        if self.video is not None:
            self.video.release()
        self.pipeline = None
        self.video = None
        self.alarm = None

    def _current_user_settings(self) -> UserSettings:
        try:
            alert_after_seconds = float(self.alert_seconds_var.get())
        except (tk.TclError, ValueError):
            alert_after_seconds = 10.0
        return UserSettings(
            profile=profile_from_combo(self.profile_var.get()),
            alert_after_seconds=max(1.0, alert_after_seconds),
            draw_landmarks=self.draw_landmarks_var.get(),
            snapshot_on_alert=self.snapshot_on_alert_var.get(),
        )

    def _save_current_settings(self) -> None:
        path = save_user_settings(self._current_user_settings())
        messagebox.showinfo("Da luu", f"Cai dat da luu vao:\n{path}")

    def _scan_cameras(self, *, silent: bool = False) -> None:
        cameras = scan_cameras()
        if not cameras:
            if not silent:
                messagebox.showinfo("Quet camera", "Khong tim thay webcam.")
            return

        labels = [format_camera_label(info) for info in cameras]
        self.camera_combo["values"] = labels
        self.camera_combo.current(0)
        self.source_var.set(str(cameras[0].source))
        if not silent:
            messagebox.showinfo(
                "Quet camera",
                f"Tim thay {len(cameras)} webcam:\n" + "\n".join(labels),
            )

    def _on_camera_selected(self, _event: object = None) -> None:
        selection = self.camera_combo.get().strip()
        if selection:
            self.source_var.set(selection.split()[0])

    def _choose_video(self) -> None:
        path = filedialog.askopenfilename(
            title="Chon video",
            filetypes=[("Video", "*.mp4 *.avi *.mov *.mkv"), ("All", "*.*")],
        )
        if path:
            self.source_var.set(path)

    def _choose_config(self) -> None:
        path = filedialog.askopenfilename(
            title="Chon config YAML",
            filetypes=[("YAML", "*.yaml *.yml"), ("All", "*.*")],
            initialdir="configs",
        )
        if path:
            self.config_var.set(path)

    def _set_inputs_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        combo_state = "readonly" if enabled else tk.DISABLED
        for widget in self._input_widgets:
            if isinstance(widget, ttk.Combobox):
                widget.configure(state=combo_state)
            else:
                widget.configure(state=state)

    def _set_status(self, status: str, help_text: str) -> None:
        self.status_var.set(self._display_status_key(status))
        self.state_help_var.set(help_text)
        background, foreground = STATUS_THEME.get(status, ("#eeeeee", "#222222"))
        self.status_label.configure(bg=background, fg=foreground)

    def _update_alert_progress(self, detection) -> None:
        if self.pipeline is None:
            return
        alert_after = self.pipeline.config.detector.alert_after_seconds
        if detection.state in FALLEN_PROGRESS_STATES:
            progress = min(100.0, (detection.lying_seconds / alert_after) * 100.0)
            self.alert_progress["value"] = progress
            self.progress_label_var.set(
                f"Dem canh bao: {detection.lying_seconds:.1f}s / {alert_after:.0f}s"
            )
            return
        self._reset_alert_progress()

    def _reset_alert_progress(self) -> None:
        self.alert_progress["value"] = 0
        self.progress_label_var.set("")

    def _update_detail(self, pipeline_result) -> None:
        ai_prediction = pipeline_result.ai_prediction
        if ai_prediction is not None and ai_prediction.enabled:
            ai_text = (
                f"AI: {ai_prediction.label} ({ai_prediction.probability * 100:.0f}%)"
            )
        else:
            ai_text = "AI: chua bat"
        self.detail_var.set(f"{ai_text} | profile={self._current_user_settings().profile}")
        self._update_metrics(pipeline_result)

    def _update_metrics(self, pipeline_result) -> None:
        if self.pipeline is None:
            return
        pose_cfg = self.pipeline.config.pose
        self.metrics_var.set(
            f"FPS: {pipeline_result.fps:.1f} | Pose: {pipeline_result.pose_ms:.0f} ms "
            f"| {pose_cfg.input_width}x{pose_cfg.input_height} | model={pose_cfg.model_complexity}"
        )

    def _draw_overlay(self, frame, pipeline_result) -> None:
        assert pipeline_result.detection is not None
        draw_status(
            frame,
            pipeline_result.detection,
            pipeline_result.ai_prediction,
            self.pipeline.config.ai.decision_mode,
            pipeline_result.fps,
            pipeline_result.pose_ms,
        )
        if pipeline_result.event_logged:
            detection = pipeline_result.detection
            self._append_event(
                f"ALERT {detection.state.value} — nam {detection.lying_seconds:.1f}s"
            )
            if self.snapshot_on_alert_var.get():
                try:
                    snapshot_path = save_alert_snapshot(frame)
                    self._append_event(f"Anh: {snapshot_path.name}")
                except Exception as exc:
                    self._append_event(f"Loi luu anh: {exc}")

    def _clear_event_log(self) -> None:
        self.event_text.configure(state=tk.NORMAL)
        self.event_text.delete("1.0", tk.END)
        self.event_text.configure(state=tk.DISABLED)

    def _open_event_log(self) -> None:
        log_path = Path("data/events.csv")
        if self.pipeline is not None:
            log_path = Path(self.pipeline.config.app.event_log_path)
        elif self.config_var.get():
            try:
                log_path = Path(load_config(self.config_var.get()).app.event_log_path)
            except Exception:
                pass
        if not log_path.exists():
            messagebox.showinfo("Chua co log", f"Khong tim thay: {log_path}")
            return
        try:
            os.startfile(log_path)  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror("Loi", str(exc))

    def _append_event(self, message: str, *, timestamp: str | None = None) -> None:
        stamp = timestamp or datetime.now().strftime("%H:%M:%S")
        self.event_text.configure(state=tk.NORMAL)
        self.event_text.insert(tk.END, f"[{stamp}] {message}\n")
        self.event_text.see(tk.END)
        self.event_text.configure(state=tk.DISABLED)

    def _load_event_history(self, log_path: str | Path | None = None, *, limit: int = 15) -> None:
        if log_path is not None:
            path = Path(log_path)
        else:
            try:
                path = Path(load_config(self.config_var.get()).app.event_log_path)
            except Exception:
                path = Path("data/events.csv")
        if not path.exists():
            return

        rows = EventLogger(path).read_recent(limit)
        if not rows:
            return

        self._clear_event_log()
        for row in rows:
            timestamp = row.get("timestamp", "")
            state = row.get("state", "")
            source = row.get("source", "")
            lying = row.get("lying_seconds", "")
            stamp = timestamp[-8:] if len(timestamp) >= 8 else timestamp
            self._append_event(
                f"{source} | {state} | nam {lying}s",
                timestamp=stamp,
            )

    def _reload_event_history(self) -> None:
        log_path = None
        if self.pipeline is not None:
            log_path = self.pipeline.config.app.event_log_path
        self._load_event_history(log_path)


def main() -> None:
    root = tk.Tk()
    FallDetectionDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
