from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json
import re

from app.core.paths import CONFIG_PATH, DATA_DIR
from app.edition import current


YOUTUBE_SLOT_COUNT = current.slot_count
DEFAULT_RELOAD_TIME = "01:00"


def default_title(index: int) -> str:
    return f"YouTube {index + 1}"


def default_youtube_slots(count: int | None = None) -> list[dict[str, object]]:
    return [{"title": "", "url": "", "enabled": False, "channel": ""}
            for _ in range(count or YOUTUBE_SLOT_COUNT)]


def normalize_youtube_slots(slots: object, count: int | None = None) -> list[dict[str, object]]:
    """Exactly `count` slots. `title` is the user's own name ("" = use the channel name) and
    `channel` the channel name found automatically from the link."""
    count = count or YOUTUBE_SLOT_COUNT
    normalized: list[dict[str, object]] = []
    if isinstance(slots, list):
        for index, raw_slot in enumerate(slots[:count]):
            slot = raw_slot if isinstance(raw_slot, dict) else {}
            title = str(slot.get("title") or "").strip()
            normalized.append({
                # Older versions saved "YouTube N" when the name was left empty.
                "title": "" if title == default_title(index) else title,
                "url": str(slot.get("url") or ""),
                "enabled": bool(slot.get("enabled", False)),
                "channel": str(slot.get("channel") or "").strip(),
            })
    normalized.extend(default_youtube_slots(count)[len(normalized):])
    return normalized


def slot_display_name(slot: dict[str, object], index: int) -> str:
    return str(slot.get("title") or slot.get("channel") or default_title(index))


def parse_reload_time(value: object) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", str(value).strip())
    if match and int(match[1]) < 24 and int(match[2]) < 60:
        return int(match[1]), int(match[2])
    return 1, 0


@dataclass(slots=True)
class AppConfig:
    youtube_slots: list[dict[str, object]] = field(default_factory=default_youtube_slots)
    ui_theme: str = "midnight"
    daily_reload_enabled: bool = True
    daily_reload_time: str = DEFAULT_RELOAD_TIME
    telegram_alerts_enabled: bool = False
    alert_after_minutes: int = 5

    def __post_init__(self) -> None:
        self.youtube_slots = normalize_youtube_slots(self.youtube_slots)
        self.daily_reload_time = "%02d:%02d" % parse_reload_time(self.daily_reload_time)
        try:
            self.alert_after_minutes = min(120, max(1, int(self.alert_after_minutes)))
        except (TypeError, ValueError):
            self.alert_after_minutes = 5

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "AppConfig":
        if not path.exists():
            config = cls()
            config.save(path)
            return config
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            data = None
        if not isinstance(data, dict):
            # Keep the unreadable file for the user instead of silently overwriting their links.
            path.replace(path.with_name(path.name + ".broken"))
            config = cls()
            config.save(path)
            return config
        # Keys from older versions (video transcoding settings) are simply dropped.
        known = {name: data[name] for name in cls.__dataclass_fields__ if name in data}
        return cls(**known)

    def save(self, path: Path = CONFIG_PATH) -> None:
        temp = path.with_name(path.name + ".tmp")
        temp.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temp.replace(path)

    def ensure_directories(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
