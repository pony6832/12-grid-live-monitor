from pathlib import Path
import json
import sys
import time

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QAbstractSocket, QNetworkAccessManager, QNetworkRequest
from PySide6.QtWebSockets import QWebSocket


def app_root() -> Path:
    # A PyInstaller build keeps its modules under _internal/, which the installer replaces on upgrade.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


PROFILE = app_root() / "data" / "chrome_monitor_profile"

PERMANENT_ERRORS = {2, 100, 101, 150, 153}
FAST_RETRIES = 3
SLOW_RETRY_SECONDS = 600
HEALTHY_RESET_SECONDS = 120


class PlaybackHealth:
    """Detect stalled playback without mistaking a paused video for a network error.

    After a few fast retries it keeps retrying slowly instead of giving up, and sustained
    healthy playback earns the fast retries back, so a 24/7 monitor recovers on its own.
    """
    def __init__(self):
        self.last_time = None
        self.last_progress = time.monotonic()
        self.retries = 0
        self.next_retry = self.last_progress + 30
        self.playing_since = None

    def observe(self, snapshot: dict, now: float) -> tuple[str, bool]:
        error, state, current = snapshot.get('error'), snapshot.get('state'), snapshot.get('time')
        if error in PERMANENT_ERRORS:
            self.playing_since = None
            return 'error', False
        if state == 1 and current != self.last_time:
            self.last_time = current
            self.last_progress = now
            if self.playing_since is None:
                self.playing_since = now
            elif self.retries and now - self.playing_since >= HEALTHY_RESET_SECONDS:
                self.retries = 0
            return 'playing', False
        if state == 2 and not error:
            self.last_progress = now
            self.playing_since = None
            return 'paused', False
        stalled = now - self.last_progress >= 30
        if error or stalled:
            self.playing_since = None
            if now >= self.next_retry:
                self.retries += 1
                delay = 30 * 2 ** self.retries if self.retries < FAST_RETRIES else SLOW_RETRY_SECONDS
                self.next_retry = now + delay
                self.last_progress = now
                self.last_time = None
                return 'retrying', True
            if self.retries >= FAST_RETRIES:
                return 'waiting', False
            if error:
                return 'error', False
        return ('playing' if state == 1 and not stalled else 'loading'), False


def browser_args() -> list[str]:
    PROFILE.mkdir(parents=True, exist_ok=True)
    return [f"--user-data-dir={PROFILE}", "--remote-debugging-port=0",
            "--remote-debugging-address=127.0.0.1", "--no-first-run",
            "--disable-backgrounding-occluded-windows",
            "--disable-features=CalculateNativeWinOcclusion",
            "--autoplay-policy=no-user-gesture-required"]


# YouTube only honours unMute() issued inside its own (cross-origin) frame with a user gesture;
# the page-level iframe API call is silently ignored, so audio is driven through the frame target.
AUDIO_EXPRESSION = """(() => {{
  const p = document.getElementById('movie_player');
  if (!p || !p.isMuted) return null;
  const want = {muted};
  if (p.isMuted() !== want) {{ if (want) {{ p.mute(); }} else {{ p.unMute(); p.setVolume(100); }} }}
  return p.isMuted();
}})()"""


class PlayerConnection(QObject):
    ready = Signal()
    failed = Signal(str)
    playback = Signal(str)
    chrome_inset = Signal(int)

    def __init__(self, marker: str, url: str, parent: QObject) -> None:
        super().__init__(parent)
        self.marker, self.url = marker, url
        self.network = QNetworkAccessManager(self)
        self.ws = QWebSocket(parent=self)
        self.ws.connected.connect(self._connected)
        self.ws.textMessageReceived.connect(self._message)
        self.frame_ws = QWebSocket(parent=self)
        self.frame_ws.connected.connect(self._sync_audio)
        self.repair_timer = QTimer(self)
        self.repair_timer.timeout.connect(self._maintain)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._discover)
        self.timer.start(500)
        self.attempts = 0
        self.pending = False
        self.closed = False
        self.reply = None
        self.frame_reply = None
        self.page_id = None
        self.health = PlaybackHealth()
        self.muted = True

    def set_muted(self, muted: bool) -> None:
        self.muted = muted
        self._sync_audio()

    def _devtools_list_request(self) -> QNetworkRequest | None:
        try:
            port = int((PROFILE / "DevToolsActivePort").read_text().splitlines()[0])
        except (OSError, ValueError, IndexError):
            return None
        request = QNetworkRequest(QUrl(f"http://127.0.0.1:{port}/json/list"))
        request.setTransferTimeout(2000)
        return request

    def _discover(self) -> None:
        if self.pending:
            return
        self.attempts += 1
        if self.attempts > 60:
            self.timer.stop()
            self.failed.emit("播放器連線逾時")
            return
        request = self._devtools_list_request()
        if request is None:
            return
        self.pending = True
        self.reply = self.network.get(request)
        self.reply.finished.connect(self._discovered)

    def _discovered(self) -> None:
        reply = self.reply
        self.pending = False
        if self.closed:
            reply.deleteLater()
            return
        try:
            targets = json.loads(bytes(reply.readAll()))
            target = next((t for t in targets if self.marker in t.get("url", "")), None)
            if target and target.get("webSocketDebuggerUrl"):
                self.timer.stop()
                self.page_id = target.get("id")
                self.ws.open(QUrl(target["webSocketDebuggerUrl"]))
        except (ValueError, TypeError):
            pass
        finally:
            reply.deleteLater()

    def _frame_connected(self) -> bool:
        return self.frame_ws.state() == QAbstractSocket.SocketState.ConnectedState

    def _sync_audio(self) -> None:
        if self.closed:
            return
        if self._frame_connected():
            self._send_frame("Runtime.evaluate", {
                "expression": AUDIO_EXPRESSION.format(muted=json.dumps(self.muted)),
                "returnByValue": True,
                "userGesture": True,
            })
        elif (self.page_id and self.frame_reply is None
              and self.frame_ws.state() == QAbstractSocket.SocketState.UnconnectedState):
            self._discover_frame()

    def _send_frame(self, method: str, params: dict) -> None:
        self.frame_ws.sendTextMessage(json.dumps({"id": 1, "method": method, "params": params}))

    def _discover_frame(self) -> None:
        request = self._devtools_list_request()
        if request is None:
            return
        self.frame_reply = self.network.get(request)
        self.frame_reply.finished.connect(self._frame_discovered)

    def _frame_discovered(self) -> None:
        reply, self.frame_reply = self.frame_reply, None
        if self.closed:
            reply.deleteLater()
            return
        try:
            targets = json.loads(bytes(reply.readAll()))
            frame = next((t for t in targets if t.get("type") == "iframe"
                          and t.get("parentId") == self.page_id
                          and "youtube.com/embed" in t.get("url", "")), None)
            if frame and frame.get("webSocketDebuggerUrl"):
                self.frame_ws.open(QUrl(frame["webSocketDebuggerUrl"]))
        except (ValueError, TypeError):
            pass
        finally:
            reply.deleteLater()

    def _send(self, ident: int, method: str, params: dict) -> None:
        self.ws.sendTextMessage(json.dumps({"id": ident, "method": method, "params": params}))

    def _connected(self) -> None:
        self._send(0, "Page.enable", {})

    def _maintain(self) -> None:
        self._send(5, "Runtime.evaluate", {
            "expression": "window.monitorSnapshot ? window.monitorSnapshot() : {state:-1,time:0}",
            "returnByValue": True,
        })
        # Re-applied every poll: a reload or reconnect creates a fresh, muted YouTube frame.
        self._sync_audio()

    def _message(self, raw: str) -> None:
        message = json.loads(raw)
        if "error" in message:
            # A poll can hit a page that is mid-navigation; the next poll simply tries again.
            if message.get("id") != 5:
                self.failed.emit("播放器控制失敗")
        elif message.get("id") == 0:
            self._send(2, "Page.navigate", {"url": self.url})
            self.repair_timer.start(3000)
        elif message.get("id") == 2:
            if message.get("result", {}).get("errorText"):
                self.failed.emit("網頁載入失敗")
            else:
                self.ready.emit()
        elif message.get("id") == 5:
            snapshot = message.get("result", {}).get("result", {}).get("value")
            if isinstance(snapshot, dict):
                inset = snapshot.get('chromeTop')
                if isinstance(inset, (int, float)) and 0 <= inset <= 200:
                    self.chrome_inset.emit(round(inset))
                state, retry = self.health.observe(snapshot, time.monotonic())
                self.playback.emit(state)
                if retry:
                    self._send(6, "Page.reload", {"ignoreCache": True})

    def close(self) -> None:
        self.closed = True
        self.timer.stop()
        self.repair_timer.stop()
        if self.pending and self.reply:
            self.reply.abort()
        if self.frame_reply is not None:
            self.frame_reply.abort()
        self.ws.close()
        self.frame_ws.close()
