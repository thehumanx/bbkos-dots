"""scripts/install-dictation.sh: the owner-run installer (docs/modules/dictation.md). Nothing here installs anything."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/install-dictation.sh"


def run(*args, env=None):
    full = {"PATH": os.environ["PATH"], **(env or {})}
    return subprocess.run(["/usr/bin/bash", str(SCRIPT), *args], capture_output=True, text=True, env=full, timeout=20)


class InstallTest(unittest.TestCase):
    def test_dry_run_prints_yay_line_first(self):
        with tempfile.TemporaryDirectory() as home:
            r = run("--dry-run", env={"HOME": home})
        self.assertEqual(r.returncode, 0, r.stderr)
        steps = [ln for ln in r.stdout.splitlines() if ln.startswith("would run:")]
        self.assertIn("yay -S voxtype", steps[0])
        self.assertNotIn("voxtype-bin", steps[0])             # the source package: the prebuilt one is ~700 MB of GPU variants
        for want in ("stow --no-folding -d", "voxtype setup --download", "voxtype setup systemd",
                     "systemctl --user enable --now voxtype"):
            self.assertTrue(any(want in s for s in steps), want)

    def test_dry_run_changes_nothing(self):
        with tempfile.TemporaryDirectory() as home:
            r = run("--dry-run", env={"HOME": home})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(list(Path(home).iterdir()), [])

    def test_refuses_root(self):
        r = run("--dry-run", env={"BBKOS_FAKE_EUID": "0", "HOME": "/nonexistent"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("root", r.stderr)

    def test_stops_when_voxtype_missing(self):
        with tempfile.TemporaryDirectory() as empty:
            r = subprocess.run(["/usr/bin/bash", str(SCRIPT)], capture_output=True, text=True,
                               env={"PATH": empty, "HOME": empty}, timeout=20)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("yay -S voxtype", r.stderr)
            self.assertEqual(list(Path(empty).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
