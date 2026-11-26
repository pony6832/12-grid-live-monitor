"""Two copies would share one Chrome profile and fight over its debugging port."""
from __future__ import annotations

import ctypes

from app.edition import current

ERROR_ALREADY_EXISTS = 183
_handle = None


def acquire(name: str = "") -> bool:
    """True when this is the only running copy. The mutex lives until the process exits."""
    global _handle
    name = name or f"Local\\{current.registry_name}"
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, False, name)
    if handle and ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(ctypes.c_void_p(handle))
        return False
    _handle = handle
    return True
