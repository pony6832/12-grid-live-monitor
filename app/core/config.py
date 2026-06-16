from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json


CONFIG_PATH = Path("config.json")
YOUTUBE_SLOT_COUNT = 12


def default_youtube_slots() -> list[dict[str, object]]:
    return [
        {
            "title": f"YouTube {index + 1}",
            "url": "",
            "enabled": False,
        }
        for index in range(YOUTUBE_SLOT_COUNT)
    ]


def normalize_youtube_slots(slots: object) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    if isinstance(slots, list):
        for index, raw_slot in enumerate(slots[:YOUTUBE_SLOT_COUNT]):
            slot = raw_slot if isinstance(raw_slot, dict) else {}
            normalized.append(
                {
                    "title": str(slot.get("title") or f"YouTube {index + 1}"),
                    "url": str(slot.get("url") or ""),
                    "enabled": bool(slot.get("enabled", False)),
                }
            )

    for index in range(len(normalized), YOUTUBE_SLOT_COUNT):
        normalized.append(
            {
                "title": f"YouTube {index + 1}",
                "url": "",
                "enabled": False,
            }
        )
    return normalized


@dataclass(slots=True)
class AppConfig:
    watch_dir: str = "data/incoming"
    output_dir: str = "data/output"
    done_dir: str = "data/done"
    failed_dir: str = "data/failed"
    database_path: str = "data/jobs.sqlite3"
    output_width: int = 1080
    output_height: int = 1920
    video_crf: int = 23
    video_preset: str = "medium"
    audio_bitrate: str = "192k"
    stable_wait_seconds: int = 10
    youtube_slots: list[dict[str, object]] = field(default_factory=default_youtube_slots)
    youtube_monitor_interval_seconds: int = 30
    youtube_reload_after_bad_seconds: int = 90
    telegram_alerts_enabled: bool = False

    def __post_init__(self) -> None:
        self.youtube_slots = normalize_youtube_slots(self.youtube_slots)
        self.youtube_monitor_interval_seconds = max(5, int(self.youtube_monitor_interval_seconds))
        self.youtube_reload_after_bad_seconds = max(15, int(self.youtube_reload_after_bad_seconds))

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "AppConfig":
        if not path.exists():
            config = cls()
            config.save(path)
            return config
        data = json.loads(path.read_text(encoding="utf-8"))
        known = {field: data[field] for field in cls.__dataclass_fields__ if field in data}
        return cls(**known)

    def save(self, path: Path = CONFIG_PATH) -> None:
        path.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def ensure_directories(self) -> None:
        for directory in [self.watch_dir, self.output_dir, self.done_dir, self.failed_dir]:
            Path(directory).mkdir(parents=True, exist_ok=True)
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        Path("data").mkdir(parents=True, exist_ok=True)
