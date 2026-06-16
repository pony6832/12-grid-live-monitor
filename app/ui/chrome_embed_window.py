from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import ctypes
from ctypes import wintypes
import subprocess
import time
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.chrome_grid import find_chrome, normalize_url
from app.core.config import AppConfig, YOUTUBE_SLOT_COUNT, normalize_youtube_slots
from app.core.youtube_playback import build_watch_playback_url
from app.version import APP_NAME, APP_VERSION


GWL_STYLE = -16
WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU = 0x00080000
WM_CLOSE = 0x0010
SW_HIDE = 0
SW_SHOW = 5

user32 = ctypes.windll.user32


@dataclass(slots=True)
class EmbeddedChrome:
    process: subprocess.Popen[bytes]
    hwnd: int


class ChromeEmbedWindow(QMainWindow):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.config = config
        self.slots: list[ChromeEmbedSlot] = []
        self.link_rows: list[LinkEditorRow] = []

        self.sidebar_button = QPushButton("連結設定")
        self.save_reload_button = QPushButton("保存並重載")
        self.reload_button = QPushButton("重新載入啟用格")
        self.close_button = QPushButton("關閉Chrome")
        self.fullscreen_button = QPushButton("離開全螢幕")
        self.status_label = QLabel("使用真正 Chrome 視窗嵌入每個宮格")
        self.sidebar = QWidget()

        self._build_layout()
        self._connect_events()
        self.reload_enabled_slots()

    def _build_layout(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)

        self._build_sidebar()
        root_layout.addWidget(self.sidebar)

        main = QWidget()
        layout = QVBoxLayout(main)

        controls = QHBoxLayout()
        controls.addWidget(self.sidebar_button)
        controls.addWidget(self.save_reload_button)
        controls.addWidget(self.reload_button)
        controls.addWidget(self.close_button)
        controls.addWidget(self.fullscreen_button)
        controls.addWidget(self.status_label)
        controls.addStretch(1)
        layout.addLayout(controls)

        grid = QGridLayout()
        grid.setSpacing(8)
        slots = normalize_youtube_slots(self.config.youtube_slots)
        for index in range(YOUTUBE_SLOT_COUNT):
            slot = ChromeEmbedSlot(index, slots[index])
            self.slots.append(slot)
            row = index // 4
            column = index % 4
            grid.addWidget(slot, row, column)
            grid.setColumnStretch(column, 1)
            grid.setRowStretch(row, 1)
        layout.addLayout(grid, stretch=1)
        root_layout.addWidget(main, stretch=1)
        self.setCentralWidget(root)
        self.sidebar.hide()

    def _build_sidebar(self) -> None:
        self.sidebar.setFixedWidth(430)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.addWidget(QLabel("YouTube 連結設定"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        slots = normalize_youtube_slots(self.config.youtube_slots)
        for index, slot_config in enumerate(slots):
            row = LinkEditorRow(index, slot_config)
            self.link_rows.append(row)
            content_layout.addWidget(row)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        sidebar_layout.addWidget(scroll, stretch=1)

    def _connect_events(self) -> None:
        self.sidebar_button.clicked.connect(self.toggle_sidebar)
        self.save_reload_button.clicked.connect(self.save_and_reload)
        self.reload_button.clicked.connect(self.reload_enabled_slots)
        self.close_button.clicked.connect(self.close_all_chrome)
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)

    def toggle_sidebar(self) -> None:
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_button.setText("全螢幕")
            return
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
            slot.stop_chrome()
            slot.start_if_enabled()

    def close_all_chrome(self) -> None:
        for slot in self.slots:
            slot.stop_chrome()

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.close_all_chrome()
        event.accept()


class ChromeEmbedSlot(QFrame):
    def __init__(self, index: int, slot_config: dict[str, object]) -> None:
        super().__init__()
        self.index = index
        self.slot_config = slot_config
        self.chrome: EmbeddedChrome | None = None

        self.title_edit = QLineEdit(str(slot_config.get("title") or f"YouTube {index + 1}"))
        self.title_edit.setReadOnly(True)
        self.enabled_check = QCheckBox("啟用")
        self.enabled_check.setChecked(bool(slot_config.get("enabled", False)))
        self.enabled_check.setEnabled(False)
        self.status_label = QLabel("待命")
        self.reload_button = QPushButton("重載")
        self.container = QWidget()
        self.container.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._build_layout()
        self.resize_timer = QTimer(self)
        self.resize_timer.timeout.connect(self.fit_chrome)
        self.resize_timer.start(1000)

    def update_config(self, slot_config: dict[str, object]) -> None:
        self.slot_config = slot_config
        self.title_edit.setText(str(slot_config.get("title") or f"YouTube {self.index + 1}"))
        self.enabled_check.setChecked(bool(slot_config.get("enabled", False)))

    def _build_layout(self) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { border: 1px solid #333; background: #111; } "
            "QLineEdit { background: #202020; color: #f2f2f2; border: 1px solid #444; padding: 3px; } "
            "QLabel, QCheckBox { color: #f2f2f2; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        top = QHBoxLayout()
        top.addWidget(self.title_edit, stretch=1)
        top.addWidget(self.enabled_check)
        top.addWidget(self.status_label)
        top.addWidget(self.reload_button)
        layout.addLayout(top)
        layout.addWidget(self.container, stretch=1)
        self.reload_button.clicked.connect(self.reload_chrome)

    def reload_chrome(self) -> None:
        self.stop_chrome()
        self.start_if_enabled()

    def start_if_enabled(self) -> None:
        enabled = bool(self.slot_config.get("enabled", False))
        url = str(self.slot_config.get("url") or "").strip()
        if not enabled:
            self.status_label.setText("停用")
            return
        if not url:
            self.status_label.setText("缺 URL")
            return

        try:
            chrome = self._launch_and_embed(url)
        except Exception as exc:
            self.status_label.setText(f"失敗: {exc}")
            return

        self.chrome = chrome
        self.status_label.setText("Chrome嵌入")
        self.fit_chrome()

    def stop_chrome(self) -> None:
        if self.chrome is None:
            return
        if self.chrome.hwnd:
            user32.PostMessageW(wintypes.HWND(self.chrome.hwnd), WM_CLOSE, 0, 0)
        try:
            self.chrome.process.terminate()
        except Exception:
            pass
        self.chrome = None
        self.status_label.setText("已關閉")

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        self.fit_chrome()

    def fit_chrome(self) -> None:
        if self.chrome is None or not self.chrome.hwnd:
            return
        width = max(1, self.container.width())
        height = max(1, self.container.height())
        user32.MoveWindow(wintypes.HWND(self.chrome.hwnd), 0, 0, width, height, True)

    def _launch_and_embed(self, url: str) -> EmbeddedChrome:
        profile_dir = (Path("data/chrome_embedded_profiles") / f"slot_{self.index + 1}").resolve()
        profile_dir.mkdir(parents=True, exist_ok=True)
        chrome_path = find_chrome()
        args = [
            chrome_path,
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--disable-extensions",
            "--autoplay-policy=no-user-gesture-required",
            "--mute-audio",
            "--app=" + build_watch_playback_url(url),
            "--window-position=-32000,-32000",
            "--window-size=640,360",
        ]
        process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        hwnd = wait_for_process_window(process.pid, timeout_seconds=15)
        if not hwnd:
            raise RuntimeError("找不到 Chrome 視窗")

        parent_hwnd = int(self.container.winId())
        embed_window(hwnd, parent_hwnd)
        return EmbeddedChrome(process=process, hwnd=hwnd)


class LinkEditorRow(QFrame):
    def __init__(self, index: int, slot_config: dict[str, object]) -> None:
        super().__init__()
        self.index = index
        self.title_edit = QLineEdit(str(slot_config.get("title") or f"YouTube {index + 1}"))
        self.url_edit = QLineEdit(str(slot_config.get("url") or ""))
        self.enabled_check = QCheckBox("啟用")
        self.enabled_check.setChecked(bool(slot_config.get("enabled", False)))

        self._build_layout()

    def _build_layout(self) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel(f"{self.index + 1:02d}"))
        top.addWidget(self.title_edit, stretch=1)
        top.addWidget(self.enabled_check)
        layout.addLayout(top)
        layout.addWidget(self.url_edit)

    def to_config(self) -> dict[str, object]:
        return {
            "title": self.title_edit.text().strip() or f"YouTube {self.index + 1}",
            "url": self.url_edit.text().strip(),
            "enabled": self.enabled_check.isChecked(),
        }


def wait_for_process_window(process_id: int, timeout_seconds: float) -> int | None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        hwnd = find_window_for_process(process_id)
        if hwnd:
            return hwnd
        time.sleep(0.2)
    return None


def find_window_for_process(process_id: int) -> int | None:
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
        if pid.value == process_id:
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(enum_callback, 0)
    return found[0] if found else None


def embed_window(hwnd: int, parent_hwnd: int) -> None:
    style = user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_STYLE)
    style &= ~(WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU)
    style |= WS_CHILD | WS_VISIBLE
    user32.SetWindowLongW(wintypes.HWND(hwnd), GWL_STYLE, style)
    user32.SetParent(wintypes.HWND(hwnd), wintypes.HWND(parent_hwnd))
    user32.ShowWindow(wintypes.HWND(hwnd), SW_SHOW)
