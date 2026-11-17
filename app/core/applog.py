"""One rotating log file under data\\, so a windowed build leaves something to diagnose from."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import sys

from app.core.paths import LOG_PATH

log = logging.getLogger("monitor")


def setup_logging() -> None:
    if log.handlers:
        return
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3,
                                                       encoding="utf-8")
    except OSError:
        handler = logging.NullHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)

    def report(exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        log.error("未處理的例外", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = report
