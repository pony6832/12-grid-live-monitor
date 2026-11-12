from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from app.core.telegram import TelegramNotifier


class TelegramNotifierTests(unittest.TestCase):
    def test_missing_credentials_logs_and_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "youtube_monitor.log"
            notifier = TelegramNotifier(enabled=True, log_path=log_path)

            with patch.dict("os.environ", {}, clear=True):
                self.assertFalse(notifier.send_alert("test alert"))

            text = log_path.read_text(encoding="utf-8")
            self.assertIn("test alert", text)
            self.assertIn("Telegram skipped", text)

    def test_http_failure_logs_and_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "youtube_monitor.log"
            notifier = TelegramNotifier(enabled=True, log_path=log_path)

            with patch.dict(
                "os.environ",
                {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"},
                clear=True,
            ):
                with patch("app.core.telegram.urlopen", side_effect=OSError("network down")):
                    self.assertFalse(notifier.send_alert("test alert"))

            self.assertIn("Telegram failed", log_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
