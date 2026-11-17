"""Decide when a slot has been unhealthy long enough to tell someone, and when it recovered."""
from __future__ import annotations


class SlotAlertTracker:
    def __init__(self, after_seconds: float) -> None:
        self.after_seconds = after_seconds
        self.bad_since: dict[int, float] = {}
        self.alerted: set[int] = set()

    def forget(self, index: int) -> None:
        self.bad_since.pop(index, None)
        self.alerted.discard(index)

    def observe(self, index: int, title: str, status: str, healthy: bool, now: float) -> str | None:
        """Return a message to send, or None. One alert per incident, one recovery after it."""
        if healthy:
            was_alerted = index in self.alerted
            self.forget(index)
            return f"✅ 已恢復：{index + 1:02d} {title}" if was_alerted else None
        started = self.bad_since.setdefault(index, now)
        if index not in self.alerted and now - started >= self.after_seconds:
            self.alerted.add(index)
            minutes = round((now - started) / 60)
            return f"⚠️ 異常 {minutes} 分鐘：{index + 1:02d} {title}（{status}）"
        return None
