from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import queue
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.config import AppConfig
from app.core.jobs import Job, JobStore
from app.core.processor import VideoProcessor
from app.core.watcher import FolderWatcher


class UiSignals(QObject):
    refresh_requested = Signal()
    log_requested = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.setWindowTitle("影音自動化操作軟體")
        self.config = config
        self.store = JobStore(config.database_path)
        self.signals = UiSignals()
        self.signals.refresh_requested.connect(self.refresh_jobs)
        self.signals.log_requested.connect(self.append_log)

        self.watcher: FolderWatcher | None = None
        self.stop_event = threading.Event()
        self.job_queue: queue.Queue[Path | None] = queue.Queue()
        self.worker_thread: threading.Thread | None = None

        self.watch_edit = QLineEdit(config.watch_dir)
        self.output_edit = QLineEdit(config.output_dir)
        self.done_edit = QLineEdit(config.done_dir)
        self.failed_edit = QLineEdit(config.failed_dir)

        self.start_button = QPushButton("開始監控")
        self.stop_button = QPushButton("停止")
        self.stop_button.setEnabled(False)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "狀態", "進度", "來源", "輸出", "錯誤"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)

        self._build_layout()
        self._connect_events()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_jobs)
        self.refresh_timer.start(1500)
        self.refresh_jobs()

    def _build_layout(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)

        form = QGridLayout()
        self._add_path_row(form, 0, "監控資料夾", self.watch_edit)
        self._add_path_row(form, 1, "輸出資料夾", self.output_edit)
        self._add_path_row(form, 2, "完成資料夾", self.done_edit)
        self._add_path_row(form, 3, "失敗資料夾", self.failed_edit)
        layout.addLayout(form)

        controls = QHBoxLayout()
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addStretch(1)
        layout.addLayout(controls)

        layout.addWidget(QLabel("任務佇列"))
        layout.addWidget(self.table, stretch=3)
        layout.addWidget(QLabel("Log"))
        layout.addWidget(self.log_view, stretch=2)

        self.setCentralWidget(root)

    def _add_path_row(self, form: QGridLayout, row: int, label: str, edit: QLineEdit) -> None:
        button = QPushButton("選擇")
        button.clicked.connect(lambda: self._browse_directory(edit))
        form.addWidget(QLabel(label), row, 0)
        form.addWidget(edit, row, 1)
        form.addWidget(button, row, 2)

    def _connect_events(self) -> None:
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button.clicked.connect(self.stop_monitoring)

    def start_monitoring(self) -> None:
        try:
            self.config = replace(
                self.config,
                watch_dir=self.watch_edit.text().strip(),
                output_dir=self.output_edit.text().strip(),
                done_dir=self.done_edit.text().strip(),
                failed_dir=self.failed_edit.text().strip(),
            )
            self.config.ensure_directories()
            self.config.save()
            if str(self.store.database_path) != self.config.database_path:
                self.store.close()
                self.store = JobStore(self.config.database_path)

            self.stop_event.clear()
            self._start_worker()
            self.watcher = FolderWatcher(
                Path(self.config.watch_dir),
                self.config.stable_wait_seconds,
                callback=self._queue_file,
                log_callback=self._log_from_thread,
            )
            self.watcher.start()
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.append_log("監控已開始")
        except Exception as exc:
            QMessageBox.critical(self, "啟動失敗", str(exc))
            self.stop_monitoring()

    def stop_monitoring(self) -> None:
        self.stop_event.set()
        if self.watcher is not None:
            self.watcher.stop()
            self.watcher = None
        self.job_queue.put(None)
        if self.worker_thread is not None and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=3)
        self.worker_thread = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.append_log("監控已停止")

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.stop_monitoring()
        self.store.close()
        event.accept()

    def refresh_jobs(self) -> None:
        jobs = self.store.list_recent()
        self.table.setRowCount(len(jobs))
        for row, job in enumerate(jobs):
            values = [
                str(job.id),
                job.status,
                f"{job.progress:.1f}%",
                job.source_path,
                job.output_path or "",
                _shorten(job.error or "", 300),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                self.table.setItem(row, column, item)

    def append_log(self, message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{stamp}] {message}")

    def _browse_directory(self, edit: QLineEdit) -> None:
        selected = QFileDialog.getExistingDirectory(self, "選擇資料夾", edit.text())
        if selected:
            edit.setText(selected)

    def _queue_file(self, path: Path) -> None:
        self.job_queue.put(path)
        self._log_from_thread(f"Queued: {path}")

    def _start_worker(self) -> None:
        if self.worker_thread is not None and self.worker_thread.is_alive():
            return
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def _worker_loop(self) -> None:
        processor = VideoProcessor(
            self.config,
            self.store,
            job_callback=self._job_from_thread,
            log_callback=self._log_from_thread,
        )
        while not self.stop_event.is_set():
            path = self.job_queue.get()
            if path is None:
                break
            processor.process(path)

    def _job_from_thread(self, _job: Job) -> None:
        self.signals.refresh_requested.emit()

    def _log_from_thread(self, message: str) -> None:
        self.signals.log_requested.emit(message)


def _shorten(value: str, length: int) -> str:
    if len(value) <= length:
        return value
    return value[: length - 3] + "..."
