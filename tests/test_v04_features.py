import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

from app.core import autostart
from app.core.alerts import SlotAlertTracker
from app.core.player_host import PlayerHost
from app.core.youtube import YouTubeUrlError, parse_youtube_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import make_payload  # noqa: E402

CHANNEL = "UC" + "a" * 22


class ChannelLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.host = PlayerHost()

    @classmethod
    def tearDownClass(cls):
        cls.host.close()

    def test_channel_live_url_is_parsed(self):
        for url in [f"https://www.youtube.com/channel/{CHANNEL}/live", f"youtube.com/channel/{CHANNEL}"]:
            target = parse_youtube_url(url)
            self.assertEqual(target.channel_id, CHANNEL)
            self.assertIsNone(target.video_id)

    def test_handle_url_is_rejected_with_a_hint(self):
        with self.assertRaises(YouTubeUrlError) as caught:
            parse_youtube_url("https://www.youtube.com/@somechannel/live")
        self.assertIn("channel/UC", str(caught.exception))

    def test_player_page_embeds_the_channel_live_stream(self):
        url = self.host.player_url(f"https://www.youtube.com/channel/{CHANNEL}/live")
        self.assertEqual(parse_qs(urlsplit(url).query)["c"], [CHANNEL])
        with urlopen(url, timeout=2) as response:
            page = response.read().decode()
        self.assertIn(f'"channelId": "{CHANNEL}"', page)
        self.assertIn("embed/live_stream?", page)

    def test_malformed_channel_id_is_refused(self):
        with self.assertRaises(YouTubeUrlError):
            self.host.player_url("https://www.youtube.com/channel/UCshort/live")
        with self.assertRaises(HTTPError):
            urlopen(self.host.origin + "/player?c=%22%3E%3Cscript%3E", timeout=2)


class SlotAlertTrackerTests(unittest.TestCase):
    def test_alerts_once_after_the_delay_and_reports_recovery(self):
        tracker = SlotAlertTracker(300)
        self.assertIsNone(tracker.observe(2, "新聞台", "緩衝中", False, 0))
        self.assertIsNone(tracker.observe(2, "新聞台", "緩衝中", False, 299))
        alert = tracker.observe(2, "新聞台", "影片無法播放", False, 300)
        self.assertIn("03 新聞台", alert)
        self.assertIn("影片無法播放", alert)
        self.assertIsNone(tracker.observe(2, "新聞台", "影片無法播放", False, 900))
        self.assertIn("已恢復", tracker.observe(2, "新聞台", "播放中", True, 930))
        self.assertIsNone(tracker.observe(2, "新聞台", "播放中", True, 960))

    def test_short_glitch_sends_nothing(self):
        tracker = SlotAlertTracker(300)
        tracker.observe(0, "A", "緩衝中", False, 0)
        self.assertIsNone(tracker.observe(0, "A", "播放中", True, 60))
        self.assertIsNone(tracker.observe(0, "A", "緩衝中", False, 320))


class AutostartTests(unittest.TestCase):
    def test_enable_writes_quoted_exe_and_disable_removes_it(self):
        with patch.object(autostart, "winreg") as winreg:
            key = MagicMock()
            winreg.OpenKey.return_value.__enter__.return_value = key
            autostart.set_enabled(True)
            name, _, kind, value = winreg.SetValueEx.call_args.args[1:]
            self.assertEqual(name, autostart.VALUE_NAME)
            self.assertEqual(value, f'"{sys.executable}"')
            autostart.set_enabled(False)
            winreg.DeleteValue.assert_called_once_with(key, autostart.VALUE_NAME)

    def test_source_checkout_cannot_enable_autostart(self):
        self.assertFalse(autostart.available())


class PayloadTests(unittest.TestCase):
    def test_user_state_never_reaches_the_installer(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp) / "app"
            for name in ["app.exe", "config.json", "_internal/lib.dll", "_internal/data/keep.txt",
                         "data/chrome_monitor_profile/Default/Cookies", "data/app.log"]:
                (app_dir / name).parent.mkdir(parents=True, exist_ok=True)
                (app_dir / name).write_text("x")
            names = {p.relative_to(app_dir).as_posix() for p in make_payload.payload_files(app_dir)}
        self.assertEqual(names, {"app.exe", "_internal/lib.dll", "_internal/data/keep.txt"})


if __name__ == "__main__":
    unittest.main()
