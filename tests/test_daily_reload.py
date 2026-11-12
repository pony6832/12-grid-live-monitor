from datetime import datetime
import unittest

from app.core.daily_reload import DailyReloadSchedule


class DailyReloadScheduleTests(unittest.TestCase):
    def setUp(self):
        self.schedule = DailyReloadSchedule(hour=1, minute=0)

    def test_does_not_trigger_before_target_minute(self):
        self.assertFalse(self.schedule.should_trigger(datetime(2026, 11, 12, 0, 59, 59)))

    def test_triggers_during_target_minute(self):
        self.assertTrue(self.schedule.should_trigger(datetime(2026, 11, 12, 1, 0, 0)))

    def test_does_not_trigger_twice_on_same_date(self):
        self.assertTrue(self.schedule.should_trigger(datetime(2026, 11, 12, 1, 0, 0)))
        self.assertFalse(self.schedule.should_trigger(datetime(2026, 11, 12, 1, 0, 59)))

    def test_does_not_catch_up_after_target_minute(self):
        self.assertFalse(self.schedule.should_trigger(datetime(2026, 11, 12, 1, 1, 0)))

    def test_triggers_again_on_next_date(self):
        self.assertTrue(self.schedule.should_trigger(datetime(2026, 11, 12, 1, 0, 59)))
        self.assertTrue(self.schedule.should_trigger(datetime(2026, 11, 13, 1, 0, 0)))


if __name__ == "__main__":
    unittest.main()
