from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(slots=True)
class DailyReloadSchedule:
    hour: int = 1
    minute: int = 0
    _last_trigger_date: date | None = field(default=None, init=False, repr=False)

    def should_trigger(self, now: datetime) -> bool:
        if now.hour != self.hour or now.minute != self.minute:
            return False
        if self._last_trigger_date == now.date():
            return False
        self._last_trigger_date = now.date()
        return True
