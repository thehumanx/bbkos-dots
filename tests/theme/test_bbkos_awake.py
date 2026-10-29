"""bbkos-awake: the flag file is the state, and hypridle's idle listener suspends only when it is off. A fake
systemctl in PATH records the calls, so nothing is ever suspended."""
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "dotfiles/bin/.local/bin/bbkos-awake"


class AwakeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.state = self.dir / "state"
        self.home = self.dir / "home"
        self.home.mkdir()
        bin_ = self.dir / "bin"
        bin_.mkdir()
        self.calls = self.dir / "systemctl.log"
        fake = bin_ / "systemctl"
        fake.write_text(f'#!/bin/sh\necho "$*" >> {self.calls}\n')
        fake.chmod(0o755)
        self.screen = self.dir / "screen.log"
        for name in ("brightnessctl", "hyprctl"):
            f = bin_ / name
            f.write_text(f'#!/bin/sh\necho "{name} $*" >> {self.screen}\n')
            f.chmod(0o755)
        self.env = {"PATH": f"{bin_}:/usr/bin:/bin", "HOME": str(self.home),
                    "XDG_STATE_HOME": str(self.state)}

    def run_script(self, *args, **extra):
        return subprocess.run([str(SCRIPT), *args], env={**self.env, **extra}, capture_output=True, text=True,
                              timeout=20)

    def calls_list(self):
        return self.calls.read_text().splitlines() if self.calls.exists() else []

    def test_status_is_off_without_the_flag(self):
        r = self.run_script("status")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "off")

    def test_status_is_the_default_action(self):
        self.assertEqual(self.run_script().stdout.strip(), "off")
        self.run_script("on")
        self.assertEqual(self.run_script().stdout.strip(), "on")

    def test_on_creates_the_flag_under_xdg_state_home(self):
        self.assertEqual(self.run_script("on").returncode, 0)
        self.assertTrue((self.state / "bbkos/awake").exists())
        self.assertEqual(self.run_script("status").stdout.strip(), "on")

    def test_off_removes_the_flag_and_is_idempotent(self):
        (self.state / "bbkos").mkdir(parents=True)
        (self.state / "bbkos/awake").touch()
        self.assertEqual(self.run_script("off").returncode, 0)
        self.assertFalse((self.state / "bbkos/awake").exists())
        self.assertEqual(self.run_script("off").returncode, 0)
        self.assertEqual(self.run_script("status").stdout.strip(), "off")

    def test_state_falls_back_to_home_when_xdg_state_home_is_unset(self):
        env = {k: v for k, v in self.env.items() if k != "XDG_STATE_HOME"}
        r = subprocess.run([str(SCRIPT), "on"], env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 0)
        self.assertTrue((self.home / ".local/state/bbkos/awake").exists())

    def test_idle_suspend_does_nothing_while_awake(self):
        self.run_script("on")
        r = self.run_script("idle-suspend")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.calls_list(), [])

    def test_idle_suspend_suspends_when_awake_is_off(self):
        r = self.run_script("idle-suspend")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.calls_list(), ["suspend-then-hibernate"])

    def test_idle_lock_locks_only_when_awake_is_off(self):
        bin_ = self.dir / "bin"
        f = bin_ / "loginctl"
        f.write_text(f'#!/bin/sh\necho "$*" >> {self.calls}\n')
        f.chmod(0o755)
        self.run_script("on")
        self.assertEqual(self.run_script("idle-lock").returncode, 0)
        self.assertEqual(self.calls_list(), [])
        self.run_script("off")
        self.run_script("idle-lock")
        self.assertEqual(self.calls_list(), ["lock-session"])

    def screen_calls(self):
        return self.screen.read_text().splitlines() if self.screen.exists() else []

    def test_idle_dim_dims_only_when_awake_is_off_and_resume_restores_only_after_a_dim(self):
        self.run_script("idle-dim-resume")                       # nothing was dimmed: must not restore a stale level
        self.assertEqual(self.screen_calls(), [])
        self.run_script("idle-dim")
        self.assertEqual(self.screen_calls(), ["brightnessctl -s set 10"])
        self.run_script("idle-dim-resume")
        self.assertEqual(self.screen_calls()[-1], "brightnessctl -r")
        self.run_script("idle-dim-resume")                       # the marker is gone: no second restore
        self.assertEqual(len(self.screen_calls()), 2)

    def test_awake_mode_keeps_the_screen_on(self):
        self.run_script("on")
        self.screen.unlink(missing_ok=True)
        for action in ("idle-dim", "idle-kbd", "idle-screen-off"):
            self.assertEqual(self.run_script(action).returncode, 0)
        self.assertEqual(self.screen_calls(), [])

    def test_screen_off_runs_when_awake_is_off(self):
        self.run_script("idle-screen-off")
        self.assertEqual(len(self.screen_calls()), 1)
        self.assertIn("dpms", self.screen_calls()[0])
        self.assertIn("off", self.screen_calls()[0])

    def test_turning_awake_on_while_dimmed_restores_the_screen(self):
        self.run_script("idle-dim")
        self.run_script("idle-kbd")
        self.screen.unlink()
        self.run_script("on")
        calls = self.screen_calls()
        self.assertIn("brightnessctl -r", calls)
        self.assertIn("brightnessctl -rd platform::kbd_backlight", calls)
        self.assertTrue(any("dpms" in c and "on" in c for c in calls))

    def test_unknown_action_prints_usage_and_exits_2(self):
        r = self.run_script("sleep")
        self.assertEqual(r.returncode, 2)
        self.assertIn("usage:", r.stderr)
        self.assertEqual(self.calls_list(), [])


if __name__ == "__main__":
    unittest.main()
