import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from app.core import channel_name
from app.core.config import AppConfig
from app.edition import SIX, TWELVE
from app.ui.chrome_embed_window import SIDE_SPOTLIGHT_RATIO, ChromeEmbedWindow, LinkEditorRow

ROOT = Path(__file__).resolve().parents[1]


def make_window(edition):
    config = AppConfig(youtube_slots=[{"title": "", "url": "", "enabled": False}])
    window = ChromeEmbedWindow(config, edition)
    for slot in window.slots:
        slot.resize_timer.stop()
    return window


def dispose(window):
    for timer in (window.launch_timer, window.reveal_timer, window.login_timer, window.health_timer,
                  window.daily_reload_timer, window.channel_save_timer):
        timer.stop()
    window.player_host.close()


def cell(window, slot):
    row, column, row_span, column_span = window.grid.getItemPosition(window.grid.indexOf(slot))
    return row, column, row_span, column_span


class SixGridLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_six_slots_in_three_columns_and_two_rows(self):
        window = make_window(SIX)
        try:
            self.assertEqual(len(window.slots), 6)
            self.assertEqual(len(window.link_rows), 6)
            self.assertEqual([cell(window, s)[:2] for s in window.slots],
                             [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)])
            self.assertEqual(window.enabled_count_label.text(), "0/6")
        finally:
            dispose(window)

    def test_enlarged_slot_fills_left_and_others_stack_on_the_right(self):
        window = make_window(SIX)
        try:
            focus = window.slots[4]
            window.toggle_spotlight(focus)
            self.assertEqual(cell(window, focus), (0, 0, 5, 1))
            others = [s for s in window.slots if s is not focus]
            self.assertEqual([cell(window, s) for s in others], [(r, 1, 1, 1) for r in range(5)])
            self.assertTrue(all(not s.isHidden() for s in window.slots))
            self.assertEqual(window.grid.columnStretch(0), SIDE_SPOTLIGHT_RATIO)
            self.assertEqual(window.grid.columnStretch(1), 1)
            self.assertEqual(window.grid.columnStretch(2), 0)
            self.assertTrue(focus.spotlight_button.isChecked())

            # Clicking 放大 on a small slot swaps it in; the slot order on the right follows.
            window.toggle_spotlight(window.slots[0])
            self.assertEqual(cell(window, window.slots[0]), (0, 0, 5, 1))
            self.assertEqual(cell(window, window.slots[4]), (3, 1, 1, 1))
            self.assertFalse(window.slots[4].spotlight_button.isChecked())

            window.step_back()
            self.assertIsNone(window.spotlight_slot)
            self.assertEqual(cell(window, window.slots[5]), (1, 2, 1, 1))
            self.assertEqual([window.grid.rowStretch(r) for r in range(window.grid.rowCount())],
                             [1, 1, 0, 0, 0])
            self.assertEqual([window.grid.columnStretch(c) for c in range(3)], [1, 1, 1])
        finally:
            dispose(window)

    def test_twelve_grid_keeps_hiding_the_others(self):
        window = make_window(TWELVE)
        try:
            focus = window.slots[6]
            window.toggle_spotlight(focus)
            self.assertEqual(cell(window, focus), (1, 2, 1, 1))
            self.assertEqual([s for s in window.slots if not s.isHidden()], [focus])
            window.toggle_spotlight(None)
            self.assertEqual(len([s for s in window.slots if not s.isHidden()]), 12)
        finally:
            dispose(window)


class ChannelNameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_lookup_uses_oembed_for_videos_and_the_page_for_channels(self):
        calls = []

        def fake_get(url, timeout):
            calls.append(url)
            if "oembed" in url:
                return json.dumps({"author_name": "民視新聞網"})
            return '<meta itemprop="name" content="中視新聞 &amp; HD">'

        with patch.object(channel_name, "_get", fake_get):
            self.assertEqual(channel_name.lookup_channel_name("https://youtu.be/ylYJSBUgaMA"), "民視新聞網")
            self.assertIn("watch%3Fv%3DylYJSBUgaMA", calls[-1])
            self.assertEqual(channel_name.lookup_channel_name(
                "https://www.youtube.com/channel/UCmH4q-YjeazayYCVHHkGAMA/live"), "中視新聞 & HD")
            self.assertIsNone(channel_name.lookup_channel_name("https://example.com/x"))
        with patch.object(channel_name, "_get", side_effect=OSError("offline")):
            self.assertIsNone(channel_name.lookup_channel_name("https://youtu.be/ylYJSBUgaMA"))

    def test_row_fills_the_name_but_keeps_a_name_the_user_typed(self):
        row = LinkEditorRow(0, {"title": "", "url": "", "enabled": True})
        row.url_edit.setText("https://youtu.be/ylYJSBUgaMA")
        row._name_ready("https://youtu.be/ylYJSBUgaMA", "民視新聞網")
        self.assertEqual(row.title_edit.text(), "民視新聞網")
        self.assertEqual(row.to_config()["title"], "")
        self.assertEqual(row.to_config()["channel"], "民視新聞網")

        row.title_edit.setText("新聞台")
        row.url_edit.setText("https://youtu.be/TCnaIE_SAtM")
        self.assertEqual(row.to_config()["channel"], "")
        row._name_ready("https://youtu.be/ylYJSBUgaMA", "過期的結果")
        row._name_ready("https://youtu.be/TCnaIE_SAtM", "中視新聞")
        self.assertEqual(row.title_edit.text(), "新聞台")
        self.assertEqual(row.to_config()["title"], "新聞台")
        self.assertEqual(row.to_config()["channel"], "中視新聞")

    def test_new_link_replaces_an_automatic_name(self):
        row = LinkEditorRow(0, {"title": "", "url": "https://youtu.be/ylYJSBUgaMA", "enabled": True,
                                "channel": "民視新聞網"})
        self.assertEqual(row.title_edit.text(), "民視新聞網")
        row.url_edit.setText("https://youtu.be/TCnaIE_SAtM")
        self.assertEqual(row.title_edit.text(), "")
        row._name_ready("https://youtu.be/TCnaIE_SAtM", "中視新聞")
        self.assertEqual(row.title_edit.text(), "中視新聞")

    def test_name_reported_by_the_player_is_saved_and_shown(self):
        window = make_window(SIX)
        try:
            window.config.youtube_slots[1].update(url="https://youtu.be/ylYJSBUgaMA", enabled=True)
            window.link_rows[1].url_edit.setText("https://youtu.be/ylYJSBUgaMA")
            with patch.object(AppConfig, "save") as save:
                window.slots[1]._on_channel_name("民視新聞網")
                self.assertTrue(window.channel_save_timer.isActive())
                # Fire it now and stop the real timer, or it would write the real config.json later.
                window.channel_save_timer.stop()
                window.channel_save_timer.timeout.emit()
                save.assert_called_once()
            self.assertEqual(window.config.youtube_slots[1]["channel"], "民視新聞網")
            self.assertEqual(window.slots[1].title_label.text(), "民視新聞網")
            self.assertEqual(window.link_rows[1].title_edit.text(), "民視新聞網")
        finally:
            dispose(window)


class EditionTests(unittest.TestCase):
    def test_six_edition_has_its_own_names_and_files(self):
        script = ("from app.edition import current; from app.core import paths, autostart, single_instance; "
                  "from app.core.uninstall import UNINSTALL_KEY; from app.version import APP_NAME; "
                  "print(APP_NAME, current.slot_count, paths.CONFIG_PATH.name, paths.DATA_DIR.name, "
                  "autostart.VALUE_NAME, UNINSTALL_KEY.rsplit(chr(92), 1)[1])")
        env = {**os.environ, "LIVE_MONITOR_EDITION": "6", "PYTHONIOENCODING": "utf-8"}
        out = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env, capture_output=True,
                             text=True, encoding="utf-8", check=True).stdout.split()
        self.assertEqual(out, ["6宮格直播監控", "6", "config-6grid.json", "data-6grid",
                               "6GridLiveMonitor", "6GridLiveMonitor"])

    def test_six_config_template_is_valid(self):
        data = json.loads((ROOT / "config-6grid.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["youtube_slots"]), 6)


if __name__ == "__main__":
    unittest.main()
