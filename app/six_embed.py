"""Entry point of 6宮格直播監控."""
from __future__ import annotations

import os

# Must run before any other app module is imported: they read the edition at import time.
os.environ["LIVE_MONITOR_EDITION"] = "6"

from app.chrome_embed import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
