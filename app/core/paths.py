"""Where the app keeps its files, independent of the current working directory."""
from __future__ import annotations

from pathlib import Path
import sys

from app.edition import current


def app_root() -> Path:
    # A PyInstaller build keeps its modules under _internal/, which the installer replaces on upgrade.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


# An installed app has its own folder; a source checkout holds both editions side by side.
_suffix = "" if is_frozen() else current.dev_suffix
CONFIG_PATH = app_root() / f"config{_suffix}.json"
DATA_DIR = app_root() / f"data{_suffix}"
PROFILE = DATA_DIR / "chrome_monitor_profile"
LOG_PATH = DATA_DIR / "app.log"
