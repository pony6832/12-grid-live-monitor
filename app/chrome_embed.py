from __future__ import annotations

import ctypes
import sys

from PySide6.QtWidgets import QApplication

from app.core import single_instance
from app.core.applog import log, setup_logging
from app.core.config import AppConfig
from app.ui.chrome_embed_window import ChromeEmbedWindow
from app.version import APP_NAME, APP_VERSION


def main() -> int:
    if "--uninstall" in sys.argv[1:]:
        from app.core import uninstall
        return uninstall.run()

    if not single_instance.acquire():
        ctypes.windll.user32.MessageBoxW(None, f"{APP_NAME} 已經在執行中。", APP_NAME, 0x40)
        return 1

    setup_logging()
    log.info("啟動 %s %s", APP_NAME, APP_VERSION)
    config = AppConfig.load()
    config.ensure_directories()

    app = QApplication(sys.argv)
    window = ChromeEmbedWindow(config)
    window.resize(1680, 980)
    window.showFullScreen()
    code = app.exec()
    log.info("結束，代碼 %s", code)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
