from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication

from app.core.config import AppConfig
from app.ui.light_player_window import LightPlayerWindow


def main() -> int:
    config = AppConfig.load()
    config.ensure_directories()
    app = QApplication(sys.argv)
    lock = QLockFile(str((Path("data") / "youtube_player.lock").resolve()))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        return 0
    window = LightPlayerWindow(config)
    window.resize(1680, 980)
    window.showFullScreen()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
