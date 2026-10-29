"""The touchpad safety net: the installer lays out the helper and the sudoers rule, the user command calls the helper
through sudo and reports the result, and the root helper refuses arguments. The root helper itself reloads a kernel
driver, so it is not run here (that needs root); a fake sudo and a fake helper stand in for it."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALL = ROOT / "scripts/install-touchpad-helper.sh"
HELPER = ROOT / "touchpad/bbkos-touchpad-reload"
RESET = ROOT / "dotfiles/bin/.local/bin/bbkos-touchpad-reset"


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.prefix, True)

    def run_script(self, *args):
        return subprocess.run(["bash", str(INSTALL), *args], capture_output=True, text=True)

    def test_install_lays_out_files(self):
        r = self.run_script("--prefix", self.prefix, "--user", "alice")
        self.assertEqual(r.returncode, 0, r.stderr)
        helper = Path(self.prefix, "usr/local/sbin/bbkos-touchpad-reload")
        self.assertTrue(helper.is_file())
        self.assertTrue(helper.stat().st_mode & 0o100)
        self.assertEqual(helper.read_bytes(), HELPER.read_bytes())
        self.assertEqual(Path(self.prefix, "etc/sudoers.d/bbkos-touchpad").read_text(),
                         'alice ALL=(root) NOPASSWD: /usr/local/sbin/bbkos-touchpad-reload ""\n')

    def test_uninstall_removes_both(self):
        self.run_script("--prefix", self.prefix, "--user", "alice")
        r = self.run_script("--uninstall", "--prefix", self.prefix)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(Path(self.prefix, "usr/local/sbin/bbkos-touchpad-reload").exists())
        self.assertFalse(Path(self.prefix, "etc/sudoers.d/bbkos-touchpad").exists())
        self.assertEqual(self.run_script("--uninstall", "--prefix", self.prefix).returncode, 0)

    def test_refuses_real_install_without_root(self):
        r = self.run_script("--user", "alice")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("needs root", r.stderr)

    def test_refuses_bad_user_names(self):
        for bad in ("root", "a b", "x;y", ""):
            r = self.run_script("--prefix", self.prefix, "--user", bad)
            self.assertNotEqual(r.returncode, 0, bad)


class ResetTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        bin_ = self.dir / "bin"
        bin_.mkdir()
        self.calls = self.dir / "sudo.log"
        self.sudo = bin_ / "sudo"
        self.helper = self.dir / "helper"
        self.helper.write_text("#!/bin/sh\n")
        self.helper.chmod(0o755)
        self.set_sudo(0, "touchpad is back")
        self.env = {"PATH": f"{bin_}:/usr/bin:/bin", "BBKOS_TOUCHPAD_HELPER": str(self.helper)}

    def set_sudo(self, rc, text):
        self.sudo.write_text(f'#!/bin/sh\necho "$*" >> {self.calls}\necho "{text}"\nexit {rc}\n')
        self.sudo.chmod(0o755)

    def run_reset(self, **extra):
        return subprocess.run([str(RESET)], env={**self.env, **extra}, capture_output=True, text=True, timeout=20)

    def test_calls_the_helper_through_noninteractive_sudo(self):
        r = self.run_reset()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.calls.read_text().strip(), f"-n {self.helper}")
        self.assertIn("touchpad is back", r.stdout)

    def test_reports_the_helper_failure_and_its_exit_code(self):
        self.set_sudo(1, "did not come back")
        r = self.run_reset()
        self.assertEqual(r.returncode, 1)
        self.assertIn("reset failed (exit 1)", r.stdout)
        self.assertIn("did not come back", r.stdout)

    def test_missing_helper_says_how_to_install_it(self):
        r = self.run_reset(BBKOS_TOUCHPAD_HELPER=str(self.dir / "nope"))
        self.assertEqual(r.returncode, 3)
        self.assertIn("install-touchpad-helper.sh", r.stdout)
        self.assertFalse(self.calls.exists())


class RootHelperTest(unittest.TestCase):
    def test_refuses_arguments_before_doing_anything(self):
        r = subprocess.run([str(HELPER), "--anything"], capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 2)
        self.assertIn("no arguments", r.stderr)

    def test_always_loads_the_driver_again(self):
        text = HELPER.read_text()
        self.assertLess(text.index('modprobe -r "$module" ||'), text.index('modprobe "$module" ||'))


if __name__ == "__main__":
    unittest.main()
