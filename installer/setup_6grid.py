"""Installer entry for 6宮格直播監控: picks the edition, then runs the shared installer."""
from __future__ import annotations

import os
from pathlib import Path
import sys

# Must run before setup_exe is imported: it reads the edition at import time.
os.environ["LIVE_MONITOR_EDITION"] = "6"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import setup_exe  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(setup_exe.main())
