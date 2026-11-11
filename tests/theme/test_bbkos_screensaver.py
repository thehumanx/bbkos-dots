"""bbkos-screensaver: the guards (no tte, blank logo, lock running, already running) and one fullscreen kitty per monitor.
Fake hyprctl, pgrep, pkill and bbkos-branding in PATH record what would happen; nothing is opened or killed for real."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "dotfiles/bin/.local/bin/bbkos-screensaver"
LOCK = ROOT / "dotfiles/bin/.local/bin/bbkos-lock"


class ScreensaverTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.bin = self.dir / "bin"
        self.bin.mkdir()
        self.log = self.dir / "calls.log"
        self.settings = self.dir / "settings.json"
        self.fake("tte", "exit 0")
        self.fake("bbkos-branding", 'printf "%s" "${FAKE_LOGO-LOGO}"')
        self.fake("hyprctl", f'if [ "$1" = monitors ]; then printf "%s" "$FAKE_MONITORS"; else echo "hyprctl $*" >> {self.log}; fi')
        self.fake("pgrep", f'case "$*" in *hyprlock*) [ -n "$FAKE_HYPRLOCK" ];; *) [ -n "$FAKE_RUNNING" ];; esac')
        self.fake("pkill", f'echo "pkill $*" >> {self.log}')
        self.env = {"PATH": f"{self.bin}:/usr/bin:/bin", "HOME": str(self.dir), "XDG_RUNTIME_DIR": str(self.dir),
                    "BBKOS_SETTINGS": str(self.settings), "FAKE_MONITORS": '[{"name": "eDP-1"}]'}

    def fake(self, name, body):
        f = self.bin / name
        f.write_text(f"#!/bin/sh\n{body}\n")
        f.chmod(0o755)

    def run_it(self, *args, stdin=None, **extra):
        return subprocess.run([str(SCRIPT), *args], env={**self.env, **extra}, capture_output=True, text=True, timeout=20,
                              input=stdin)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_starts_one_window_per_monitor(self):
        mons = json.dumps([{"name": "eDP-1"}, {"name": "HDMI-A-1"}])
        self.assertEqual(self.run_it(FAKE_MONITORS=mons).returncode, 0)
        starts = [c for c in self.calls() if c.startswith("hyprctl dispatch")]
        self.assertEqual(len(starts), 2)
        self.assertIn('monitor="eDP-1"', starts[0])
        self.assertIn('monitor="HDMI-A-1"', starts[1])
        self.assertIn("org.bbkos.screensaver", starts[0])
        self.assertIn("--play decrypt", starts[0])

    def test_effect_comes_from_settings(self):
        self.settings.write_text('{"branding": {"effect": "matrix"}}')
        self.run_it()
        self.assertIn("--play matrix", self.calls()[0])

    def test_unknown_effect_falls_back(self):
        self.settings.write_text('{"branding": {"effect": "x; reboot"}}')
        self.run_it()
        self.assertIn("--play decrypt", self.calls()[0])
        self.assertNotIn("reboot", self.calls()[0])

    def test_no_tte_does_nothing(self):
        bare = self.dir / "bare"   # only the tools the script needs, so a tte installed on this machine is not found
        bare.mkdir()
        for tool in ("bash", "env", "tr", "jq"):
            (bare / tool).symlink_to(subprocess.run(["which", tool], capture_output=True, text=True).stdout.strip())
        for name in ("bbkos-branding", "hyprctl", "pgrep", "pkill"):
            (bare / name).symlink_to(self.bin / name)
        r = subprocess.run([str(SCRIPT)], env={**self.env, "PATH": str(bare)}, capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_blank_logo_does_nothing_and_says_so(self):
        self.assertEqual(self.run_it(FAKE_LOGO="  \n").returncode, 3)    # 3: not started, so bbkos-awake dims instead
        self.assertEqual(self.calls(), [])

    def test_lock_running_does_nothing_and_says_so(self):
        self.assertEqual(self.run_it(FAKE_HYPRLOCK="1").returncode, 3)
        self.assertEqual(self.calls(), [])

    def test_second_start_is_a_noop(self):
        self.assertEqual(self.run_it(FAKE_RUNNING="1").returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_a_key_in_one_window_closes_every_window(self):
        self.fake("clear", "exit 0")
        self.fake("tte", "exit 0")
        r = self.run_it("--play", "decrypt", stdin="x")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(any("org.bbkos.screensaver" in c for c in self.calls() if c.startswith("pkill")), self.calls())

    def test_stop_kills_by_class(self):
        self.assertEqual(self.run_it("stop").returncode, 0)
        self.assertTrue(any("org.bbkos.screensaver" in c for c in self.calls() if c.startswith("pkill")))

    def test_lock_stops_the_screensaver_first(self):
        run = self.dir / "run"
        run.mkdir()
        self.fake("bbkos-screensaver", f'echo "screensaver $*" >> {self.log}')
        self.fake("hyprlock", f'echo hyprlock >> {self.log}')
        env = {**self.env, "XDG_RUNTIME_DIR": str(run), "BBKOS_STATE_DIR": str(self.dir / "none")}
        subprocess.run([str(LOCK)], env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(self.calls()[:2], ["screensaver stop", "hyprlock"])


if __name__ == "__main__":
    unittest.main()
