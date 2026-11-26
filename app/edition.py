"""The two apps built from this code: the 12-slot monitor and the 6-slot monitor.

Each entry point picks its edition through LIVE_MONITOR_EDITION before importing the rest of
the app, so every module sees one fixed edition for the life of the process.
"""
from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True, slots=True)
class Edition:
    key: str
    name: str
    version: str
    columns: int
    rows: int
    # True: an enlarged slot fills the left and the others stack in a column on the right.
    # False: an enlarged slot fills the whole grid and the others are hidden.
    side_spotlight: bool
    # Windows names: mutex, Run value and Uninstall key. Different per edition so both apps can
    # be installed and run side by side.
    registry_name: str
    icon: str
    # Running from source keeps each edition's config and Chrome profile apart.
    dev_suffix: str

    @property
    def slot_count(self) -> int:
        return self.columns * self.rows


TWELVE = Edition(key="12", name="12宮格直播監控", version="V04", columns=4, rows=3,
                 side_spotlight=False, registry_name="12GridLiveMonitor",
                 icon="12grid-live-monitor-icon", dev_suffix="")
SIX = Edition(key="6", name="6宮格直播監控", version="V01", columns=3, rows=2,
              side_spotlight=True, registry_name="6GridLiveMonitor",
              icon="6grid-live-monitor-icon", dev_suffix="-6grid")
EDITIONS = {edition.key: edition for edition in (TWELVE, SIX)}

ENV_NAME = "LIVE_MONITOR_EDITION"
current = EDITIONS.get(os.environ.get(ENV_NAME, "").strip(), TWELVE)
