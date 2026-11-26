from __future__ import annotations

from app.edition import current

# Names and versions live in app\edition.py; this module keeps the old import path working.
APP_NAME = current.name
APP_VERSION = current.version
