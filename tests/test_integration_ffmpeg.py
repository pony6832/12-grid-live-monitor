from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from app.core.config import AppConfig
from app.core.ffmpeg_pipeline import probe_video, transcode_vertical


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe are required")
class FfmpegIntegrationTests(unittest.TestCase):
    def test_transcode_vertical_outputs_1080x1920_mp4(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.mp4"
            output = root / "output.mp4"

            subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=size=320x240:rate=24",
                    "-t",
                    "1",
                    "-pix_fmt",
                    "yuv420p",
                    str(source),
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            transcode_vertical(source, output, AppConfig(video_preset="ultrafast"))
            info = probe_video(output)

            self.assertEqual(info.width, 1080)
            self.assertEqual(info.height, 1920)
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
