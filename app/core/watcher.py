from __future__ import annotations

from pathlib import Path
import threading
import time
from typing import Callable

from app.core.ffmpeg_pipeline import is_supported_video


FileCallback = Callable[[Path], None]
LogCallback = Callable[[str], None]


class FolderWatcher:
    def __init__(
        self,
        watch_dir: Path,
        stable_wait_seconds: int,
        callback: FileCallback,
        log_callback: LogCallback | None = None,
    ) -> None:
        self.watch_dir = watch_dir
        self.stable_wait_seconds = stable_wait_seconds
        self.callback = callback
        self.log_callback = log_callback
        self._observer = None
        self._stop_event = threading.Event()
        self._pending: set[Path] = set()

    def start(self) -> None:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self._stop_event.clear()

        watcher = self

        class Handler(FileSystemEventHandler):
            def on_created(self, event) -> None:  # type: ignore[no-untyped-def]
                if not event.is_directory:
                    watcher.enqueue(Path(event.src_path))

            def on_moved(self, event) -> None:  # type: ignore[no-untyped-def]
                if not event.is_directory:
                    watcher.enqueue(Path(event.dest_path))

        self._observer = Observer()
        self._observer.schedule(Handler(), str(self.watch_dir), recursive=False)
        self._observer.start()
        self.scan_existing()
        self._log(f"Watching: {self.watch_dir}")

    def stop(self) -> None:
        self._stop_event.set()
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        self._log("Watcher stopped")

    def scan_existing(self) -> None:
        for path in self.watch_dir.iterdir():
            self.enqueue(path)

    def enqueue(self, path: Path) -> None:
        if not is_supported_video(path):
            return
        resolved = path.resolve()
        if resolved in self._pending:
            return
        self._pending.add(resolved)
        thread = threading.Thread(target=self._wait_and_emit, args=(resolved,), daemon=True)
        thread.start()

    def _wait_and_emit(self, path: Path) -> None:
        try:
            if wait_until_file_stable(path, self.stable_wait_seconds, stop_event=self._stop_event):
                self._log(f"File ready: {path}")
                self.callback(path)
        finally:
            self._pending.discard(path)

    def _log(self, message: str) -> None:
        if self.log_callback:
            self.log_callback(message)


def wait_until_file_stable(
    path: Path,
    stable_wait_seconds: int,
    poll_interval: float = 1.0,
    stop_event: threading.Event | None = None,
) -> bool:
    unchanged_for = 0.0
    last_size = -1

    while stop_event is None or not stop_event.is_set():
        if not path.exists():
            return False

        size = path.stat().st_size
        if size > 0 and size == last_size:
            unchanged_for += poll_interval
            if unchanged_for >= stable_wait_seconds:
                return True
        else:
            unchanged_for = 0.0
            last_size = size

        time.sleep(poll_interval)

    return False
