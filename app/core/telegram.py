from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import os


class TelegramNotifier:
    def __init__(
        self,
        *,
        enabled: bool,
        log_path: Path = Path("data/youtube_monitor.log"),
        timeout_seconds: int = 10,
    ) -> None:
        self.enabled = enabled
        self.log_path = log_path
        self.timeout_seconds = timeout_seconds

    def send_alert(self, message: str) -> bool:
        self._write_log(message)
        if not self.enabled:
            return False

        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        if not token or not chat_id:
            self._write_log("Telegram skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing.")
            return False

        try:
            payload = urlencode({"chat_id": chat_id, "text": message}).encode("utf-8")
            request = Request(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=payload,
                method="POST",
            )
            with urlopen(request, timeout=self.timeout_seconds):
                return True
        except Exception as exc:
            self._write_log(f"Telegram failed: {exc}")
            return False

    def _write_log(self, message: str) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{stamp}] {message}\n")
