from __future__ import annotations

from pathlib import Path
from typing import Callable

from app.core.config import AppConfig
from app.core.ffmpeg_pipeline import build_output_path, transcode_vertical
from app.core.file_ops import move_unique
from app.core.jobs import Job, JobStore


JobCallback = Callable[[Job], None]
LogCallback = Callable[[str], None]


class VideoProcessor:
    def __init__(
        self,
        config: AppConfig,
        store: JobStore,
        job_callback: JobCallback | None = None,
        log_callback: LogCallback | None = None,
    ) -> None:
        self.config = config
        self.store = store
        self.job_callback = job_callback
        self.log_callback = log_callback

    def process(self, source: Path) -> Job | None:
        job = self.store.create_if_new(source)
        if job is None:
            self._log(f"Skip duplicate file: {source}")
            return None

        self._emit(job)
        output_path = build_output_path(source, Path(self.config.output_dir))
        try:
            job = self.store.mark_running(job.id, output_path)
            self._emit(job)
            self._log(f"Processing: {source}")

            def on_progress(progress: float) -> None:
                updated = self.store.update_progress(job.id, progress)
                self._emit(updated)

            transcode_vertical(
                source,
                output_path,
                self.config,
                progress_callback=on_progress,
                log_callback=self._log,
            )
            done_path = move_unique(source, Path(self.config.done_dir))
            self._log(f"Moved source to done: {done_path}")
            job = self.store.mark_completed(job.id, output_path)
            self._emit(job)
            return job
        except Exception as exc:
            error = str(exc)
            self._log(error)
            if source.exists():
                failed_path = move_unique(source, Path(self.config.failed_dir))
                self._log(f"Moved source to failed: {failed_path}")
            job = self.store.mark_failed(job.id, error)
            self._emit(job)
            return job

    def _emit(self, job: Job) -> None:
        if self.job_callback:
            self.job_callback(job)

    def _log(self, message: str) -> None:
        if self.log_callback:
            self.log_callback(message)
