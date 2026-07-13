from __future__ import annotations

from pathlib import Path
import ctypes
from ctypes import wintypes
import json
import os
import shutil


QUALITY_HEIGHTS = {
    "480p": 480,
    "720p": 720,
    "1080p": 1080,
}


def find_mpv() -> str:
    configured = os.environ.get("MPV_PATH", "").strip()
    candidates = [
        configured,
        shutil.which("mpv") or "",
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/WinGet/Links/mpv.exe"),
        *_winget_package_candidates("mpv-player.mpv-CI.MSVC_*", "mpv.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate).resolve())
    raise FileNotFoundError("找不到 mpv，請先執行 install-light-player.ps1")


def find_ytdlp() -> str:
    configured = os.environ.get("YTDLP_PATH", "").strip()
    candidates = [
        configured,
        shutil.which("yt-dlp") or "",
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/WinGet/Links/yt-dlp.exe"),
        *_winget_package_candidates("yt-dlp.yt-dlp_*", "yt-dlp.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate).resolve())
    raise FileNotFoundError("找不到 yt-dlp，請先執行 install-light-player.ps1")


def _winget_package_candidates(package_pattern: str, executable_name: str) -> list[str]:
    package_root = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/WinGet/Packages"
    if not package_root.exists():
        return []
    return [str(path) for path in package_root.glob(f"{package_pattern}/{executable_name}")]


def build_mpv_args(
    mpv_path: str,
    ytdlp_path: str,
    url: str,
    window_id: int,
    quality: str = "720p",
    ipc_path: str | None = None,
) -> list[str]:
    height = QUALITY_HEIGHTS.get(quality, QUALITY_HEIGHTS["720p"])
    video_format = (
        f"bestvideo[height<={height}][fps<=30]+bestaudio/"
        f"best[height<={height}][fps<=30]/best[height<={height}]/best"
    )
    args = [
        mpv_path,
        f"--wid={window_id}",
        "--force-window=yes",
        "--no-terminal",
        "--really-quiet",
        "--no-osc",
        "--osd-level=0",
        "--no-input-default-bindings",
        "--border=no",
        "--mute=yes",
        "--hwdec=auto-safe",
        "--profile=fast",
        "--keep-open=no",
        "--cache=yes",
        "--demuxer-max-bytes=32MiB",
        "--demuxer-max-back-bytes=8MiB",
        f"--script-opts=ytdl_hook-ytdl_path={ytdlp_path}",
        f"--ytdl-format={video_format}",
    ]
    if ipc_path:
        args.append(f"--input-ipc-server={ipc_path}")
    args.append(url)
    return args


def encode_mpv_command(command: list[object]) -> bytes:
    return (json.dumps({"command": command}, ensure_ascii=True) + "\n").encode("utf-8")


def send_mpv_command(ipc_path: str, command: list[object], timeout_ms: int = 500) -> None:
    kernel32 = ctypes.windll.kernel32
    kernel32.WaitNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
    kernel32.WaitNamedPipeW.restype = wintypes.BOOL
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE

    if not kernel32.WaitNamedPipeW(ipc_path, timeout_ms):
        raise OSError(ctypes.get_last_error(), "mpv IPC 尚未就緒")

    generic_write = 0x40000000
    open_existing = 3
    handle = kernel32.CreateFileW(ipc_path, generic_write, 0, None, open_existing, 0, None)
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        raise OSError(ctypes.get_last_error(), "無法開啟 mpv IPC")
    try:
        payload = encode_mpv_command(command)
        written = wintypes.DWORD()
        if not kernel32.WriteFile(handle, payload, len(payload), ctypes.byref(written), None):
            raise OSError(ctypes.get_last_error(), "無法寫入 mpv IPC")
    finally:
        kernel32.CloseHandle(handle)
