from __future__ import annotations

from pathlib import Path
import shutil


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    for index in range(1, 10_000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate

    raise RuntimeError(f"Cannot find available filename for {path}")


def move_unique(source: Path, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    target = unique_path(target_dir / source.name)
    return Path(shutil.move(str(source), str(target)))
