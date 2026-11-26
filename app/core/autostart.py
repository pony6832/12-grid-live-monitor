"""Start with Windows through the per-user Run key (no administrator rights needed)."""
from __future__ import annotations

import sys
import winreg

from app.core.paths import is_frozen
from app.edition import current

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = current.registry_name


def available() -> bool:
    # Only an installed build has a stable exe to point the Run entry at.
    return is_frozen()


def command() -> str:
    return f'"{sys.executable}"'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return bool(winreg.QueryValueEx(key, VALUE_NAME)[0])
    except OSError:
        return False


def set_enabled(enabled: bool) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
