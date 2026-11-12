from datetime import datetime
import re
import unittest

from PySide6.QtWidgets import QApplication

from app.core.config import AppConfig
from app.ui.chrome_embed_window import RELAUNCH_DELAYS, ChromeEmbedSlot, ChromeEmbedWindow
from app.ui.themes import THEMES, build_stylesheet, get_theme


class FakeHost:
    def player_url(self, url):
        return 'http://127.0.0.1/player'


class FakeReloadSlot:
    def __init__(self):
        self.stopped = False
        self.disabled_status_refreshed = False

    def stop_chrome(self):
        self.stopped = True

    def is_runnable(self):
        return False

    def start_if_enabled(self):
        self.disabled_status_refreshed = True


class DailyReloadWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_window(self):
        window = ChromeEmbedWindow(AppConfig())
        for slot in window.slots:
            slot.resize_timer.stop()
        return window

    def dispose_window(self, window):
        window.launch_timer.stop()
        window.reveal_timer.stop()
        if hasattr(window, 'daily_reload_timer'):
            window.daily_reload_timer.stop()
        window.player_host.close()

    def test_due_schedule_uses_existing_reload_path_and_updates_status(self):
        window = self.make_window()
        fake_slot = FakeReloadSlot()
        window.slots = [fake_slot]
        try:
            triggered = window._check_daily_reload(datetime(2026, 11, 12, 1, 0, 0))

            self.assertTrue(triggered)
            self.assertTrue(fake_slot.stopped)
            self.assertTrue(fake_slot.disabled_status_refreshed)
            self.assertEqual(window.status_label.text(), "每日 01:00 已自動全部重載")
        finally:
            self.dispose_window(window)

    def test_not_due_does_not_reload_or_replace_status(self):
        window = self.make_window()
        fake_slot = FakeReloadSlot()
        window.slots = [fake_slot]
        window.status_label.setText("原有狀態")
        try:
            triggered = window._check_daily_reload(datetime(2026, 11, 12, 1, 1, 0))

            self.assertFalse(triggered)
            self.assertFalse(fake_slot.stopped)
            self.assertFalse(fake_slot.disabled_status_refreshed)
            self.assertEqual(window.status_label.text(), "原有狀態")
        finally:
            self.dispose_window(window)


class SlotRelaunchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_slot(self, enabled=True, url='https://youtu.be/abcdefghijk'):
        slot = ChromeEmbedSlot(0, {'title': 'T', 'url': url, 'enabled': enabled}, FakeHost(), get_theme('midnight'))
        slot.resize_timer.stop()
        return slot

    def test_unexpected_loss_schedules_relaunch_with_backoff(self):
        slot = self.make_slot()
        slot.want_running = True
        slot._schedule_relaunch('Chrome 視窗已關閉')
        self.assertTrue(slot.relaunch_timer.isActive())
        self.assertEqual(slot.relaunch_timer.interval(), RELAUNCH_DELAYS[0] * 1000)
        for _ in range(10):
            slot._schedule_relaunch('x')
        self.assertEqual(slot.relaunch_timer.interval(), RELAUNCH_DELAYS[-1] * 1000)

    def test_user_stop_cancels_relaunch(self):
        slot = self.make_slot()
        slot.want_running = True
        slot._schedule_relaunch('x')
        slot.stop_chrome()
        self.assertFalse(slot.relaunch_timer.isActive())
        slot._schedule_relaunch('x')
        self.assertFalse(slot.relaunch_timer.isActive())

    def test_playing_resets_relaunch_backoff(self):
        slot = self.make_slot()
        slot.want_running = True
        slot._schedule_relaunch('x')
        slot._schedule_relaunch('x')
        slot._playback_status('playing')
        self.assertEqual(slot.relaunch_attempts, 0)

    def test_runnable_requires_enabled_and_url(self):
        self.assertTrue(self.make_slot().is_runnable())
        self.assertFalse(self.make_slot(enabled=False).is_runnable())
        self.assertFalse(self.make_slot(url='  ').is_runnable())


class ThemeTests(unittest.TestCase):
    def test_every_theme_defines_every_token(self):
        keys = set(THEMES['midnight'])
        for name, theme in THEMES.items():
            self.assertEqual(set(theme), keys, name)
            for key, value in theme.items():
                if key != 'label':
                    self.assertRegex(value, r'^#[0-9a-fA-F]{6}$', f'{name}.{key}')

    def test_stylesheet_has_no_unfilled_placeholders(self):
        for theme in THEMES.values():
            sheet = build_stylesheet(theme)
            self.assertIsNone(re.search(r"\{t\[", sheet))

    def test_unknown_theme_falls_back(self):
        self.assertIs(get_theme('nope'), THEMES['midnight'])


if __name__ == '__main__':
    unittest.main()
