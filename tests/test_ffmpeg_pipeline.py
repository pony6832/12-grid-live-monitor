from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from app.core.ffmpeg_pipeline import build_output_path, build_vertical_filter


class FfmpegPipelineTests(unittest.TestCase):
    def test_build_vertical_filter_uses_center_crop(self) -> None:
        self.assertEqual(
            build_vertical_filter(1080, 1920),
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920:(iw-1080)/2:(ih-1920)/2",
        )

    def test_build_output_path_avoids_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            source = output_dir / "clip.mov"
            (output_dir / "clip.mp4").write_text("existing", encoding="utf-8")
            (output_dir / "clip_1.mp4").write_text("existing", encoding="utf-8")

            self.assertEqual(build_output_path(source, output_dir), output_dir / "clip_2.mp4")


if __name__ == "__main__":
    unittest.main()
