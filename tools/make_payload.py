"""Zip the PyInstaller app folder (plus config.json) into the installer payload."""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

# Never ship user state: running the build from dist\ creates data\ with the Chrome profile,
# which holds the Google sign-in, and a config.json that the template below replaces anyway.
EXCLUDED_TOP_LEVEL = {"data", "config.json", "config.json.tmp", "config.json.broken"}


def payload_files(app_dir: Path) -> list[Path]:
    return [path for path in sorted(app_dir.rglob("*"))
            if path.is_file() and path.relative_to(app_dir).parts[0] not in EXCLUDED_TOP_LEVEL]


def main() -> int:
    app_dir, config, output = (Path(arg) for arg in sys.argv[1:4])
    if not (app_dir / f"{app_dir.name}.exe").exists():
        print(f"missing app build: {app_dir}", file=sys.stderr)
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    files = payload_files(app_dir)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files:
            archive.write(path, path.relative_to(app_dir).as_posix())
        archive.write(config, "config.json")
    print(f"payload: {output} ({len(files) + 1} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
