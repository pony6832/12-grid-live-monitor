from __future__ import annotations

from pathlib import Path
import os
import subprocess
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.config import AppConfig, YOUTUBE_SLOT_COUNT, normalize_youtube_slots
from app.core.mpv_playback import build_mpv_args, find_mpv, find_ytdlp, send_mpv_command
from app.core.process_memory import process_working_set_bytes
from app.ui.chrome_embed_window import APP_QSS, LinkEditorRow
from app.version import APP_NAME, APP_VERSION


LOG_PATH = Path("data/light_player.log")

LIGHT_PLAYER_QSS = """
QToolButton {
    background: #182231;
    color: #e6edf6;
    border: 1px solid #2b3a4c;
    border-radius: 4px;
}
QToolButton:hover {
    background: #213047;
    border-color: #3b82f6;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #263345;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #2997d6;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 12px;
    margin: -4px 0;
    background: #e6edf6;
    border: 1px solid #2997d6;
    border-radius: 6px;
}
QComboBox {
    background: #182231;
    color: #e6edf6;
    padding: 4px 8px;
}
"""


class LightPlayerWindow(QMainWindow):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.slots: list[LightPlayerSlot] = []
        self.link_rows: list[LinkEditorRow] = []
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["480p", "720p", "1080p"])
        self.quality_combo.setCurrentText("720p")
        self.enabled_count_label = QLabel()
        self.memory_label = QLabel("0 MB")
        self.status_label = QLabel("mpv 輕量播放模式")
        self.sidebar_button = QPushButton("連結設定")
        self.save_button = QPushButton("保存並重載")
        self.reload_button = QPushButton("重新載入啟用格")
        self.stop_button = QPushButton("停止全部")
        self.fullscreen_button = QPushButton("離開全螢幕")
        self.sidebar = QWidget()

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setStyleSheet(APP_QSS + LIGHT_PLAYER_QSS)
        self._build_layout()
        self._connect_events()

        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._monitor_players)
        self.monitor_timer.start(2000)
        QTimer.singleShot(0, self.reload_enabled_slots)

    @property
    def quality(self) -> str:
        return self.quality_combo.currentText()

    def _build_layout(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self._build_sidebar()
        root_layout.addWidget(self.sidebar)

        main = QWidget()
        main.setObjectName("mainPanel")
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)
        main_layout.addWidget(self._build_top_bar())

        grid = QGridLayout()
        grid.setSpacing(7)
        for index, slot_config in enumerate(normalize_youtube_slots(self.config.youtube_slots)):
            slot = LightPlayerSlot(index, slot_config, self)
            self.slots.append(slot)
            grid.addWidget(slot, index // 4, index % 4)
            grid.setColumnStretch(index % 4, 1)
            grid.setRowStretch(index // 4, 1)
        main_layout.addLayout(grid, stretch=1)
        root_layout.addWidget(main, stretch=1)
        self.setCentralWidget(root)
        self.sidebar.hide()
        self._refresh_summary()

    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("topBar")
        bar.setFixedHeight(48)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(8)
        title = QLabel(APP_NAME)
        title.setObjectName("appTitle")
        version = QLabel(APP_VERSION)
        version.setObjectName("appMeta")
        self.enabled_count_label.setObjectName("metricValue")
        self.memory_label.setObjectName("metricValue")
        self.status_label.setObjectName("statusText")
        self.save_button.setObjectName("primaryButton")
        self.stop_button.setObjectName("dangerButton")
        for widget in [
            title, version, QLabel("啟用"), self.enabled_count_label,
            QLabel("畫質"), self.quality_combo, QLabel("mpv RAM"), self.memory_label,
            self.sidebar_button, self.save_button, self.reload_button,
            self.stop_button, self.fullscreen_button, self.status_label,
        ]:
            layout.addWidget(widget)
        layout.addStretch(1)
        return bar

    def _build_sidebar(self) -> None:
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(430)
        layout = QVBoxLayout(self.sidebar)
        layout.setContentsMargins(12, 12, 12, 12)
        title = QLabel("YouTube 連結設定")
        title.setObjectName("sidebarTitle")
        layout.addWidget(title)
        for index, slot_config in enumerate(normalize_youtube_slots(self.config.youtube_slots)):
            row = LinkEditorRow(index, slot_config)
            self.link_rows.append(row)
            layout.addWidget(row)
        layout.addStretch(1)
        close_button = QPushButton("收合")
        close_button.clicked.connect(self.toggle_sidebar)
        layout.addWidget(close_button)

    def _connect_events(self) -> None:
        self.sidebar_button.clicked.connect(self.toggle_sidebar)
        self.save_button.clicked.connect(self.save_and_reload)
        self.reload_button.clicked.connect(self.reload_enabled_slots)
        self.stop_button.clicked.connect(self.stop_all)
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        self.quality_combo.currentTextChanged.connect(self.reload_enabled_slots)

    def toggle_sidebar(self) -> None:
        self.sidebar.setVisible(not self.sidebar.isVisible())
        self.sidebar_button.setText("收合設定" if self.sidebar.isVisible() else "連結設定")

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_button.setText("全螢幕")
        else:
            self.showFullScreen()
            self.fullscreen_button.setText("離開全螢幕")

    def save_and_reload(self) -> None:
        self.config.youtube_slots = [row.to_config() for row in self.link_rows]
        self.config.save()
        for slot, slot_config in zip(self.slots, self.config.youtube_slots):
            slot.update_config(slot_config)
        self.reload_enabled_slots()
        self.status_label.setText("連結已保存並重載")

    def reload_enabled_slots(self) -> None:
        for slot in self.slots:
            slot.reload_player()
        self._refresh_summary()

    def stop_all(self) -> None:
        for slot in self.slots:
            slot.stop_player(manual=True)
        self.status_label.setText("全部播放器已停止")

    def _monitor_players(self) -> None:
        total_bytes = 0
        for slot in self.slots:
            slot.monitor()
            if slot.process is not None and slot.process.poll() is None:
                total_bytes += process_working_set_bytes(slot.process.pid)
        self.memory_label.setText(f"{total_bytes / 1024 / 1024:.0f} MB")

    def _refresh_summary(self) -> None:
        count = sum(1 for slot in self.slots if bool(slot.slot_config.get("enabled")))
        self.enabled_count_label.setText(f"{count}/12")

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.stop_all()
        event.accept()


class LightPlayerSlot(QFrame):
    def __init__(self, index: int, slot_config: dict[str, object], window: LightPlayerWindow) -> None:
        super().__init__()
        self.index = index
        self.slot_config = slot_config
        self.window = window
        self.process: subprocess.Popen[bytes] | None = None
        self.manual_stop = False
        self.restart_at = 0.0
        self.restart_count = 0
        self.slot_log_path = (Path("data/mpv_slots") / f"slot_{self.index + 1}.log").resolve()
        self.ipc_path = rf"\\.\pipe\12grid_mpv_{os.getpid()}_{self.index + 1}"
        self.muted = True
        self.volume = 50
        self.title_label = QLabel(str(slot_config.get("title") or f"YouTube {index + 1}"))
        self.status_dot = QLabel("●")
        self.status_label = QLabel("待命")
        self.reload_button = QPushButton("重載")
        self.sound_button = QToolButton()
        self.sound_button.setFixedSize(26, 24)
        self.sound_button.setToolTip("開啟聲音")
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.volume)
        self.volume_slider.setFixedWidth(62)
        self.volume_slider.setToolTip("音量 50%")
        self.volume_label = QLabel(str(self.volume))
        self.volume_label.setObjectName("slotStatus")
        self.volume_label.setFixedWidth(24)
        self.volume_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.volume_timer = QTimer(self)
        self.volume_timer.setSingleShot(True)
        self.volume_timer.setInterval(100)
        self.container = QWidget()
        self.container.setObjectName("chromeContainer")
        self.container.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._build_layout()

    def _build_layout(self) -> None:
        self.setObjectName("slotFrame")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = QFrame()
        header.setObjectName("slotHeader")
        header.setFixedHeight(32)
        top = QHBoxLayout(header)
        top.setContentsMargins(8, 4, 8, 4)
        index_label = QLabel(f"{self.index + 1:02d}")
        index_label.setObjectName("slotIndex")
        self.title_label.setObjectName("slotTitle")
        self.status_dot.setObjectName("statusDot")
        self.status_label.setObjectName("slotStatus")
        self.reload_button.setObjectName("slotReloadButton")
        self._refresh_sound_button()
        top.addWidget(index_label)
        top.addWidget(self.title_label, stretch=1)
        top.addWidget(self.status_dot)
        top.addWidget(self.status_label)
        top.addWidget(self.sound_button)
        top.addWidget(self.volume_slider)
        top.addWidget(self.volume_label)
        top.addWidget(self.reload_button)
        layout.addWidget(header)
        layout.addWidget(self.container, stretch=1)
        self.reload_button.clicked.connect(self.reload_player)
        self.sound_button.clicked.connect(self.toggle_sound)
        self.volume_slider.valueChanged.connect(self._schedule_volume_change)
        self.volume_timer.timeout.connect(self._apply_volume)

    def update_config(self, slot_config: dict[str, object]) -> None:
        self.slot_config = slot_config
        self.title_label.setText(str(slot_config.get("title") or f"YouTube {self.index + 1}"))

    def reload_player(self) -> None:
        self.stop_player(manual=False)
        self.start_if_enabled()

    def start_if_enabled(self) -> None:
        if not bool(self.slot_config.get("enabled")):
            self._set_status("停用", "#64748b")
            return
        url = str(self.slot_config.get("url") or "").strip()
        if not url:
            self._set_status("缺 URL", "#f59e0b")
            return
        try:
            self.muted = True
            self._refresh_sound_button()
            args = build_mpv_args(
                find_mpv(),
                find_ytdlp(),
                url,
                int(self.container.winId()),
                self.window.quality,
                self.ipc_path,
            )
            args.insert(-1, f"--volume={self.volume}")
            self.slot_log_path.parent.mkdir(parents=True, exist_ok=True)
            self.slot_log_path.unlink(missing_ok=True)
            args.insert(-1, f"--log-file={self.slot_log_path}")
            args.insert(-1, "--msg-level=all=warn,cplayer=info,vo=info,vd=info,ytdl_hook=info")
            self.process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.manual_stop = False
            self._set_status("載入中", "#38bdf8")
            self._write_log(f"slot {self.index + 1} started pid={self.process.pid} quality={self.window.quality}")
        except Exception as exc:
            self.process = None
            self._set_status("啟動失敗", "#ef4444")
            self._write_log(f"slot {self.index + 1} start failed: {exc}")

    def stop_player(self, manual: bool) -> None:
        self.manual_stop = manual
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None
        self.restart_at = 0.0
        self._set_status("已停止" if manual else "待命", "#94a3b8")

    def monitor(self) -> None:
        if self.process is not None and self.process.poll() is None:
            if self.status_label.text() == "載入中" and self._playback_confirmed():
                self._set_status("播放中", "#22c55e")
            return
        if self.process is not None:
            exit_code = self.process.poll()
            self.process = None
            if not self.manual_stop and bool(self.slot_config.get("enabled")):
                self.restart_count += 1
                self.restart_at = time.monotonic() + 5
                self._set_status(f"重連 {self.restart_count}", "#f59e0b")
                self._write_log(f"slot {self.index + 1} exited code={exit_code}; restart scheduled")
        if self.restart_at and time.monotonic() >= self.restart_at:
            self.restart_at = 0.0
            self.start_if_enabled()

    def toggle_sound(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        next_muted = not self.muted
        try:
            send_mpv_command(self.ipc_path, ["set_property", "mute", next_muted])
        except OSError as exc:
            self._write_log(f"slot {self.index + 1} mute control failed: {exc}")
            return
        self.muted = next_muted
        self._refresh_sound_button()

    def _schedule_volume_change(self, value: int) -> None:
        self.volume = value
        self.volume_label.setText(str(value))
        self.volume_slider.setToolTip(f"音量 {value}%")
        self.volume_timer.start()

    def _apply_volume(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        try:
            send_mpv_command(self.ipc_path, ["set_property", "volume", self.volume])
        except OSError as exc:
            self._write_log(f"slot {self.index + 1} volume control failed: {exc}")

    def _refresh_sound_button(self) -> None:
        icon_name = (
            QStyle.StandardPixmap.SP_MediaVolumeMuted
            if self.muted
            else QStyle.StandardPixmap.SP_MediaVolume
        )
        self.sound_button.setIcon(self.style().standardIcon(icon_name))
        self.sound_button.setToolTip("開啟聲音" if self.muted else "關閉聲音")

    def _playback_confirmed(self) -> bool:
        try:
            return "playback restart complete" in self.slot_log_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            return False

    def _set_status(self, text: str, color: str) -> None:
        self.status_label.setText(text)
        self.status_dot.setStyleSheet(f"color: {color};")

    @staticmethod
    def _write_log(message: str) -> None:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"[{stamp}] {message}\n")
