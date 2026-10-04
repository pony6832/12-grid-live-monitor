from __future__ import annotations

import unittest

from app.core.youtube import YouTubeUrlError, parse_youtube_url


class YouTubeUrlTests(unittest.TestCase):
    def test_parse_watch_url(self) -> None:
        target = parse_youtube_url("https://www.youtube.com/watch?v=abc123XYZ_9")

        self.assertEqual(target.video_id, "abc123XYZ_9")
        self.assertIsNone(target.playlist_id)

    def test_parse_short_url(self) -> None:
        target = parse_youtube_url("https://youtu.be/abc123XYZ_9?t=30")

        self.assertEqual(target.video_id, "abc123XYZ_9")

    def test_parse_shorts_url(self) -> None:
        target = parse_youtube_url("https://youtube.com/shorts/shortId123")

        self.assertEqual(target.video_id, "shortId123")

    def test_parse_live_url(self) -> None:
        target = parse_youtube_url("https://www.youtube.com/live/liveId123?feature=share")

        self.assertEqual(target.video_id, "liveId123")

    def test_parse_playlist_url(self) -> None:
        target = parse_youtube_url("https://www.youtube.com/watch?v=video1&list=PL123")

        self.assertEqual(target.video_id, "video1")
        self.assertEqual(target.playlist_id, "PL123")
        self.assertTrue(target.is_playlist)

    def test_reject_invalid_host(self) -> None:
        with self.assertRaises(YouTubeUrlError):
            parse_youtube_url("https://example.com/watch?v=abc")


if __name__ == "__main__":
    unittest.main()
