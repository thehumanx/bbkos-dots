import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/install-power-helper.sh"
HELPER = ROOT / "power/bbkos-power-apply"


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.prefix, True)

    def run_script(self, *args):
        return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True)

    def test_install_lays_out_files(self):
        r = self.run_script("--prefix", self.prefix, "--user", "alice")
        self.assertEqual(r.returncode, 0, r.stderr)
        helper = Path(self.prefix, "usr/local/sbin/bbkos-power-apply")
        self.assertTrue(helper.is_file())
        self.assertTrue(helper.stat().st_mode & 0o100)
        self.assertEqual(helper.read_bytes(), HELPER.read_bytes())
        sudoers = Path(self.prefix, "etc/sudoers.d/bbkos-power")
        self.assertEqual(sudoers.read_text(),
                         'alice ALL=(root) NOPASSWD: /usr/local/sbin/bbkos-power-apply ""\n')

    def test_uninstall_removes_both(self):
        self.run_script("--prefix", self.prefix, "--user", "alice")
        r = self.run_script("--uninstall", "--prefix", self.prefix)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(Path(self.prefix, "usr/local/sbin/bbkos-power-apply").exists())
        self.assertFalse(Path(self.prefix, "etc/sudoers.d/bbkos-power").exists())
        self.assertEqual(self.run_script("--uninstall", "--prefix", self.prefix).returncode, 0)

    def test_refuses_real_install_without_root(self):
        r = self.run_script("--user", "alice")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("needs root", r.stderr)


if __name__ == "__main__":
    unittest.main()
