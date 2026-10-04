from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import ctypes
import json
import os
import subprocess
import sys
import time


CONFIG_PATH = Path("config.json")
LOG_PATH = Path("data/youtube_chrome_grid.log")
COLUMNS = 4
ROWS = 3


@dataclass(frozen=True, slots=True)
class ChromeSlot:
    index: int
    title: str
    url: str


def main() -> int:
    try:
        chrome_path = find_chrome()
        slots = load_enabled_slots(CONFIG_PATH)
        if not slots:
            print("No enabled YouTube slots found in config.json.")
            return 1

        width, height = get_screen_size()
        cell_width = max(360, width // COLUMNS)
        cell_height = max(260, height // ROWS)

        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        write_log(f"Launching {len(slots)} Chrome YouTube windows.")

        for slot in slots:
            column = slot.index % COLUMNS
            row = slot.index // COLUMNS
            x = column * cell_width
            y = row * cell_height
            launch_chrome(chrome_path, slot.url, x, y, cell_width, cell_height)
            write_log(f"Slot {slot.index + 1}: {slot.url} at {x},{y} {cell_width}x{cell_height}")
            time.sleep(0.35)

        print(f"Launched {len(slots)} Chrome windows.")
        return 0
    except Exception as exc:
        write_log(f"ERROR: {exc}")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def load_enabled_slots(path: Path) -> list[ChromeSlot]:
    data = json.loads(path.read_text(encoding="utf-8"))
    slots: list[ChromeSlot] = []
    for index, raw_slot in enumerate(data.get("youtube_slots", [])[: COLUMNS * ROWS]):
        if not isinstance(raw_slot, dict):
            continue
        enabled = bool(raw_slot.get("enabled", False))
        url = str(raw_slot.get("url") or "").strip()
        if not enabled or not url:
            continue
        slots.append(
            ChromeSlot(
                index=index,
                title=str(raw_slot.get("title") or f"YouTube {index + 1}"),
                url=normalize_url(url),
            )
        )
    return slots


def normalize_url(url: str) -> str:
    if "://" not in url:
        return "https://" + url
    return url


def find_chrome() -> str:
    env_path = os.environ.get("CHROME_PATH", "").strip()
    candidates = [
        env_path,
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        str(Path(os.environ.get("LOCALAPPDATA", "")) / r"Google\Chrome\Application\chrome.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return "chrome.exe"


def get_screen_size() -> tuple[int, int]:
    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()
    return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))


def launch_chrome(chrome_path: str, url: str, x: int, y: int, width: int, height: int) -> None:
    args = [
        chrome_path,
        "--new-window",
        "--autoplay-policy=no-user-gesture-required",
        "--mute-audio",
        f"--window-position={x},{y}",
        f"--window-size={width},{height}",
        url,
    ]
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def write_log(message: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"[{stamp}] {message}\n")


if __name__ == "__main__":
    raise SystemExit(main())
