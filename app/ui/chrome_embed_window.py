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

from app.chrome_grid import find_chrome
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


APP_QSS = """
QMainWindow {
    background: #070a0f;
}
QWidget#root {
    background: #070a0f;
    color: #d7dee8;
    font-family: "Microsoft JhengHei UI", "Segoe UI", Arial, sans-serif;
    font-size: 12px;
}
QWidget#mainPanel {
    background: #070a0f;
}
QFrame#topBar {
    background: #0d121a;
    border: 1px solid #1a2430;
    border-radius: 6px;
}
QLabel#appTitle {
    color: #f3f7fb;
    font-size: 16px;
    font-weight: 700;
}
QLabel#appMeta, QLabel#statusText, QLabel#metricLabel {
    color: #8f9bad;
}
QLabel#metricValue {
    color: #36d399;
    font-weight: 700;
}
QPushButton {
    background: #182231;
    color: #e6edf6;
    border: 1px solid #2b3a4c;
    border-radius: 5px;
    padding: 5px 10px;
    min-height: 22px;
}
QPushButton:hover {
    background: #213047;
    border-color: #3b82f6;
}
QPushButton:pressed {
    background: #111827;
}
QPushButton:disabled {
    background: #111827;
    color: #5b6675;
    border-color: #1f2937;
}
QPushButton#primaryButton {
    background: #14532d;
    border-color: #22c55e;
}
QPushButton#dangerButton {
    background: #451a1a;
    border-color: #ef4444;
}
QFrame#slotFrame {
    background: #05070a;
    border: 1px solid #202a36;
    border-radius: 6px;
}
QFrame#slotFrame[active="true"] {
    border-color: #2d5f43;
}
QFrame#slotHeader {
    background: #0c1118;
    border: 0;
    border-bottom: 1px solid #1f2937;
    border-radius: 0;
}
QLabel#slotIndex {
    color: #64748b;
    font-size: 11px;
    font-weight: 700;
}
QLabel#slotTitle {
    color: #e5edf8;
    font-size: 12px;
    font-weight: 600;
}
QLabel#statusDot {
    font-size: 13px;
}
QLabel#slotStatus {
    color: #9ca3af;
    font-size: 11px;
}
QPushButton#slotReloadButton {
    padding: 2px 8px;
    min-height: 18px;
    font-size: 11px;
}
QWidget#chromeContainer {
    background: #000000;
}
QWidget#sidebar {
    background: #0d121a;
    border-right: 1px solid #1f2937;
}
QLabel#sidebarTitle {
    color: #f3f7fb;
    font-size: 15px;
    font-weight: 700;
}
QScrollArea {
    background: transparent;
    border: 0;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
QFrame#linkRow {
    background: #101722;
    border: 1px solid #223044;
    border-radius: 6px;
}
QLabel#rowIndex {
    background: #1f2937;
    color: #bfdbfe;
    border-radius: 4px;
    padding: 3px 6px;
    font-weight: 700;
}
QLineEdit {
    background: #060a10;
    color: #e5edf8;
    border: 1px solid #263345;
    border-radius: 4px;
    padding: 4px 6px;
    selection-background-color: #2563eb;
}
QLineEdit:read-only {
    background: transparent;
    border: 0;
    color: #e5edf8;
    font-weight: 600;
}
QLineEdit:focus {
    border-color: #3b82f6;
}
QCheckBox {
    color: #cbd5e1;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
}
"""


@dataclass(slots=True)
class EmbeddedChrome:
    process: subprocess.Popen[bytes]
    hwnd: int


class ChromeEmbedWindow(QMainWindow):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setStyleSheet(APP_QSS)
        self.config = config
        self.slots: list[ChromeEmbedSlot] = []
        self.link_rows: list[LinkEditorRow] = []

        self.sidebar_button = QPushButton("連結設定")
        self.save_reload_button = QPushButton("保存並重載")
        self.reload_button = QPushButton("重新載入啟用格")
        self.close_button = QPushButton("關閉Chrome")
        self.fullscreen_button = QPushButton("離開全螢幕")
        self.enabled_count_label = QLabel()
        self.status_label = QLabel("使用真正 Chrome 視窗嵌入每個宮格")
        self.sidebar = QWidget()

        self._build_layout()
        self._connect_events()
        self.reload_enabled_slots()

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
        layout = QVBoxLayout(main)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        layout.addWidget(self._build_top_bar())

        grid = QGridLayout()
        grid.setSpacing(7)
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
        self._refresh_summary()

    def _build_top_bar(self) -> QFrame:
        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_bar.setFixedHeight(48)
        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(8)

        title = QLabel(APP_NAME)
        title.setObjectName("appTitle")
        version = QLabel(APP_VERSION)
        version.setObjectName("appMeta")
        metric_label = QLabel("啟用")
        metric_label.setObjectName("metricLabel")
        self.enabled_count_label.setObjectName("metricValue")
        self.status_label.setObjectName("statusText")

        self.save_reload_button.setObjectName("primaryButton")
        self.close_button.setObjectName("dangerButton")

        layout.addWidget(title)
        layout.addWidget(version)
        layout.addSpacing(14)
        layout.addWidget(metric_label)
        layout.addWidget(self.enabled_count_label)
        layout.addSpacing(14)
        layout.addWidget(self.sidebar_button)
        layout.addWidget(self.save_reload_button)
        layout.addWidget(self.reload_button)
        layout.addWidget(self.close_button)
        layout.addWidget(self.fullscreen_button)
        layout.addWidget(self.status_label)
        layout.addStretch(1)
        return top_bar

    def _build_sidebar(self) -> None:
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(430)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(12, 12, 12, 12)
        sidebar_layout.setSpacing(10)
        title = QLabel("YouTube 連結設定")
        title.setObjectName("sidebarTitle")
        hint = QLabel("勾選要監看的頻道，保存後會重新載入啟用格。")
        hint.setObjectName("appMeta")
        sidebar_layout.addWidget(title)
        sidebar_layout.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(7)
        slots = normalize_youtube_slots(self.config.youtube_slots)
        for index, slot_config in enumerate(slots):
            row = LinkEditorRow(index, slot_config)
            self.link_rows.append(row)
            content_layout.addWidget(row)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        sidebar_layout.addWidget(scroll, stretch=1)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        side_save_button = QPushButton("保存並重載")
        side_save_button.setObjectName("primaryButton")
        side_close_button = QPushButton("收合")
        side_save_button.clicked.connect(self.save_and_reload)
        side_close_button.clicked.connect(self.toggle_sidebar)
        footer.addWidget(side_save_button)
        footer.addWidget(side_close_button)
        sidebar_layout.addLayout(footer)

    def _connect_events(self) -> None:
        self.sidebar_button.clicked.connect(self.toggle_sidebar)
        self.save_reload_button.clicked.connect(self.save_and_reload)
        self.reload_button.clicked.connect(self.reload_enabled_slots)
        self.close_button.clicked.connect(self.close_all_chrome)
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)

    def toggle_sidebar(self) -> None:
        self.sidebar.setVisible(not self.sidebar.isVisible())
        self.sidebar_button.setText("收合設定" if self.sidebar.isVisible() else "連結設定")

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
        self._refresh_summary()

    def reload_enabled_slots(self) -> None:
        for slot in self.slots:
            slot.stop_chrome()
            slot.start_if_enabled()
        self._refresh_summary()

    def close_all_chrome(self) -> None:
        for slot in self.slots:
            slot.stop_chrome()
        self.status_label.setText("Chrome 已全部關閉")

    def _refresh_summary(self) -> None:
        enabled_count = sum(1 for slot in normalize_youtube_slots(self.config.youtube_slots) if slot.get("enabled"))
        self.enabled_count_label.setText(f"{enabled_count}/12")

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
        self.status_dot = QLabel("●")
        self.reload_button = QPushButton("重載")
        self.container = QWidget()
        self.container.setObjectName("chromeContainer")
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
        self._apply_active_style()

    def _build_layout(self) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("slotFrame")
        self._apply_active_style()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("slotHeader")
        header.setFixedHeight(32)
        top = QHBoxLayout(header)
        top.setContentsMargins(8, 4, 8, 4)
        top.setSpacing(6)
        slot_index = QLabel(f"{self.index + 1:02d}")
        slot_index.setObjectName("slotIndex")
        self.title_edit.setObjectName("slotTitle")
        self.status_dot.setObjectName("statusDot")
        self.status_label.setObjectName("slotStatus")
        self.reload_button.setObjectName("slotReloadButton")
        top.addWidget(slot_index)
        top.addWidget(self.title_edit, stretch=1)
        top.addWidget(self.status_dot)
        top.addWidget(self.status_label)
        top.addWidget(self.reload_button)
        layout.addWidget(header)
        layout.addWidget(self.container, stretch=1)
        self.reload_button.clicked.connect(self.reload_chrome)

    def reload_chrome(self) -> None:
        self.stop_chrome()
        self.start_if_enabled()

    def start_if_enabled(self) -> None:
        enabled = bool(self.slot_config.get("enabled", False))
        url = str(self.slot_config.get("url") or "").strip()
        if not enabled:
            self._set_status("停用", "#64748b")
            return
        if not url:
            self._set_status("缺 URL", "#f59e0b")
            return

        try:
            chrome = self._launch_and_embed(url)
        except Exception as exc:
            self._set_status(f"失敗: {exc}", "#ef4444")
            return

        self.chrome = chrome
        self._set_status("在線", "#22c55e")
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
        self._set_status("已關閉", "#94a3b8")

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

    def _set_status(self, text: str, color: str) -> None:
        self.status_label.setText(text)
        self.status_dot.setStyleSheet(f"color: {color};")

    def _apply_active_style(self) -> None:
        self.setProperty("active", bool(self.slot_config.get("enabled", False)))
        self.style().unpolish(self)
        self.style().polish(self)


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
        self.setObjectName("linkRow")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 7, 8, 8)
        layout.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(6)
        index_label = QLabel(f"{self.index + 1:02d}")
        index_label.setObjectName("rowIndex")
        top.addWidget(index_label)
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
