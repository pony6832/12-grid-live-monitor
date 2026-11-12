import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "installer"))
import setup_exe  # noqa: E402


class SetupExeInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.payload = self.root / "payload.zip"
        with zipfile.ZipFile(self.payload, "w") as archive:
            archive.writestr("12宮格直播監控.exe", "new exe")
            archive.writestr("config.json", '{"fresh": true}')
            archive.writestr("_internal/lib.txt", "new lib")
        self.target = self.root / "Programs" / "12宮格直播監控"

    def tearDown(self):
        self.tmp.cleanup()

    def test_fresh_install_extracts_payload(self):
        self.assertFalse(setup_exe.install(self.payload, self.target))
        self.assertEqual((self.target / "12宮格直播監控.exe").read_text(), "new exe")
        self.assertEqual((self.target / "config.json").read_text(), '{"fresh": true}')

    def test_upgrade_keeps_config_and_login_and_drops_old_files(self):
        (self.target / "data" / "chrome_monitor_profile").mkdir(parents=True)
        (self.target / "data" / "chrome_monitor_profile" / "Cookies").write_text("login")
        (self.target / "config.json").write_text('{"mine": true}')
        (self.target / "old.dll").write_text("stale")
        self.assertTrue(setup_exe.install(self.payload, self.target))
        self.assertEqual((self.target / "config.json").read_text(), '{"mine": true}')
        self.assertEqual((self.target / "data" / "chrome_monitor_profile" / "Cookies").read_text(), "login")
        self.assertFalse((self.target / "old.dll").exists())
        self.assertEqual((self.target / "_internal" / "lib.txt").read_text(), "new lib")

    def test_v1_profile_under_internal_is_migrated(self):
        legacy = self.target / "_internal" / "data" / "chrome_monitor_profile"
        legacy.mkdir(parents=True)
        (legacy / "Cookies").write_text("v1 login")
        setup_exe.install(self.payload, self.target)
        self.assertEqual((self.target / "data" / "chrome_monitor_profile" / "Cookies").read_text(), "v1 login")

    def test_upgrade_never_moves_or_deletes_user_state(self):
        (self.target / "data" / "chrome_monitor_profile").mkdir(parents=True)
        (self.target / "config.json").write_text('{"mine": true}')
        touched = []
        real_rmtree = setup_exe.shutil.rmtree
        setup_exe.shutil.rmtree = lambda path, *a, **k: (touched.append(Path(path).name), real_rmtree(path, *a, **k))
        try:
            setup_exe.install(self.payload, self.target)
        finally:
            setup_exe.shutil.rmtree = real_rmtree
        self.assertNotIn("data", touched)
        self.assertEqual((self.target / "config.json").read_text(), '{"mine": true}')

    def test_reinstall_over_same_version_is_idempotent(self):
        setup_exe.install(self.payload, self.target)
        setup_exe.install(self.payload, self.target)
        self.assertEqual((self.target / "12宮格直播監控.exe").read_text(), "new exe")

    def test_missing_payload_is_reported(self):
        with self.assertRaises(setup_exe.InstallError):
            setup_exe.install(self.root / "nope.zip", self.target)


class RunningCheckTests(unittest.TestCase):
    def test_detects_current_process_and_ignores_missing(self):
        self.assertTrue(setup_exe.app_is_running(Path(sys.executable).name))
        self.assertFalse(setup_exe.app_is_running("不存在的程式-12grid.exe"))


if __name__ == "__main__":
    unittest.main()
