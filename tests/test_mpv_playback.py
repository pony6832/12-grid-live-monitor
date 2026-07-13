from __future__ import annotations

import unittest

from app.core.mpv_playback import _winget_package_candidates, build_mpv_args, encode_mpv_command


class MpvPlaybackTests(unittest.TestCase):
    def test_builds_embedded_muted_720p_player(self) -> None:
        args = build_mpv_args("mpv.exe", "yt-dlp.exe", "https://youtu.be/test", 1234, "720p")

        self.assertEqual(args[0], "mpv.exe")
        self.assertIn("--wid=1234", args)
        self.assertIn("--mute=yes", args)
        self.assertIn("--no-osc", args)
        self.assertIn("--hwdec=auto-safe", args)
        self.assertTrue(any("height<=720" in value for value in args))
        self.assertEqual(args[-1], "https://youtu.be/test")

    def test_unknown_quality_falls_back_to_720p(self) -> None:
        args = build_mpv_args("mpv.exe", "yt-dlp.exe", "https://youtu.be/test", 1, "invalid")

        self.assertTrue(any("height<=720" in value for value in args))

    def test_missing_winget_root_returns_no_candidates(self) -> None:
        self.assertIsInstance(_winget_package_candidates("not-a-real-package_*", "missing.exe"), list)

    def test_ipc_and_volume_options_are_added(self) -> None:
        args = build_mpv_args("mpv.exe", "yt-dlp.exe", "https://youtu.be/test", 1, ipc_path=r"\\.\pipe\test")

        self.assertIn(r"--input-ipc-server=\\.\pipe\test", args)

    def test_encodes_json_ipc_command(self) -> None:
        self.assertEqual(
            encode_mpv_command(["set_property", "mute", False]),
            b'{"command": ["set_property", "mute", false]}\n',
        )


if __name__ == "__main__":
    unittest.main()
