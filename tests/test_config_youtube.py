from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

from app.core.config import AppConfig, YOUTUBE_SLOT_COUNT


class YouTubeConfigTests(unittest.TestCase):
    def test_legacy_config_gets_youtube_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "watch_dir": "incoming",
                        "output_dir": "output",
                        "done_dir": "done",
                        "failed_dir": "failed",
                        "database_path": "jobs.sqlite3",
                    }
                ),
                encoding="utf-8",
            )

            config = AppConfig.load(path)

            self.assertEqual(len(config.youtube_slots), YOUTUBE_SLOT_COUNT)
            self.assertEqual(config.youtube_monitor_interval_seconds, 30)
            self.assertEqual(config.youtube_reload_after_bad_seconds, 90)
            self.assertFalse(config.telegram_alerts_enabled)

    def test_short_slot_list_is_normalized_to_twelve_slots(self) -> None:
        config = AppConfig(youtube_slots=[{"title": "Main", "url": "https://youtu.be/a", "enabled": True}])

        self.assertEqual(len(config.youtube_slots), YOUTUBE_SLOT_COUNT)
        self.assertEqual(config.youtube_slots[0]["title"], "Main")
        self.assertEqual(config.youtube_slots[0]["enabled"], True)
        self.assertEqual(config.youtube_slots[1]["title"], "YouTube 2")


if __name__ == "__main__":
    unittest.main()
