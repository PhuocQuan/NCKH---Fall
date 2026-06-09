from __future__ import annotations

import os
import tkinter as tk
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import cv2
from PIL import Image, ImageTk

from src.ai_classifier import FallAIClassifier
from src.config import load_config
from src.decision_fusion import fuse_detection_with_ai
from src.event_logger import EventLogger
from src.feature_extractor import LandmarkFeatureBuffer
from src.fall_detector import FallDetector, FallState
from src.pose_estimator import PoseEstimator
from src.runtime_metrics import FPSCounter
from src.video_source import VideoSource


STATE_COLORS = {
    FallState.NORMAL: (70, 200, 90),
    FallState.LYING: (180, 180, 180),
    FallState.WARNING: (0, 190, 255),
    FallState.POSSIBLE_FALL: (0, 140, 255),
    FallState.FALLEN: (40, 40, 230),
    FallState.ALERT: (0, 0, 255),
}

ALARM_STATES = frozenset({FallState.POSSIBLE_FALL, FallState.FALLEN, FallState.ALERT})

STATE_HELP = {
    FallState.NORMAL: "Binh thuong: chua co dau hieu te nga.",
    FallState.LYING: "Dang nam: khong canh bao neu khong co chuyen dong giong te nga.",
    FallState.WARNING: "Canh bao nhe: co dau hieu bat thuong ngan.",
    FallState.POSSIBLE_FALL: "Nghi te nga: he thong se bao chuong va tiep tuc theo doi.",
    FallState.FALLEN: "Da phat hien te nga: dang dem thoi gian nam.",
    FallState.ALERT: "CANH BAO: da te nga va nam qua nguong thoi gian.",
}

STATUS_THEME = {
    "READY": ("#e8eef7", "#16345f"),
    "RUNNING": ("#e8f5e9", "#1b5e20"),
    "STOPPED": ("#eeeeee", "#222222"),
    "NO POSE": ("#fff8e1", "#7a4f00"),
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
        self.root.title("NCKH Fall Detection")
        self.root.geometry("1180x760")
        self.root.minsize(900, 620)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.source_var = tk.StringVar(value="0")
        self.config_var = tk.StringVar(value="configs/default.yaml")
        self.alert_long_lying_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="READY")
        self.detail_var = tk.StringVar(value="AI: disabled/no model | FPS: 0.0")
        self.state_help_var = tk.StringVar(value="Bam Start de bat dau demo.")

        self.config = None
        self.detector: FallDetector | None = None
        self.feature_buffer: LandmarkFeatureBuffer | None = None
        self.ai_classifier: FallAIClassifier | None = None
        self.estimator: PoseEstimator | None = None
        self.logger: EventLogger | None = None
        self.video: VideoSource | None = None
        self.fps_counter: FPSCounter | None = None
        self._photo: ImageTk.PhotoImage | None = None
        self._running = False
        self._after_id: str | None = None
        self._previous_state = FallState.NORMAL
        self._frames_since_bell = 60
        self._bell_interval_frames = 60
        self._input_widgets: list[tk.Widget] = []

        self._build_layout()

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = ttk.Frame(self.root, padding=12)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=0)
        main.rowconfigure(0, weight=1)

        video_frame = ttk.Frame(main)
        video_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        video_frame.columnconfigure(0, weight=1)
        video_frame.rowconfigure(0, weight=1)

        self.video_label = ttk.Label(video_frame, anchor="center", background="#111111")
        self.video_label.grid(row=0, column=0, sticky="nsew")

        side = ttk.Frame(main, width=360)
        side.grid(row=0, column=1, sticky="ns")
        side.columnconfigure(0, weight=1)

        ttk.Label(side, text="Dieu khien demo", font=("Segoe UI", 13, "bold")).grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 12),
        )

        ttk.Label(side, text="Nguon camera/video").grid(row=1, column=0, sticky="w")
        source_row = ttk.Frame(side)
        source_row.grid(row=2, column=0, sticky="ew", pady=(4, 4))
        source_row.columnconfigure(0, weight=1)
        self.source_entry = ttk.Entry(source_row, textvariable=self.source_var)
        self.source_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.video_button = ttk.Button(source_row, text="Chon video", command=self._choose_video)
        self.video_button.grid(row=0, column=1)

        source_buttons = ttk.Frame(side)
        source_buttons.grid(row=3, column=0, sticky="ew", pady=(0, 4))
        source_buttons.columnconfigure((0, 1), weight=1)
        self.webcam0_button = ttk.Button(
            source_buttons,
            text="Webcam 0",
            command=lambda: self._set_source("0"),
        )
        self.webcam0_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.webcam1_button = ttk.Button(
            source_buttons,
            text="Webcam 1",
            command=lambda: self._set_source("1"),
        )
        self.webcam1_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ttk.Label(
            side,
            text="Nhap 0/1 de dung webcam, duong dan video, hoac RTSP URL.",
            foreground="#555555",
            wraplength=330,
        ).grid(row=4, column=0, sticky="w", pady=(0, 10))

        ttk.Label(side, text="Config").grid(row=5, column=0, sticky="w")
        config_row = ttk.Frame(side)
        config_row.grid(row=6, column=0, sticky="ew", pady=(4, 4))
        config_row.columnconfigure(0, weight=1)
        self.config_entry = ttk.Entry(config_row, textvariable=self.config_var)
        self.config_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.config_button = ttk.Button(config_row, text="Chon file", command=self._choose_config)
        self.config_button.grid(row=0, column=1)
        ttk.Label(
            side,
            text="File YAML chua nguong te nga, kich thuoc camera, log va AI.",
            foreground="#555555",
            wraplength=330,
        ).grid(row=7, column=0, sticky="w", pady=(0, 10))

        self.demo_checkbox = ttk.Checkbutton(
            side,
            text="Demo: canh bao khi nam lau",
            variable=self.alert_long_lying_var,
        )
        self.demo_checkbox.grid(row=8, column=0, sticky="w", pady=(0, 4))
        ttk.Label(
            side,
            text="Chi dung de test nhanh chuong/log. Khi bao cao nen tat che do nay.",
            foreground="#777777",
            wraplength=330,
        ).grid(row=9, column=0, sticky="w", pady=(0, 12))

        buttons = ttk.Frame(side)
        buttons.grid(row=10, column=0, sticky="ew", pady=(0, 14))
        buttons.columnconfigure((0, 1, 2), weight=1)
        self.start_button = ttk.Button(buttons, text="Start", command=self.start)
        self.start_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.stop_button = ttk.Button(buttons, text="Stop", command=self.stop, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, sticky="ew", padx=4)
        self.reset_button = ttk.Button(buttons, text="Reset", command=self.reset, state=tk.DISABLED)
        self.reset_button.grid(row=0, column=2, sticky="ew", padx=(4, 0))

        ttk.Label(side, text="Trang thai").grid(row=11, column=0, sticky="w")
        self.status_label = tk.Label(
            side,
            textvariable=self.status_var,
            font=("Segoe UI", 22, "bold"),
            bg="#eeeeee",
            fg="#222222",
            anchor="w",
            padx=10,
            pady=8,
        )
        self.status_label.grid(
            row=12,
            column=0,
            sticky="ew",
            pady=(4, 6),
        )
        ttk.Label(side, textvariable=self.state_help_var, wraplength=330).grid(
            row=13,
            column=0,
            sticky="w",
            pady=(0, 4),
        )
        ttk.Label(side, textvariable=self.detail_var, wraplength=330).grid(
            row=14,
            column=0,
            sticky="w",
            pady=(0, 14),
        )

        log_header = ttk.Frame(side)
        log_header.grid(row=15, column=0, sticky="ew")
        log_header.columnconfigure(0, weight=1)
        ttk.Label(log_header, text="Event log").grid(row=0, column=0, sticky="w")
        ttk.Button(log_header, text="Xoa", command=self._clear_event_log).grid(
            row=0,
            column=1,
            padx=(4, 0),
        )
        ttk.Button(log_header, text="Mo CSV", command=self._open_event_log).grid(
            row=0,
            column=2,
            padx=(4, 0),
        )
        self.event_text = tk.Text(side, height=14, width=42, state=tk.DISABLED)
        self.event_text.grid(row=16, column=0, sticky="nsew", pady=(4, 0))
        side.rowconfigure(16, weight=1)

        self._input_widgets = [
            self.source_entry,
            self.video_button,
            self.webcam0_button,
            self.webcam1_button,
            self.config_entry,
            self.config_button,
            self.demo_checkbox,
        ]
        self._set_status("READY", "Bam Start de bat dau demo.")

    def start(self) -> None:
        if self._running:
            return

        try:
            self.config = load_config(self.config_var.get())
            detector_config = self.config.detector
            if self.alert_long_lying_var.get():
                detector_config = replace(detector_config, alert_on_long_lying_without_fall=True)

            self.detector = FallDetector(detector_config)
            self.feature_buffer = LandmarkFeatureBuffer(window_size=round(detector_config.assumed_fps))
            self.ai_classifier = FallAIClassifier(self.config.ai)
            self.estimator = PoseEstimator()
            self.logger = EventLogger(self.config.app.event_log_path)
            self.fps_counter = FPSCounter(window_size=round(detector_config.assumed_fps))
            self.video = VideoSource(
                source=self.source_var.get(),
                width=self.config.app.camera_width,
                height=self.config.app.camera_height,
            )
            self._bell_interval_frames = max(1, round(detector_config.assumed_fps * 2))
            self._frames_since_bell = self._bell_interval_frames
        except Exception as exc:
            self._release_runtime()
            messagebox.showerror("Khong khoi dong duoc", str(exc))
            return

        self._running = True
        self._set_inputs_enabled(False)
        self.start_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)
        self.reset_button.configure(state=tk.NORMAL)
        self._set_status("RUNNING", "Dang doc camera/video va phan tich pose realtime.")
        self._append_event(f"Started source={self.source_var.get()}")
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
        self._set_status("STOPPED", "Da dung camera/video. Bam Start de chay lai.")
        self.detail_var.set("AI: disabled/no model | FPS: 0.0")
        self._append_event("Stopped")

    def reset(self) -> None:
        if self.detector is not None:
            self.detector.reset()
        if self.feature_buffer is not None:
            self.feature_buffer.reset()
        if self.ai_classifier is not None:
            self.ai_classifier.reset()
        self._previous_state = FallState.NORMAL
        self._frames_since_bell = self._bell_interval_frames
        self._append_event("Reset detector")

    def close(self) -> None:
        self.stop()
        self.root.destroy()

    def _schedule_next_frame(self) -> None:
        self._after_id = self.root.after(1, self._process_frame)

    def _process_frame(self) -> None:
        if not self._running:
            return
        if not self._runtime_ready():
            self.stop()
            return

        assert self.video is not None
        assert self.estimator is not None
        assert self.detector is not None
        assert self.feature_buffer is not None
        assert self.ai_classifier is not None
        assert self.logger is not None
        assert self.fps_counter is not None
        assert self.config is not None

        ok, frame = self.video.read()
        if not ok:
            self._append_event("Video source ended/unavailable")
            self.stop()
            return

        fps = self.fps_counter.tick()
        points, pose_results = self.estimator.estimate(frame)
        if points:
            features = self.feature_buffer.append(points)
            ai_prediction = self.ai_classifier.predict(features)
            result = self.detector.update(points)
            result = fuse_detection_with_ai(result, ai_prediction, self.config.ai)

            if result.event_started:
                self.logger.write(result, source=self.source_var.get(), fps=fps)
                self._append_event(f"ALERT state={result.state.value} lie={result.lying_seconds:.1f}s")

            self._update_alarm(result.state)
            if self.config.app.draw_landmarks:
                self.estimator.draw(frame, pose_results)
            self._draw_overlay(frame, result, ai_prediction, fps)
            self._set_status(result.state.value.upper(), STATE_HELP[result.state])
            self.detail_var.set(
                f"AI: {ai_prediction.label} ({ai_prediction.probability:.2f}) "
                f"| mode={self.config.ai.decision_mode} | FPS: {fps:.1f}"
            )
        else:
            self.detector.reset()
            self.feature_buffer.reset()
            self.ai_classifier.reset()
            self._previous_state = FallState.NORMAL
            self._frames_since_bell = self._bell_interval_frames
            _draw_text(frame, "No pose detected", (20, 40), (180, 180, 180))
            _draw_text(frame, f"FPS: {fps:.1f}", (20, 80), (180, 180, 180))
            self._set_status("NO POSE", "Khong thay khung xuong nguoi. Hay dung trong khung hinh.")
            self.detail_var.set(f"AI: disabled/no model | FPS: {fps:.1f}")

        self._render_frame(frame)
        self._schedule_next_frame()

    def _runtime_ready(self) -> bool:
        return all(
            item is not None
            for item in [
                self.video,
                self.estimator,
                self.detector,
                self.feature_buffer,
                self.ai_classifier,
                self.logger,
                self.fps_counter,
                self.config,
            ]
        )

    def _release_runtime(self) -> None:
        if self.estimator is not None:
            self.estimator.close()
        if self.video is not None:
            self.video.release()
        self.detector = None
        self.feature_buffer = None
        self.ai_classifier = None
        self.estimator = None
        self.logger = None
        self.video = None
        self.fps_counter = None
        self.config = None

    def _set_source(self, source: str) -> None:
        self.source_var.set(source)

    def _choose_video(self) -> None:
        path = filedialog.askopenfilename(
            title="Chon video",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mov *.mkv"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.source_var.set(path)

    def _choose_config(self) -> None:
        path = filedialog.askopenfilename(
            title="Chon config YAML",
            filetypes=[
                ("YAML files", "*.yaml *.yml"),
                ("All files", "*.*"),
            ],
            initialdir="configs",
        )
        if path:
            self.config_var.set(path)

    def _set_inputs_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        for widget in self._input_widgets:
            widget.configure(state=state)

    def _set_status(self, status: str, help_text: str) -> None:
        self.status_var.set(status)
        self.state_help_var.set(help_text)
        background, foreground = STATUS_THEME.get(status, ("#eeeeee", "#222222"))
        self.status_label.configure(bg=background, fg=foreground)

    def _clear_event_log(self) -> None:
        self.event_text.configure(state=tk.NORMAL)
        self.event_text.delete("1.0", tk.END)
        self.event_text.configure(state=tk.DISABLED)

    def _open_event_log(self) -> None:
        log_path = Path("data/events.csv")
        if self.config is not None:
            log_path = Path(self.config.app.event_log_path)
        if not log_path.exists():
            messagebox.showinfo("Chua co log", f"Chua tim thay file: {log_path}")
            return
        try:
            os.startfile(log_path)  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror("Khong mo duoc log", str(exc))

    def _draw_overlay(self, frame, result, ai_prediction, fps: float) -> None:
        color = STATE_COLORS[result.state]
        label = (
            f"{result.state.value.upper()} | angle={result.torso_angle_deg:.1f} "
            f"| lie={result.lying_seconds:.1f}s | fps={fps:.1f}"
        )
        _draw_text(frame, label, (20, 40), color)
        if ai_prediction.enabled:
            ai_label = f"AI: {ai_prediction.label} ({ai_prediction.probability:.2f})"
        else:
            ai_label = "AI: disabled/no model"
        _draw_text(frame, ai_label, (20, 80), (180, 180, 180))
        if result.state in ALARM_STATES:
            height, width = frame.shape[:2]
            cv2.rectangle(frame, (0, 0), (width - 1, height - 1), color, 6)

    def _render_frame(self, frame) -> None:
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame_rgb)
        max_width = max(320, self.video_label.winfo_width())
        max_height = max(240, self.video_label.winfo_height())
        image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        self._photo = ImageTk.PhotoImage(image)
        self.video_label.configure(image=self._photo)

    def _update_alarm(self, state: FallState) -> None:
        if state in ALARM_STATES:
            if self._previous_state not in ALARM_STATES:
                self._frames_since_bell = 0
                self.root.bell()
            else:
                self._frames_since_bell += 1
                if self._frames_since_bell >= self._bell_interval_frames:
                    self._frames_since_bell = 0
                    self.root.bell()
        else:
            self._frames_since_bell = self._bell_interval_frames
        self._previous_state = state

    def _append_event(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.event_text.configure(state=tk.NORMAL)
        self.event_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.event_text.see(tk.END)
        self.event_text.configure(state=tk.DISABLED)


def _draw_text(frame, text: str, origin: tuple[int, int], color: tuple[int, int, int]) -> None:
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2, cv2.LINE_AA)


def main() -> None:
    root = tk.Tk()
    FallDetectionDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
