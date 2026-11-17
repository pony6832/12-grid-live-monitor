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
        self.assertFalse(self.schedule.should_trigger(datetime(2026, 11, 12, 9, 0, 0)))

    def test_program_started_after_target_time_does_not_reload(self):
        self.assertFalse(self.schedule.should_trigger(datetime(2026, 11, 12, 1, 1, 0)))
        self.assertFalse(self.schedule.should_trigger(datetime(2026, 11, 12, 1, 1, 1)))

    def test_triggers_again_on_next_date(self):
        self.assertTrue(self.schedule.should_trigger(datetime(2026, 11, 12, 1, 0, 59)))
        self.assertTrue(self.schedule.should_trigger(datetime(2026, 11, 13, 1, 0, 0)))

    def test_catches_up_once_after_sleeping_through_target_time(self):
        self.assertFalse(self.schedule.should_trigger(datetime(2026, 11, 12, 0, 30, 0)))
        self.assertTrue(self.schedule.should_trigger(datetime(2026, 11, 12, 7, 45, 0)))
        self.assertFalse(self.schedule.should_trigger(datetime(2026, 11, 12, 7, 45, 1)))

    def test_sleeping_several_days_catches_up_only_once(self):
        self.assertFalse(self.schedule.should_trigger(datetime(2026, 11, 12, 0, 30, 0)))
        self.assertTrue(self.schedule.should_trigger(datetime(2026, 11, 15, 12, 0, 0)))
        self.assertFalse(self.schedule.should_trigger(datetime(2026, 11, 15, 12, 0, 1)))
        self.assertTrue(self.schedule.should_trigger(datetime(2026, 11, 16, 1, 0, 0)))

    def test_disabled_schedule_never_triggers(self):
        self.schedule.enabled = False
        self.assertFalse(self.schedule.should_trigger(datetime(2026, 11, 12, 1, 0, 0)))

    def test_changing_the_time_does_not_count_as_a_missed_reload(self):
        self.assertFalse(self.schedule.should_trigger(datetime(2026, 11, 12, 10, 0, 0)))
        self.schedule.set_time(9, 30)
        self.assertFalse(self.schedule.should_trigger(datetime(2026, 11, 12, 10, 0, 1)))
        self.assertTrue(self.schedule.should_trigger(datetime(2026, 11, 13, 9, 30, 0)))
        self.assertEqual(self.schedule.label(), "09:30")


if __name__ == "__main__":
    unittest.main()
