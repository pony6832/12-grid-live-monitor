"""Zip the PyInstaller app folder (plus config.json) into the installer payload."""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path


def main() -> int:
    app_dir, config, output = (Path(arg) for arg in sys.argv[1:4])
    if not (app_dir / f"{app_dir.name}.exe").exists():
        print(f"missing app build: {app_dir}", file=sys.stderr)
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(app_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(app_dir).as_posix())
                count += 1
        archive.write(config, "config.json")
    print(f"payload: {output} ({count + 1} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
