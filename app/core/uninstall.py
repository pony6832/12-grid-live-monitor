"""Uninstall an installed build: `12宮格直播監控.exe --uninstall` (what Windows 設定 runs)."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import subprocess
import winreg

from app.core import autostart, single_instance
from app.core.chrome_session import stop_profile_browsers
from app.core.paths import app_root, is_frozen
from app.version import APP_NAME

UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\12GridLiveMonitor"
MB_YESNO, MB_ICONQUESTION, MB_ICONINFO, MB_DEFBUTTON2, IDYES = 0x4, 0x20, 0x40, 0x100, 6


def shortcut_paths() -> list[Path]:
    profile = Path(os.environ.get("USERPROFILE", ""))
    appdata = Path(os.environ.get("APPDATA", ""))
    return [profile / "Desktop" / f"{APP_NAME}.lnk",
            profile / "OneDrive" / "Desktop" / f"{APP_NAME}.lnk",
            appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / f"{APP_NAME}.lnk"]


def remove_registration() -> None:
    try:
        autostart.set_enabled(False)
    except OSError:
        pass
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except OSError:
        pass
    for path in shortcut_paths():
        try:
            path.unlink()
        except OSError:
            pass


def run() -> int:
    box = ctypes.windll.user32.MessageBoxW
    title = f"解除安裝 {APP_NAME}"
    if not is_frozen():
        box(None, "這是開發環境，沒有安裝可以解除。", title, MB_ICONINFO)
        return 1
    root = app_root()
    if not single_instance.acquire():
        box(None, f"{APP_NAME} 正在執行，請先關閉程式再解除安裝。", title, MB_ICONINFO)
        return 1
    if box(None, f"要解除安裝 {APP_NAME} 嗎？\n\n會刪除整個資料夾，包含頻道連結設定與 Google 登入狀態：\n{root}",
           title, MB_YESNO | MB_ICONQUESTION | MB_DEFBUTTON2) != IDYES:
        return 1
    stop_profile_browsers()
    remove_registration()
    # A running exe cannot delete itself: a detached cmd waits for this process to end first.
    # The folder is only removed when it really is the app folder.
    if (root / f"{APP_NAME}.exe").exists() and (root / "_internal").is_dir():
        subprocess.Popen(f'cmd.exe /c ping -n 4 127.0.0.1 >nul & rmdir /s /q "{root}"',
                         cwd=str(root.parent), creationflags=0x08000000 | 0x00000008)
    box(None, f"{APP_NAME} 已解除安裝。", title, MB_ICONINFO)
    return 0
