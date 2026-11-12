from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
import threading
import time


TERMINAL_STATUSES = {"completed", "failed", "skipped"}


@dataclass(slots=True)
class Job:
    id: int
    source_path: str
    source_size: int
    source_mtime_ns: int
    fingerprint: str
    output_path: str | None
    status: str
    error: str | None
    progress: float
    created_at: float
    started_at: float | None
    finished_at: float | None
    updated_at: float


class JobStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.database_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._initialize()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _initialize(self) -> None:
        with self._lock:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_path TEXT NOT NULL,
                    source_size INTEGER NOT NULL,
                    source_mtime_ns INTEGER NOT NULL,
                    fingerprint TEXT NOT NULL UNIQUE,
                    output_path TEXT,
                    status TEXT NOT NULL,
                    error TEXT,
                    progress REAL NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    started_at REAL,
                    finished_at REAL,
                    updated_at REAL NOT NULL
                )
                """
            )
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
            self._connection.commit()

    def create_if_new(self, source: Path) -> Job | None:
        stat = source.stat()
        fingerprint = make_fingerprint(source, stat.st_size, stat.st_mtime_ns)
        now = time.time()
        with self._lock:
            try:
                cursor = self._connection.execute(
                    """
                    INSERT INTO jobs (
                        source_path, source_size, source_mtime_ns, fingerprint,
                        status, progress, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, 'queued', 0, ?, ?)
                    """,
                    (str(source), stat.st_size, stat.st_mtime_ns, fingerprint, now, now),
                )
                self._connection.commit()
                return self.get(cursor.lastrowid)
            except sqlite3.IntegrityError:
                return None

    def get(self, job_id: int) -> Job:
        with self._lock:
            row = self._connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(f"Job {job_id} does not exist")
            return _job_from_row(row)

    def list_recent(self, limit: int = 200) -> list[Job]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [_job_from_row(row) for row in rows]

    def mark_running(self, job_id: int, output_path: Path) -> Job:
        now = time.time()
        with self._lock:
            self._connection.execute(
                """
                UPDATE jobs
                SET status = 'running', output_path = ?, error = NULL, progress = 0,
                    started_at = COALESCE(started_at, ?), updated_at = ?
                WHERE id = ?
                """,
                (str(output_path), now, now, job_id),
            )
            self._connection.commit()
            return self.get(job_id)

    def update_progress(self, job_id: int, progress: float) -> Job:
        now = time.time()
        with self._lock:
            self._connection.execute(
                "UPDATE jobs SET progress = ?, updated_at = ? WHERE id = ?",
                (float(progress), now, job_id),
            )
            self._connection.commit()
            return self.get(job_id)

    def mark_completed(self, job_id: int, output_path: Path) -> Job:
        now = time.time()
        with self._lock:
            self._connection.execute(
                """
                UPDATE jobs
                SET status = 'completed', output_path = ?, progress = 100,
                    error = NULL, finished_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (str(output_path), now, now, job_id),
            )
            self._connection.commit()
            return self.get(job_id)

    def mark_failed(self, job_id: int, error: str) -> Job:
        now = time.time()
        with self._lock:
            self._connection.execute(
                """
                UPDATE jobs
                SET status = 'failed', error = ?, finished_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (error, now, now, job_id),
            )
            self._connection.commit()
            return self.get(job_id)


def make_fingerprint(source: Path, size: int, mtime_ns: int) -> str:
    return f"{source.resolve()}|{size}|{mtime_ns}"


def _job_from_row(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        source_path=row["source_path"],
        source_size=row["source_size"],
        source_mtime_ns=row["source_mtime_ns"],
        fingerprint=row["fingerprint"],
        output_path=row["output_path"],
        status=row["status"],
        error=row["error"],
        progress=row["progress"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        updated_at=row["updated_at"],
    )
