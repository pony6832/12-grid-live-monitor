from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.core.config import AppConfig
from app.ui.main_window import MainWindow


def main() -> int:
    config = AppConfig.load()
    config.ensure_directories()

    app = QApplication(sys.argv)
    window = MainWindow(config)
    window.resize(1180, 760)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
