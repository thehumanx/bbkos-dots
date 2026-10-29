"""bbkos-lock: starts hyprlock on the generated config when there is a usable one, else plain hyprlock, always under
the flock guard. A fake hyprlock in PATH records its arguments."""
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / "dotfiles/bin/.local/bin/bbkos-lock"
VALID = "background {\n    monitor =\n}\n"


class LockTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.state = self.dir / "theme"
        self.state.mkdir()
        self.run_dir = self.dir / "run"
        self.run_dir.mkdir()
        self.log = self.dir / "hyprlock.log"
        fake = self.dir / "bin"
        fake.mkdir()
        (fake / "hyprlock").write_text(f'#!/bin/sh\necho "$*" >> {self.log}\n[ -n "$FAKE_REJECT_CONFIG" ] && [ "$1" = -c ] && exit 1\nsleep "${{FAKE_HYPRLOCK_SLEEP:-0}}"\n')
        (fake / "hyprlock").chmod(0o755)
        flock = shutil.which("flock")
        self.assertIsNotNone(flock, "flock (util-linux) is needed")
        self.env = {"PATH": f"{fake}:/usr/bin:/bin", "XDG_RUNTIME_DIR": str(self.run_dir),
                    "BBKOS_STATE_DIR": str(self.state), "HOME": str(self.dir)}

    def run_lock(self, **extra):
        env = {**self.env, **extra}
        return subprocess.run([str(LOCK)], env=env, capture_output=True, text=True, timeout=20)

    def args(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_uses_generated_config(self):
        conf = self.state / "hyprlock.conf"
        conf.write_text(VALID)
        self.assertEqual(self.run_lock().returncode, 0)
        self.assertEqual(self.args(), [f"-c {conf}"])

    def test_missing_file_falls_back(self):
        self.assertEqual(self.run_lock().returncode, 0)
        self.assertEqual(self.args(), [""])

    def test_empty_file_falls_back(self):
        (self.state / "hyprlock.conf").write_text("")
        self.run_lock()
        self.assertEqual(self.args(), [""])

    def test_file_without_background_falls_back(self):
        (self.state / "hyprlock.conf").write_text("general {\n}\n")
        self.run_lock()
        self.assertEqual(self.args(), [""])

    def test_generated_config_rejected_falls_back(self):
        # hyprlock refusing the generated file (exit 1 before locking) must not leave the machine unlocked
        (self.state / "hyprlock.conf").write_text(VALID)
        r = self.run_lock(FAKE_REJECT_CONFIG="1")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.args(), [f"-c {self.state / 'hyprlock.conf'}", ""])

    def test_flock_guard_kept(self):
        first = subprocess.Popen([str(LOCK)], env={**self.env, "FAKE_HYPRLOCK_SLEEP": "3"})
        try:
            deadline = time.time() + 5
            while not self.args() and time.time() < deadline:
                time.sleep(0.05)
            self.assertEqual(len(self.args()), 1)
            second = self.run_lock()
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(len(self.args()), 1)      # the second request never started hyprlock
        finally:
            first.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
