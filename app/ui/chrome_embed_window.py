from __future__ import annotations

from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import subprocess
import time
import uuid
from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
from app.core.chrome_session import PlayerConnection, browser_args
from app.core.player_host import PlayerHost
from app.core.config import AppConfig, YOUTUBE_SLOT_COUNT, normalize_youtube_slots
from app.ui.themes import DEFAULT_THEME, THEMES, build_stylesheet, get_theme
from app.version import APP_NAME, APP_VERSION


GWL_STYLE = -16
WS_CHILD = 0x40000000
WS_POPUP = 0x80000000
WS_CLIPSIBLINGS = 0x04000000
WS_VISIBLE = 0x10000000
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU = 0x00080000
WM_CLOSE = 0x0010
SW_HIDE = 0
SW_SHOW = 5

# Seconds to wait before relaunching a slot whose Chrome window died; the last value repeats.
RELAUNCH_DELAYS = [10, 30, 60, 120, 300]
REVEAL_EDGE_PIXELS = 4

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
        self.theme_name = config.ui_theme if config.ui_theme in THEMES else DEFAULT_THEME
        self.tokens = get_theme(self.theme_name)
        self.player_host = PlayerHost()
        self.slots: list[ChromeEmbedSlot] = []
        self.link_rows: list[LinkEditorRow] = []
        self.spotlight_slot: ChromeEmbedSlot | None = None
        self.audio_slot: ChromeEmbedSlot | None = None
        self.clean_mode = False

        self.sidebar_button = QPushButton("連結與外觀")
        self.reload_button = QPushButton("全部重載")
        self.mute_all_button = QPushButton("全部靜音")
        self.clean_button = QPushButton("純影像 H")
        self.clean_button.setCheckable(True)
        self.fullscreen_button = QPushButton("離開全螢幕 F11")
        self.login_button = QPushButton("Google 登入")
        self.close_button = QPushButton("關閉 Chrome")
        self.enabled_count_label = QLabel()
        self.status_label = QLabel("使用真正 Chrome 視窗嵌入每個宮格")
        self.theme_combo = QComboBox()
        self.sidebar = QWidget()
        self.top_bar = QFrame()
        self.grid = QGridLayout()
        self.main_layout: QVBoxLayout | None = None

        self.launch_queue: list[ChromeEmbedSlot] = []
        self.launch_timer = QTimer(self)
        self.launch_timer.timeout.connect(self._start_next_slot)
        self.reveal_timer = QTimer(self)
        self.reveal_timer.timeout.connect(self._check_reveal)

        self._build_layout()
        self._connect_events()
        self._install_shortcuts()
        self.apply_theme(self.theme_name, save=False)
        QTimer.singleShot(0, self.reload_enabled_slots)

    # ---------- layout ----------

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
        self.main_layout = QVBoxLayout(main)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(8)
        self.main_layout.addWidget(self._build_top_bar())

        self.grid.setSpacing(7)
        slots = normalize_youtube_slots(self.config.youtube_slots)
        for index in range(YOUTUBE_SLOT_COUNT):
            slot = ChromeEmbedSlot(index, slots[index], self.player_host, self.tokens)
            slot.launch_requested.connect(self.request_launch)
            slot.spotlight_requested.connect(self.toggle_spotlight)
            slot.audio_requested.connect(self.toggle_audio)
            self.slots.append(slot)
            row, column = divmod(index, 4)
            self.grid.addWidget(slot, row, column)
            self.grid.setColumnStretch(column, 1)
            self.grid.setRowStretch(row, 1)
        self.main_layout.addLayout(self.grid, stretch=1)
        root_layout.addWidget(main, stretch=1)
        self.setCentralWidget(root)
        self.sidebar.hide()
        self._refresh_summary()

    def _build_top_bar(self) -> QFrame:
        self.top_bar.setObjectName("topBar")
        self.top_bar.setFixedHeight(50)
        layout = QHBoxLayout(self.top_bar)
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
        self.close_button.setObjectName("dangerButton")

        self.sidebar_button.setToolTip("編輯 12 格的 YouTube 連結與切換配色主題")
        self.reload_button.setToolTip("關閉並依序重新開啟所有啟用格")
        self.mute_all_button.setToolTip("所有格靜音（快捷鍵 M）")
        self.clean_button.setToolTip("隱藏工具列與標題列，只留影像（H）。滑鼠移到畫面最上緣可叫出工具列")
        self.fullscreen_button.setToolTip("切換全螢幕（F11）")
        self.login_button.setToolTip("開啟 YouTube 帳戶頁登入；登入後按「全部重載」")

        layout.addWidget(title)
        layout.addWidget(version)
        layout.addSpacing(12)
        layout.addWidget(metric_label)
        layout.addWidget(self.enabled_count_label)
        layout.addSpacing(12)
        for button in [self.sidebar_button, self.reload_button, self.mute_all_button,
                       self.clean_button, self.fullscreen_button, self.login_button, self.close_button]:
            layout.addWidget(button)
        layout.addSpacing(6)
        layout.addWidget(self.status_label, stretch=1)
        return self.top_bar

    def _build_sidebar(self) -> None:
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(430)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(14, 14, 14, 14)
        sidebar_layout.setSpacing(10)

        title = QLabel("設定")
        title.setObjectName("sidebarTitle")
        sidebar_layout.addWidget(title)

        appearance = QLabel("外觀")
        appearance.setObjectName("sectionTitle")
        sidebar_layout.addWidget(appearance)
        theme_row = QHBoxLayout()
        theme_label = QLabel("配色主題")
        for key, theme in THEMES.items():
            self.theme_combo.addItem(theme["label"], key)
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(self.theme_name)))
        theme_row.addWidget(theme_label)
        theme_row.addWidget(self.theme_combo, stretch=1)
        sidebar_layout.addLayout(theme_row)
        keys = QLabel("快捷鍵：F11 全螢幕 · H 純影像 · M 全部靜音 · Esc 返回\n"
                      "每格：雙擊標題列放大／還原，「聲音」只讓這格出聲")
        keys.setObjectName("hintText")
        keys.setWordWrap(True)
        sidebar_layout.addWidget(keys)

        links = QLabel("YouTube 連結")
        links.setObjectName("sectionTitle")
        sidebar_layout.addWidget(links)
        hint = QLabel("勾選要監看的頻道，保存後會重新載入啟用格。")
        hint.setObjectName("hintText")
        sidebar_layout.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(7)
        for index, slot_config in enumerate(normalize_youtube_slots(self.config.youtube_slots)):
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
        footer.addWidget(side_save_button, stretch=1)
        footer.addWidget(side_close_button)
        sidebar_layout.addLayout(footer)

    def _connect_events(self) -> None:
        self.sidebar_button.clicked.connect(self.toggle_sidebar)
        self.login_button.clicked.connect(self.open_login)
        self.reload_button.clicked.connect(self.reload_enabled_slots)
        self.mute_all_button.clicked.connect(lambda: self.toggle_audio(None))
        self.clean_button.clicked.connect(lambda checked: self.set_clean_mode(checked))
        self.close_button.clicked.connect(self.close_all_chrome)
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        self.theme_combo.currentIndexChanged.connect(
            lambda _: self.apply_theme(self.theme_combo.currentData()))

    def _install_shortcuts(self) -> None:
        # Shortcuts only fire while this window (not an embedded Chrome) has keyboard focus.
        bindings = {
            "F11": self.toggle_fullscreen,
            "H": lambda: self.set_clean_mode(not self.clean_mode),
            "M": lambda: self.toggle_audio(None),
            "Esc": self.step_back,
        }
        for key, handler in bindings.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(handler)

    # ---------- view modes ----------

    def apply_theme(self, name: str, save: bool = True) -> None:
        self.theme_name = name if name in THEMES else DEFAULT_THEME
        self.tokens = get_theme(self.theme_name)
        self.setStyleSheet(build_stylesheet(self.tokens))
        for slot in self.slots:
            slot.set_theme(self.tokens)
        if save:
            self.config.ui_theme = self.theme_name
            self.config.save()
            self.status_label.setText(f"配色已切換為「{self.tokens['label']}」")

    def toggle_sidebar(self) -> None:
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def changeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.type() == QEvent.Type.WindowStateChange:
            self.fullscreen_button.setText("離開全螢幕 F11" if self.isFullScreen() else "全螢幕 F11")
        super().changeEvent(event)

    def set_clean_mode(self, enabled: bool) -> None:
        self.clean_mode = enabled
        self.clean_button.setChecked(enabled)
        self.top_bar.setVisible(not enabled)
        margin = 0 if enabled else 10
        self.main_layout.setContentsMargins(margin, margin, margin, margin)
        self.main_layout.setSpacing(0 if enabled else 8)
        self.grid.setSpacing(2 if enabled else 7)
        for slot in self.slots:
            slot.set_header_visible(not enabled)
        if enabled:
            self.reveal_timer.start(250)
        else:
            self.reveal_timer.stop()

    def _check_reveal(self) -> None:
        # Embedded Chrome swallows mouse events, so poll the cursor to reveal the toolbar at the top edge.
        pos = self.mapFromGlobal(QCursor.pos())
        inside_x = 0 <= pos.x() < self.width()
        if not self.top_bar.isVisible():
            if inside_x and 0 <= pos.y() <= REVEAL_EDGE_PIXELS:
                self.top_bar.show()
        elif not (inside_x and 0 <= pos.y() <= self.top_bar.geometry().bottom() + 40):
            self.top_bar.hide()

    def toggle_spotlight(self, slot: ChromeEmbedSlot | None) -> None:
        self.spotlight_slot = None if slot is None or self.spotlight_slot is slot else slot
        focus = divmod(self.spotlight_slot.index, 4) if self.spotlight_slot else None
        # Empty rows/columns keep their stretch in QGridLayout, so zero them while one slot is enlarged.
        for row in range(3):
            self.grid.setRowStretch(row, 1 if focus is None or row == focus[0] else 0)
        for column in range(4):
            self.grid.setColumnStretch(column, 1 if focus is None or column == focus[1] else 0)
        for item in self.slots:
            item.setVisible(self.spotlight_slot is None or item is self.spotlight_slot)
            item.set_spotlight(item is self.spotlight_slot)

    def toggle_audio(self, slot: ChromeEmbedSlot | None) -> None:
        self.audio_slot = None if slot is None or self.audio_slot is slot else slot
        for item in self.slots:
            item.set_audio(item is self.audio_slot)
        if self.audio_slot:
            self.status_label.setText(f"聲音：{self.audio_slot.title_text()}")
        else:
            self.status_label.setText("全部靜音")

    def step_back(self) -> None:
        if self.sidebar.isVisible():
            self.toggle_sidebar()
        elif self.spotlight_slot is not None:
            self.toggle_spotlight(None)
        elif self.clean_mode:
            self.set_clean_mode(False)
        elif self.isFullScreen():
            self.showNormal()

    # ---------- chrome lifecycle ----------

    def save_and_reload(self) -> None:
        self.config.youtube_slots = [row.to_config() for row in self.link_rows]
        self.config.save()
        for slot, slot_config in zip(self.slots, self.config.youtube_slots):
            slot.update_config(slot_config)
        self.reload_enabled_slots()
        self.status_label.setText("連結已保存並重載")

    def reload_enabled_slots(self) -> None:
        self.launch_timer.stop()
        self.launch_queue.clear()
        for slot in self.slots:
            slot.stop_chrome()
        for slot in self.slots:
            if slot.is_runnable():
                self.launch_queue.append(slot)
            else:
                slot.start_if_enabled()  # only sets the 停用 / 缺 URL status
        if self.launch_queue:
            self.launch_timer.start(800)
        self._refresh_summary()

    def request_launch(self, slot: ChromeEmbedSlot) -> None:
        # Launches go through one queue: concurrent starts on a shared Chrome profile race each other.
        if slot not in self.launch_queue:
            self.launch_queue.append(slot)
        if not self.launch_timer.isActive():
            self.launch_timer.start(800)

    def _start_next_slot(self) -> None:
        if any(slot.pending_process is not None for slot in self.slots):
            return
        if self.launch_queue:
            self.launch_queue.pop(0).start_if_enabled()
        else:
            self.launch_timer.stop()

    def open_login(self) -> None:
        subprocess.Popen([find_chrome(), *browser_args(), "--new-window",
                          "https://www.youtube.com/account"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.status_label.setText("登入完成後按「全部重載」；Premium 帳戶可免廣告")

    def close_all_chrome(self) -> None:
        self.launch_timer.stop()
        self.launch_queue.clear()
        for slot in self.slots:
            slot.stop_chrome()
        self.status_label.setText("Chrome 已全部關閉")

    def _refresh_summary(self) -> None:
        enabled_count = sum(1 for slot in normalize_youtube_slots(self.config.youtube_slots) if slot.get("enabled"))
        self.enabled_count_label.setText(f"{enabled_count}/{YOUTUBE_SLOT_COUNT}")

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.reveal_timer.stop()
        self.close_all_chrome()
        self.player_host.close()
        event.accept()


class ChromeEmbedSlot(QFrame):
    launch_requested = Signal(object)
    spotlight_requested = Signal(object)
    audio_requested = Signal(object)

    def __init__(self, index: int, slot_config: dict[str, object], player_host: PlayerHost,
                 tokens: dict[str, str]) -> None:
        super().__init__()
        self.index = index
        self.slot_config = slot_config
        self.player_host = player_host
        self.tokens = tokens
        self.chrome: EmbeddedChrome | None = None
        self.pending_process = None
        self.connection = None
        self.marker = ""
        self.last_size = None
        self.chrome_top = 0
        self.want_running = False
        self.relaunch_attempts = 0
        self.audio_on = False
        self.status_kind = "idle"
        self.embed_timer = QTimer(self)
        self.embed_timer.timeout.connect(self._poll_window)
        self.relaunch_timer = QTimer(self)
        self.relaunch_timer.setSingleShot(True)
        self.relaunch_timer.timeout.connect(lambda: self.launch_requested.emit(self))

        self.header = QFrame()
        self.title_label = QLabel()
        self.status_label = QLabel("待命")
        self.status_dot = QLabel("●")
        self.audio_button = QPushButton("聲音")
        self.audio_button.setCheckable(True)
        self.audio_button.setToolTip("只讓這格出聲，其他格自動靜音")
        self.spotlight_button = QPushButton("放大")
        self.spotlight_button.setCheckable(True)
        self.spotlight_button.setToolTip("放大這格（雙擊標題列也可以）")
        self.reload_button = QPushButton("重載")
        self.container = QWidget()
        self.container.setObjectName("chromeContainer")
        self.container.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._build_layout()
        self.update_config(slot_config)
        self.resize_timer = QTimer(self)
        self.resize_timer.timeout.connect(self.fit_chrome)
        self.resize_timer.start(1000)

    def _build_layout(self) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("slotFrame")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header.setObjectName("slotHeader")
        self.header.setFixedHeight(32)
        self.header.installEventFilter(self)
        top = QHBoxLayout(self.header)
        top.setContentsMargins(8, 3, 6, 3)
        top.setSpacing(5)
        slot_index = QLabel(f"{self.index + 1:02d}")
        slot_index.setObjectName("slotIndex")
        self.title_label.setObjectName("slotTitle")
        self.title_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.status_dot.setObjectName("statusDot")
        self.status_label.setObjectName("slotStatus")
        for button in [self.audio_button, self.spotlight_button, self.reload_button]:
            button.setObjectName("slotButton")
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        top.addWidget(slot_index)
        top.addWidget(self.title_label, stretch=1)
        top.addWidget(self.status_dot)
        top.addWidget(self.status_label)
        top.addWidget(self.audio_button)
        top.addWidget(self.spotlight_button)
        top.addWidget(self.reload_button)
        layout.addWidget(self.header)
        layout.addWidget(self.container, stretch=1)
        self.reload_button.clicked.connect(self.reload_chrome)
        self.audio_button.clicked.connect(lambda: self.audio_requested.emit(self))
        self.spotlight_button.clicked.connect(lambda: self.spotlight_requested.emit(self))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.header and event.type() == QEvent.Type.MouseButtonDblClick:
            self.spotlight_requested.emit(self)
            return True
        return super().eventFilter(watched, event)

    # ---------- presentation ----------

    def title_text(self) -> str:
        return str(self.slot_config.get("title") or f"YouTube {self.index + 1}")

    def update_config(self, slot_config: dict[str, object]) -> None:
        self.slot_config = slot_config
        self.title_label.setText(self.title_text())
        self.title_label.setToolTip(str(slot_config.get("url") or ""))
        self._set_property("active", bool(slot_config.get("enabled", False)))

    def set_theme(self, tokens: dict[str, str]) -> None:
        self.tokens = tokens
        self.status_dot.setStyleSheet(f"color: {tokens[self.status_kind]};")

    def set_header_visible(self, visible: bool) -> None:
        self.header.setVisible(visible)

    def set_spotlight(self, enabled: bool) -> None:
        self.spotlight_button.setChecked(enabled)
        self.spotlight_button.setText("還原" if enabled else "放大")

    def set_audio(self, enabled: bool) -> None:
        self.audio_on = enabled
        self.audio_button.setChecked(enabled)
        self._set_property("audio", enabled)
        if self.connection:
            self.connection.set_muted(not enabled)

    def _set_property(self, name: str, value: bool) -> None:
        self.setProperty(name, value)
        self.style().unpolish(self)
        self.style().polish(self)

    def _set_status(self, text: str, kind: str) -> None:
        self.status_kind = kind
        self.status_label.setText(text)
        self.status_dot.setStyleSheet(f"color: {self.tokens[kind]};")

    # ---------- lifecycle ----------

    def is_runnable(self) -> bool:
        return bool(self.slot_config.get("enabled", False)) and bool(str(self.slot_config.get("url") or "").strip())

    def reload_chrome(self) -> None:
        self.stop_chrome()
        self.launch_requested.emit(self)

    def start_if_enabled(self) -> None:
        self.relaunch_timer.stop()
        enabled = bool(self.slot_config.get("enabled", False))
        url = str(self.slot_config.get("url") or "").strip()
        if not enabled:
            self.want_running = False
            self._set_status("停用", "idle")
            return
        if not url:
            self.want_running = False
            self._set_status("缺 URL", "warn")
            return

        try:
            self._launch_and_embed(url)
        except Exception as exc:
            self.want_running = False
            self._set_status(f"失敗: {exc}", "danger")
            return

        self.want_running = True
        self._set_status("載入中", "warn")

    def stop_chrome(self) -> None:
        """User-initiated stop: no automatic relaunch afterwards."""
        self.want_running = False
        self.relaunch_attempts = 0
        self.relaunch_timer.stop()
        had_chrome = self.chrome is not None
        self._teardown()
        if had_chrome:
            self._set_status("已關閉", "idle")

    def _teardown(self) -> None:
        self.embed_timer.stop()
        if self.connection:
            self.connection.close()
            self.connection.deleteLater()
            self.connection = None
        if self.pending_process is not None:
            hwnd = find_window_for_marker(self.marker)
            if hwnd:
                user32.PostMessageW(wintypes.HWND(hwnd), WM_CLOSE, 0, 0)
            self.pending_process = None
        if self.chrome is not None:
            if self.chrome.hwnd and user32.IsWindow(wintypes.HWND(self.chrome.hwnd)):
                user32.PostMessageW(wintypes.HWND(self.chrome.hwnd), WM_CLOSE, 0, 0)
            self.chrome = None
        self.last_size = None

    def _schedule_relaunch(self, reason: str) -> None:
        if not self.want_running:
            return
        self._teardown()
        delay = RELAUNCH_DELAYS[min(self.relaunch_attempts, len(RELAUNCH_DELAYS) - 1)]
        self.relaunch_attempts += 1
        self._set_status(f"{reason}，{delay} 秒後自動重開", "warn")
        self.relaunch_timer.start(delay * 1000)

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        self.fit_chrome()

    def fit_chrome(self) -> None:
        if self.chrome is None or not self.chrome.hwnd:
            return
        if not user32.IsWindow(wintypes.HWND(self.chrome.hwnd)):
            self._schedule_relaunch("Chrome 視窗已關閉")
            return
        ratio = self.container.devicePixelRatioF()
        width = max(1, round(self.container.width() * ratio))
        height = max(1, round(self.container.height() * ratio))
        frame_changed = enforce_embedded_style(self.chrome.hwnd)
        geometry = (width, height, self.chrome_top)
        if self.last_size == geometry and not frame_changed:
            return
        self.last_size = geometry
        # Chrome draws its app title bar inside the client area. Clip it with the native parent.
        user32.MoveWindow(wintypes.HWND(self.chrome.hwnd), 0, -self.chrome_top, width, height + self.chrome_top, True)

    def _launch_and_embed(self, url: str) -> None:
        self.marker = "monitor_" + uuid.uuid4().hex
        self.playback_url = self.player_host.player_url(url)
        args = [
            find_chrome(),
            *browser_args(),
            "--app=data:text/html,<title>" + self.marker + "</title><body style='background:black'>",
            "--window-position=-32000,-32000",
            "--window-size=640,360",
        ]
        self.pending_process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.deadline = time.monotonic() + 30
        self.embed_timer.start(100)

    def _poll_window(self) -> None:
        hwnd = find_window_for_marker(self.marker)
        if not hwnd:
            if time.monotonic() > self.deadline:
                self._schedule_relaunch("啟動逾時")
            return
        self.embed_timer.stop()
        self.chrome = EmbeddedChrome(self.pending_process, hwnd)
        self.pending_process = None
        embed_window(hwnd, int(self.container.winId()))
        self.fit_chrome()
        self.connection = PlayerConnection(self.marker, self.playback_url, self)
        self.connection.muted = not self.audio_on
        self.connection.ready.connect(lambda: self._set_status("已開啟", "ok"))
        self.connection.failed.connect(self._schedule_relaunch)
        self.connection.playback.connect(self._playback_status)
        self.connection.chrome_inset.connect(self._update_chrome_inset)

    def _update_chrome_inset(self, pixels: int) -> None:
        inset = round(pixels * self.container.devicePixelRatioF())
        if inset != self.chrome_top:
            self.chrome_top = inset
            self.fit_chrome()

    def _playback_status(self, state: str) -> None:
        labels = {
            "error": ("影片無法播放", "danger"),
            "loading": ("緩衝中", "warn"),
            "paused": ("已暫停", "idle"),
            "playing": ("播放中", "ok"),
            "retrying": ("重新連線", "warn"),
            "waiting": ("多次失敗，稍後自動重試", "danger"),
        }
        if state == "playing":
            self.relaunch_attempts = 0
        self._set_status(*labels[state])


class LinkEditorRow(QFrame):
    def __init__(self, index: int, slot_config: dict[str, object]) -> None:
        super().__init__()
        self.index = index
        self.title_edit = QLineEdit(str(slot_config.get("title") or f"YouTube {index + 1}"))
        self.url_edit = QLineEdit(str(slot_config.get("url") or ""))
        self.url_edit.setPlaceholderText("https://www.youtube.com/watch?v=…")
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


def find_window_for_marker(marker: str) -> int | None:
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _):
        title = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(wintypes.HWND(hwnd), title, len(title))
        if marker in title.value:
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(callback, 0)
    return found[0] if found else None


def embed_window(hwnd: int, parent_hwnd: int) -> None:
    user32.SetParent(wintypes.HWND(hwnd), wintypes.HWND(parent_hwnd))
    enforce_embedded_style(hwnd)
    user32.ShowWindow(wintypes.HWND(hwnd), SW_SHOW)


def enforce_embedded_style(hwnd: int) -> bool:
    style = user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_STYLE)
    desired = (style & 0xffffffff) & ~(WS_POPUP | WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU)
    desired |= WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS
    if style & 0xffffffff == desired:
        return False
    user32.SetWindowLongW(wintypes.HWND(hwnd), GWL_STYLE, ctypes.c_long(desired))
    # Chrome can restore its frame after navigation; invalidate the non-client cache.
    user32.SetWindowPos(wintypes.HWND(hwnd), None, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020)
    return True
