"""Where the app keeps its files, independent of the current working directory."""
from __future__ import annotations

from pathlib import Path
import sys


def app_root() -> Path:
    # A PyInstaller build keeps its modules under _internal/, which the installer replaces on upgrade.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


CONFIG_PATH = app_root() / "config.json"
DATA_DIR = app_root() / "data"
PROFILE = DATA_DIR / "chrome_monitor_profile"
LOG_PATH = DATA_DIR / "app.log"
