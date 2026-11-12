from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

from app.chrome_grid import load_enabled_slots, normalize_url


class ChromeGridTests(unittest.TestCase):
    def test_loads_only_enabled_slots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "youtube_slots": [
                            {"title": "One", "url": "youtube.com/watch?v=one", "enabled": True},
                            {"title": "Two", "url": "https://youtube.com/watch?v=two", "enabled": False},
                            {"title": "Three", "url": "", "enabled": True},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            slots = load_enabled_slots(path)

            self.assertEqual(len(slots), 1)
            self.assertEqual(slots[0].index, 0)
            self.assertEqual(slots[0].url, "https://youtube.com/watch?v=one")

    def test_normalize_url_adds_https(self) -> None:
        self.assertEqual(normalize_url("youtu.be/abc"), "https://youtu.be/abc")
        self.assertEqual(normalize_url("https://youtu.be/abc"), "https://youtu.be/abc")


if __name__ == "__main__":
    unittest.main()
