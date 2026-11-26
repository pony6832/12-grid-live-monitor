from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

from app.core.config import AppConfig, YOUTUBE_SLOT_COUNT, parse_reload_time, slot_display_name
from app.core.paths import CONFIG_PATH, app_root


class YouTubeConfigTests(unittest.TestCase):
    def test_config_from_an_older_version_loads_and_drops_unused_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({
                "watch_dir": "incoming", "video_crf": 23, "youtube_monitor_interval_seconds": 30,
                "youtube_slots": [{"title": "Main", "url": "https://youtu.be/a", "enabled": True}],
                "ui_theme": "oled",
            }), encoding="utf-8")

            config = AppConfig.load(path)
            config.save(path)
            saved = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(config.youtube_slots[0]["title"], "Main")
            self.assertEqual(config.ui_theme, "oled")
            self.assertEqual(config.daily_reload_time, "01:00")
            self.assertTrue(config.daily_reload_enabled)
            self.assertFalse(config.telegram_alerts_enabled)
            self.assertNotIn("watch_dir", saved)
            self.assertEqual(len(saved["youtube_slots"]), YOUTUBE_SLOT_COUNT)

    def test_short_slot_list_is_normalized_to_twelve_slots(self) -> None:
        config = AppConfig(youtube_slots=[{"title": "Main", "url": "https://youtu.be/a", "enabled": True}])

        self.assertEqual(len(config.youtube_slots), YOUTUBE_SLOT_COUNT)
        self.assertEqual(config.youtube_slots[0]["title"], "Main")
        self.assertEqual(config.youtube_slots[0]["enabled"], True)
        self.assertEqual(config.youtube_slots[1]["title"], "")
        self.assertEqual(slot_display_name(config.youtube_slots[1], 1), "YouTube 2")

    def test_old_default_titles_become_automatic(self) -> None:
        config = AppConfig(youtube_slots=[
            {"title": "YouTube 1", "url": "https://youtu.be/a", "enabled": True},
            {"title": "我的台", "url": "https://youtu.be/b", "enabled": True, "channel": "某頻道"},
            {"title": "", "url": "https://youtu.be/c", "enabled": True, "channel": "頻道C"},
        ])
        self.assertEqual(config.youtube_slots[0]["title"], "")
        self.assertEqual(slot_display_name(config.youtube_slots[1], 1), "我的台")
        self.assertEqual(slot_display_name(config.youtube_slots[2], 2), "頻道C")

    def test_unreadable_config_is_kept_aside_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text("{ not json", encoding="utf-8")

            config = AppConfig.load(path)

            self.assertEqual(len(config.youtube_slots), YOUTUBE_SLOT_COUNT)
            self.assertEqual((Path(tmp) / "config.json.broken").read_text(encoding="utf-8"), "{ not json")
            self.assertTrue(json.loads(path.read_text(encoding="utf-8"))["daily_reload_enabled"])

    def test_reload_time_falls_back_to_one_oclock(self) -> None:
        self.assertEqual(parse_reload_time("03:30"), (3, 30))
        self.assertEqual(parse_reload_time("25:00"), (1, 0))
        self.assertEqual(parse_reload_time("abc"), (1, 0))
        self.assertEqual(AppConfig(daily_reload_time="7:05").daily_reload_time, "07:05")

    def test_config_path_does_not_depend_on_the_working_directory(self) -> None:
        self.assertTrue(CONFIG_PATH.is_absolute())
        self.assertEqual(CONFIG_PATH.parent, app_root())


if __name__ == "__main__":
    unittest.main()
