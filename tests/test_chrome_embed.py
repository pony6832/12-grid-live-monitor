from __future__ import annotations

from urllib.parse import parse_qs, urlparse
import unittest

from app.core.youtube_playback import build_embed_playback_url, build_watch_playback_url


class ChromeEmbedUrlTests(unittest.TestCase):
    def test_watch_playback_url_keeps_watch_page(self) -> None:
        url = build_watch_playback_url("https://www.youtube.com/watch?v=abc123")
        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        self.assertEqual(parsed.path, "/watch")
        self.assertEqual(query["v"], ["abc123"])
        self.assertEqual(query["autoplay"], ["1"])
        self.assertEqual(query["mute"], ["1"])
        self.assertEqual(query["vq"], ["hd1080"])

    def test_watch_url_becomes_embed_player(self) -> None:
        url = build_embed_playback_url("https://www.youtube.com/watch?v=abc123")
        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "www.youtube.com")
        self.assertEqual(parsed.path, "/embed/abc123")
        self.assertEqual(query["autoplay"], ["1"])
        self.assertEqual(query["mute"], ["1"])
        self.assertEqual(query["vq"], ["hd1080"])

    def test_short_url_becomes_embed_player(self) -> None:
        url = build_embed_playback_url("https://youtu.be/short123")

        self.assertIn("/embed/short123?", url)

    def test_playlist_url_becomes_videoseries(self) -> None:
        url = build_embed_playback_url("https://www.youtube.com/playlist?list=PL123")
        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        self.assertEqual(parsed.path, "/embed/videoseries")
        self.assertEqual(query["list"], ["PL123"])
        self.assertEqual(query["vq"], ["hd1080"])


if __name__ == "__main__":
    unittest.main()
