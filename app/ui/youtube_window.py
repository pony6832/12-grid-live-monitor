from __future__ import annotations

from dataclasses import replace
import subprocess
import sys
import threading
import time
from typing import Any, Callable

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.config import AppConfig, YOUTUBE_SLOT_COUNT, normalize_youtube_slots
from app.core.telegram import TelegramNotifier
from app.core.youtube import YouTubeTarget, YouTubeUrlError, parse_youtube_url
from app.chrome_grid import find_chrome, normalize_url


PLAYER_STATES = {
    -1: "未開始",
    0: "已結束",
    1: "播放中",
    2: "已暫停",
    3: "緩衝中",
    5: "已載入",
}


class YouTubeMonitorWindow(QMainWindow):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.setWindowTitle("YouTube 12 宮格 24 小時播放器")
        self.setWindowTitle("YouTube 12 宮格連結編輯器")
        self.config = config
        self.notifier = TelegramNotifier(enabled=config.telegram_alerts_enabled)
        self.slots: list[YouTubeSlotWidget] = []

        self.save_button = QPushButton("保存連結")
        self.reload_all_button = QPushButton("開啟Chrome宮格")
        self.fullscreen_button = QPushButton("全螢幕")
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(120)

        self._build_layout()
        self._connect_events()

        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.monitor_slots)
        self.monitor_timer.start(self.config.youtube_monitor_interval_seconds * 1000)

    def _build_layout(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)

        controls = QHBoxLayout()
        controls.addWidget(self.save_button)
        controls.addWidget(self.reload_all_button)
        controls.addWidget(self.fullscreen_button)
        controls.addStretch(1)
        root_layout.addLayout(controls)

        grid = QGridLayout()
        grid.setSpacing(8)
        slots = normalize_youtube_slots(self.config.youtube_slots)
        for index in range(YOUTUBE_SLOT_COUNT):
            slot = YouTubeSlotWidget(
                index=index,
                slot_config=slots[index],
                bad_seconds=self.config.youtube_reload_after_bad_seconds,
                log_callback=self.append_log,
                alert_callback=self.send_alert,
                audio_callback=self.focus_audio,
            )
            self.slots.append(slot)
            row = index // 4
            column = index % 4
            grid.addWidget(slot, row, column)
            grid.setColumnStretch(column, 1)
            grid.setRowStretch(row, 1)
        root_layout.addLayout(grid, stretch=1)

        root_layout.addWidget(QLabel("監控紀錄"))
        root_layout.addWidget(self.log_view)
        self.setCentralWidget(root)

    def _connect_events(self) -> None:
        self.save_button.clicked.connect(self.save_links)
        self.reload_all_button.clicked.connect(self.launch_chrome_grid)
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)

    def save_links(self) -> None:
        self.config = replace(self.config, youtube_slots=[slot.to_config() for slot in self.slots])
        self.config.save()
        self.append_log("YouTube 連結已保存")

    def launch_chrome_grid(self) -> None:
        self.save_links()
        subprocess.Popen([sys.executable, "-m", "app.chrome_embed"])
        self.append_log("已啟動 Chrome 嵌入宮格播放器")

    def monitor_slots(self) -> None:
        return

    def focus_audio(self, selected: "YouTubeSlotWidget") -> None:
        for slot in self.slots:
            if slot is selected:
                slot.unmute()
            else:
                slot.mute()
        self.append_log(f"已切換聲音到第 {selected.index + 1} 格")

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_button.setText("全螢幕")
            return
        self.showFullScreen()
        self.fullscreen_button.setText("離開全螢幕")

    def append_log(self, message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{stamp}] {message}")

    def send_alert(self, message: str) -> None:
        self.append_log(message)
        threading.Thread(target=self.notifier.send_alert, args=(message,), daemon=True).start()

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.save_links()
        event.accept()


class YouTubeSlotWidget(QFrame):
    def __init__(
        self,
        *,
        index: int,
        slot_config: dict[str, object],
        bad_seconds: int,
        log_callback: Callable[[str], None],
        alert_callback: Callable[[str], None],
        audio_callback: Callable[["YouTubeSlotWidget"], None],
    ) -> None:
        super().__init__()
        self.index = index
        self.bad_seconds = bad_seconds
        self.log_callback = log_callback
        self.alert_callback = alert_callback
        self.audio_callback = audio_callback

        self.target: YouTubeTarget | None = None
        self.last_snapshot_at = 0.0
        self.last_good_at = time.monotonic()
        self.last_current_time: float | None = None
        self.consecutive_failures = 0
        self.was_bad = False
        self.last_error: str | None = None
        self.last_url = ""
        self.has_prepared_page = False

        self.title_edit = QLineEdit(str(slot_config.get("title") or f"YouTube {index + 1}"))
        self.url_edit = QLineEdit(str(slot_config.get("url") or ""))
        self.enabled_check = QCheckBox("啟用")
        self.enabled_check.setChecked(bool(slot_config.get("enabled", False)))
        self.status_label = QLabel("待命")
        self.reload_button = QPushButton("套用")
        self.audio_button = QPushButton("開Chrome")
        self.view = QWebEngineView()
        self.profile = QWebEngineProfile(f"youtube_slot_{index + 1}", self)
        self.page = QWebEnginePage(self.profile, self)
        self.view.setPage(self.page)
        self.view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.view.settings().setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        self.view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.view.loadFinished.connect(self._handle_load_finished)

        self._build_layout()
        self._connect_events()
        self.load_from_inputs(force=True)

    def _build_layout(self) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { border: 1px solid #333; background: #111; } "
            "QLineEdit { background: #202020; color: #f2f2f2; border: 1px solid #444; padding: 3px; } "
            "QLabel, QCheckBox { color: #f2f2f2; } "
            "QPushButton { padding: 4px 8px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        top = QHBoxLayout()
        top.addWidget(self.title_edit, stretch=1)
        top.addWidget(self.enabled_check)
        top.addWidget(self.status_label)
        top.addWidget(self.reload_button)
        top.addWidget(self.audio_button)
        layout.addLayout(top)
        layout.addWidget(self.url_edit)
        layout.addWidget(self.view, stretch=1)

    def _connect_events(self) -> None:
        self.reload_button.clicked.connect(lambda: self.load_from_inputs(force=True))
        self.audio_button.clicked.connect(self.launch_in_chrome)
        self.enabled_check.stateChanged.connect(lambda _state: self.load_from_inputs(force=True))
        self.url_edit.returnPressed.connect(lambda: self.load_from_inputs(force=True))

    def launch_in_chrome(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            self._set_status("缺 URL", "orange")
            return
        try:
            parse_youtube_url(url)
        except YouTubeUrlError as exc:
            self._mark_bad(f"第 {self.index + 1} 格 URL 錯誤: {exc}", notify=True)
            return
        subprocess.Popen(
            [
                find_chrome(),
                "--new-window",
                "--autoplay-policy=no-user-gesture-required",
                "--mute-audio",
                normalize_url(url),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._set_status("已開Chrome", "limegreen")

    def to_config(self) -> dict[str, object]:
        return {
            "title": self.title_edit.text().strip() or f"YouTube {self.index + 1}",
            "url": self.url_edit.text().strip(),
            "enabled": self.enabled_check.isChecked(),
        }

    def load_from_inputs(self, *, force: bool = False) -> None:
        url = self.url_edit.text().strip()
        if not self.enabled_check.isChecked():
            self.target = None
            self.last_url = url
            self._set_status("停用", "gray")
            self.view.setHtml(_empty_html("停用"))
            return
        if not url:
            self.target = None
            self.last_url = url
            self._set_status("缺 URL", "orange")
            self.view.setHtml(_empty_html("請貼上 YouTube 連結"))
            return
        if not force and url == self.last_url:
            return

        try:
            self.target = parse_youtube_url(url)
        except YouTubeUrlError as exc:
            self.target = None
            self.last_url = url
            self._mark_bad(f"第 {self.index + 1} 格 URL 錯誤: {exc}", notify=True)
            self.view.setHtml(_empty_html(str(exc)))
            return

        self.last_url = url
        self.last_good_at = time.monotonic()
        self.last_current_time = None
        self.last_error = None
        self.has_prepared_page = False
        self._set_status("已設定", "limegreen")
        self.view.setHtml(_empty_html("此格會用真正 Chrome 視窗播放。按上方「開啟Chrome宮格」。"))

    def poll_status(self) -> None:
        if not self.enabled_check.isChecked() or self.target is None:
            return
        self.view.page().runJavaScript(_video_snapshot_script(), self._handle_snapshot)

    def mute(self) -> None:
        self.view.page().runJavaScript(_set_video_muted_script(True))

    def unmute(self) -> None:
        self.view.page().runJavaScript(_set_video_muted_script(False))

    def _handle_load_finished(self, ok: bool) -> None:
        if not self.enabled_check.isChecked() or self.target is None:
            return
        if not ok:
            self._mark_bad(f"第 {self.index + 1} 格頁面載入失敗", notify=True)
            return
        self._set_status("準備播放", "deepskyblue")
        self._prepare_video()

    def _prepare_video(self) -> None:
        self.view.page().runJavaScript(_prepare_video_script(), self._handle_prepare_result)

    def _handle_prepare_result(self, snapshot: Any) -> None:
        self.has_prepared_page = True
        self._handle_snapshot(snapshot)

    def _handle_snapshot(self, snapshot: Any) -> None:
        now = time.monotonic()
        if not isinstance(snapshot, dict) or not snapshot.get("found"):
            self._check_bad_age("無法取得播放器狀態", now)
            return

        paused = bool(snapshot.get("paused", True))
        ended = bool(snapshot.get("ended", False))
        ready_state = int(snapshot.get("readyState", 0) or 0)
        current_time = _float_or_zero(snapshot.get("currentTime"))
        error = snapshot.get("error")
        play_error = snapshot.get("playError")

        if error or play_error:
            detail = error or play_error
            self._mark_bad(f"第 {self.index + 1} 格 YouTube 頁面播放錯誤: {detail}", notify=True)
            self._reload_after_failure()
            return

        is_progressing = self.last_current_time is None or current_time > self.last_current_time + 0.25
        if not paused and not ended and ready_state >= 2 and is_progressing:
            self.last_good_at = now
            self.last_current_time = current_time
            self._mark_recovered_if_needed()
            self._set_status("播放中", "limegreen")
            return

        self.last_current_time = current_time
        if ended:
            self.view.page().runJavaScript(_prepare_video_script())
            reason = "已結束"
        elif paused:
            self.view.page().runJavaScript(_prepare_video_script())
            reason = "暫停中"
        else:
            reason = f"等待資料 readyState={ready_state}"
        self._set_status(reason, "orange")
        self._check_bad_age(reason, now)

    def _check_bad_age(self, reason: str, now: float) -> None:
        if now - self.last_good_at < self.bad_seconds:
            return
        self._mark_bad(f"第 {self.index + 1} 格停滯超過 {self.bad_seconds} 秒: {reason}", notify=True)
        self._reload_after_failure()

    def _reload_after_failure(self) -> None:
        self.load_from_inputs(force=True)

    def _mark_bad(self, message: str, *, notify: bool) -> None:
        self.consecutive_failures += 1
        self.was_bad = True
        self.last_error = message
        self.last_good_at = time.monotonic()
        self._set_status("重載中", "red")
        if notify and (self.consecutive_failures == 1 or self.consecutive_failures % 3 == 0):
            self.alert_callback(message)
        else:
            self.log_callback(message)

    def _mark_recovered_if_needed(self) -> None:
        if not self.was_bad:
            return
        message = f"第 {self.index + 1} 格已恢復播放"
        self.was_bad = False
        self.consecutive_failures = 0
        self.last_error = None
        self.alert_callback(message)

    def _set_status(self, text: str, color: str) -> None:
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: 600;")


def _empty_html(message: str) -> str:
    safe = _json_dump(message)
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    html, body {{
      width: 100%;
      height: 100%;
      margin: 0;
      background: #050505;
      color: #bdbdbd;
      font-family: Arial, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      text-align: center;
    }}
  </style>
</head>
<body>
  <script>document.body.textContent = {safe};</script>
</body>
</html>"""


def _normalize_browser_url(value: str) -> str:
    url = value.strip()
    if "://" not in url:
        url = "https://" + url
    return url


def _prepare_video_script() -> str:
    return """
(function() {
  const video = document.querySelector('video');
  if (!video) {
    return {found: false, playError: null};
  }
  window.__ytGridPlayError = null;
  video.muted = true;
  video.volume = 0;
  try {
    const result = video.play();
    if (result && result.catch) {
      result.catch(function(error) { window.__ytGridPlayError = String(error); });
    }
  } catch (error) {
    window.__ytGridPlayError = String(error);
  }
  return {
    found: true,
    paused: video.paused,
    ended: video.ended,
    currentTime: video.currentTime || 0,
    readyState: video.readyState || 0,
    error: video.error ? ('media error ' + video.error.code) : null,
    playError: window.__ytGridPlayError
  };
})();
"""


def _video_snapshot_script() -> str:
    return """
(function() {
  const video = document.querySelector('video');
  if (!video) {
    return {found: false, playError: null};
  }
  return {
    found: true,
    paused: video.paused,
    ended: video.ended,
    currentTime: video.currentTime || 0,
    readyState: video.readyState || 0,
    error: video.error ? ('media error ' + video.error.code) : null,
    playError: window.__ytGridPlayError || null
  };
})();
"""


def _set_video_muted_script(muted: bool) -> str:
    muted_value = "true" if muted else "false"
    volume_value = "0" if muted else "1"
    return f"""
(function() {{
  const video = document.querySelector('video');
  if (!video) {{
    return false;
  }}
  video.muted = {muted_value};
  video.volume = {volume_value};
  try {{
    video.play();
  }} catch (error) {{}}
  return true;
}})();
"""


def _json_dump(value: str) -> str:
    import json

    return json.dumps(value)


def _float_or_zero(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
