from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass(slots=True)
class DailyReloadSchedule:
    """Fires once per day at hour:minute, and catches up when the clock jumped past it.

    The window polls every second. If the PC slept through the scheduled time, the first poll
    after waking sees the scheduled instant between the previous poll and now, and fires then.
    A program that was simply started after the scheduled time does not fire: it just loaded.
    """
    hour: int = 1
    minute: int = 0
    enabled: bool = True
    _last_check: datetime | None = field(default=None, init=False, repr=False)
    _last_fired: datetime | None = field(default=None, init=False, repr=False)

    def set_time(self, hour: int, minute: int) -> None:
        self.hour, self.minute = hour, minute
        # A new time must not look like a missed one.
        self._last_check = None

    def label(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d}"

    def should_trigger(self, now: datetime) -> bool:
        scheduled = now.replace(hour=self.hour, minute=self.minute, second=0, microsecond=0)
        if scheduled > now:
            scheduled -= timedelta(days=1)
        previous, self._last_check = self._last_check, now
        if not self.enabled or self._last_fired == scheduled:
            return False
        in_minute = now - scheduled < timedelta(minutes=1)
        missed = previous is not None and previous < scheduled
        if in_minute or missed:
            self._last_fired = scheduled
            return True
        return False
