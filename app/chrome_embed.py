from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.core.config import AppConfig
from app.ui.chrome_embed_window import ChromeEmbedWindow


def main() -> int:
    config = AppConfig.load()
    config.ensure_directories()

    app = QApplication(sys.argv)
    window = ChromeEmbedWindow(config)
    window.resize(1680, 980)
    window.showFullScreen()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
