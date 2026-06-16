from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import subprocess
from typing import Callable

from app.core.config import AppConfig
from app.core.file_ops import unique_path


SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".m4v"}
ProgressCallback = Callable[[float], None]
LogCallback = Callable[[str], None]


@dataclass(slots=True)
class VideoInfo:
    width: int
    height: int
    duration_seconds: float


def is_supported_video(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def build_vertical_filter(output_width: int, output_height: int) -> str:
    return (
        f"scale={output_width}:{output_height}:force_original_aspect_ratio=increase,"
        f"crop={output_width}:{output_height}:(iw-{output_width})/2:(ih-{output_height})/2"
    )


def build_output_path(source: Path, output_dir: Path) -> Path:
    return unique_path(output_dir / f"{source.stem}.mp4")


def probe_video(source: Path) -> VideoInfo:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height:format=duration",
        "-of",
        "json",
        str(source),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    stream = data["streams"][0]
    duration = float(data.get("format", {}).get("duration") or 0)
    return VideoInfo(width=int(stream["width"]), height=int(stream["height"]), duration_seconds=duration)


def transcode_vertical(
    source: Path,
    output: Path,
    config: AppConfig,
    progress_callback: ProgressCallback | None = None,
    log_callback: LogCallback | None = None,
) -> None:
    info = probe_video(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    video_filter = build_vertical_filter(config.output_width, config.output_height)

    command = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(source),
        "-vf",
        video_filter,
        "-c:v",
        "libx264",
        "-preset",
        config.video_preset,
        "-crf",
        str(config.video_crf),
        "-c:a",
        "aac",
        "-b:a",
        config.audio_bitrate,
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
        str(output),
    ]

    if log_callback:
        log_callback(" ".join(command))

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    combined_output: list[str] = []

    assert process.stdout is not None
    try:
        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line:
                continue
            combined_output.append(line)
            if line.startswith("out_time_ms="):
                progress = _progress_from_time(line, info.duration_seconds, divisor=1_000_000)
                if progress_callback:
                    progress_callback(progress)
            elif line.startswith("out_time_us="):
                progress = _progress_from_time(line, info.duration_seconds, divisor=1_000_000)
                if progress_callback:
                    progress_callback(progress)
            elif line.startswith("progress=end"):
                if progress_callback:
                    progress_callback(100.0)
            elif log_callback and not line.startswith(("frame=", "fps=", "stream_", "bitrate=", "total_size=", "out_time")):
                log_callback(line)
    finally:
        process.stdout.close()

    return_code = process.wait()
    if return_code != 0:
        message = "\n".join(combined_output[-80:])
        raise RuntimeError(f"ffmpeg failed with exit code {return_code}\n{message}")


def _progress_from_time(line: str, duration_seconds: float, divisor: int) -> float:
    if duration_seconds <= 0:
        return 0.0
    try:
        value = int(line.split("=", 1)[1])
    except ValueError:
        return 0.0
    seconds = value / divisor
    return max(0.0, min(99.0, (seconds / duration_seconds) * 100))
