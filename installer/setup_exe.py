"""Single-file Windows installer for 12宮格直播監控.

Built with PyInstaller --onefile; the application folder travels inside as payload.zip.
Mirrors install-v2.0.ps1: keeps config.json and data\\ (Google login) across upgrades and
migrates the V1.x profile from _internal\\data.
"""
from __future__ import annotations

import argparse
import base64
import ctypes
from ctypes import wintypes
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


APP_NAME = "12宮格直播監控"
APP_VERSION = "V2.0"
EXE_NAME = f"{APP_NAME}.exe"

MB_OK = 0x0
MB_YESNO = 0x4
MB_ICONINFO = 0x40
MB_ICONERROR = 0x10
MB_ICONQUESTION = 0x20
IDYES = 6
CREATE_NO_WINDOW = 0x08000000


class InstallError(Exception):
    pass


def default_install_dir() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / "Programs" / APP_NAME


def payload_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "payload.zip"


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def app_is_running(exe_name: str = EXE_NAME) -> bool:
    # Toolhelp snapshot with wide strings: no console code page involved, unlike parsing tasklist.
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snapshot = kernel32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if not snapshot or snapshot == wintypes.HANDLE(-1).value:
        return False
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        more = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            if entry.szExeFile.lower() == exe_name.lower():
                return True
            more = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
        return False
    finally:
        kernel32.CloseHandle(snapshot)


# User state that an upgrade never moves or deletes. Chrome may hold files in data\ open
# (e.g. a Google sign-in window), so the installer replaces program files around it instead.
PRESERVED = {"config.json", "data"}


def install(payload: Path, install_dir: Path) -> bool:
    """Install payload into install_dir. Returns True when existing user state was kept."""
    if not payload.exists():
        raise InstallError(f"找不到安裝內容：{payload}")
    install_dir.mkdir(parents=True, exist_ok=True)

    # V1.x kept the Chrome profile under _internal\data; a same-volume rename either fully
    # succeeds or leaves everything untouched, unlike a copy-then-delete move.
    legacy_profile = install_dir / "_internal" / "data" / "chrome_monitor_profile"
    profile = install_dir / "data" / "chrome_monitor_profile"
    if legacy_profile.exists() and not profile.exists():
        profile.parent.mkdir(parents=True, exist_ok=True)
        try:
            legacy_profile.rename(profile)
        except OSError as exc:
            raise InstallError("舊版登入資料正在使用中，請關閉所有相關 Chrome 視窗後再安裝。") from exc

    kept = any((install_dir / name).exists() for name in PRESERVED)
    for entry in install_dir.iterdir():
        if entry.name in PRESERVED:
            continue
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink()

    has_config = (install_dir / "config.json").exists()
    with zipfile.ZipFile(payload) as archive:
        for member in archive.infolist():
            if has_config and member.filename == "config.json":
                continue
            archive.extract(member, install_dir)
    return kept


def create_shortcuts(install_dir: Path) -> None:
    exe = install_dir / EXE_NAME
    script = f"""
$shell = New-Object -ComObject WScript.Shell
$paths = @(
  (Join-Path ([Environment]::GetFolderPath('Desktop')) '{APP_NAME}.lnk'),
  (Join-Path (Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs') '{APP_NAME}.lnk')
)
foreach ($p in $paths) {{
  $s = $shell.CreateShortcut($p)
  $s.TargetPath = '{exe}'
  $s.WorkingDirectory = '{install_dir}'
  $s.IconLocation = '{exe}'
  $s.Save()
}}
"""
    # -EncodedCommand is UTF-16LE, so the Chinese paths survive any console code page.
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
        capture_output=True, creationflags=CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        raise InstallError("建立捷徑失敗：" + result.stderr.decode("mbcs", "ignore").strip()[:300])


def message(text: str, flags: int) -> int:
    return ctypes.windll.user32.MessageBoxW(None, text, f"{APP_NAME} {APP_VERSION} 安裝程式", flags)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--silent", action="store_true", help="不顯示對話框")
    parser.add_argument("--target", type=Path, help="安裝到指定資料夾（測試用）")
    parser.add_argument("--no-shortcuts", action="store_true")
    args = parser.parse_args(argv)
    install_dir = args.target or default_install_dir()

    if not args.silent:
        answer = message(f"要安裝 {APP_NAME} {APP_VERSION} 嗎？\n\n安裝位置：\n{install_dir}\n\n"
                         "若已安裝舊版，會保留原本的連結設定與 Google 登入狀態。",
                         MB_YESNO | MB_ICONQUESTION)
        if answer != IDYES:
            return 1

    try:
        if app_is_running():
            raise InstallError(f"{APP_NAME} 正在執行，請先關閉程式再安裝。")
        kept = install(payload_path(), install_dir)
        if not args.no_shortcuts:
            create_shortcuts(install_dir)
    except (InstallError, OSError) as exc:
        if not args.silent:
            message(f"安裝失敗：\n{exc}\n\n連結設定與登入資料沒有被移動，可修正後再執行一次安裝程式。",
                    MB_OK | MB_ICONERROR)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.silent:
        print(f"installed: {install_dir} kept_state={kept}")
        return 0
    note = "\n已保留原本的連結設定與 Google 登入狀態。" if kept else ""
    answer = message(f"安裝完成！{note}\n\n桌面與開始功能表已建立捷徑。\n要立即開啟 {APP_NAME} 嗎？",
                     MB_YESNO | MB_ICONINFO)
    if answer == IDYES:
        subprocess.Popen([str(install_dir / EXE_NAME)], cwd=str(install_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
