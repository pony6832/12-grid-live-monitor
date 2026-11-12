from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from app.core.jobs import JobStore


class JobStoreTests(unittest.TestCase):
    def test_same_file_is_not_enqueued_twice_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "incoming.mp4"
            source.write_bytes(b"video bytes")
            database = root / "jobs.sqlite3"

            store = JobStore(database)
            first = store.create_if_new(source)
            second = store.create_if_new(source)
            store.close()

            self.assertIsNotNone(first)
            self.assertIsNone(second)

            reopened = JobStore(database)
            third = reopened.create_if_new(source)
            jobs = reopened.list_recent()
            reopened.close()

            self.assertIsNone(third)
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0].status, "queued")


if __name__ == "__main__":
    unittest.main()
