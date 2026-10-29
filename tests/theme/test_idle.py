"""Idle and lock settings: the generated hypridle.conf, the restart only when it changed, and bbkos-idle choosing the file.
Fake systemctl and hypridle in PATH record their calls, so nothing is restarted for real."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))
from bbkos_theme import reload as R          # noqa: E402
from bbkos_theme import render, settings as S  # noqa: E402

IDLE_SCRIPT = ROOT / "dotfiles/bin/.local/bin/bbkos-idle"


def timeouts(text):
    return [int(l.split("=")[1]) for l in text.splitlines() if l.strip().startswith("timeout")]


class RenderTest(unittest.TestCase):
    def conf(self, **over):
        s, _ = S.validate({"version": 1, "idle": over})
        return render.render_hypridle(s)

    def test_defaults_keep_the_old_timers(self):
        self.assertEqual(timeouts(self.conf()), [150, 150, 300, 330, 900])

    def test_every_step_goes_through_bbkos_awake(self):
        text = self.conf()
        for step in ("idle-dim", "idle-kbd", "idle-lock", "idle-screen-off", "idle-suspend"):
            self.assertIn(f"on-timeout = bbkos-awake {step}", text)
        self.assertNotIn("on-timeout = loginctl", text)

    def test_zero_means_no_listener(self):
        text = self.conf(lock=0, suspend=0)
        self.assertEqual(timeouts(text), [150, 150, 330])
        self.assertNotIn("idle-lock", text)
        self.assertEqual(timeouts(self.conf(dim=0, lock=0, screenOff=0, suspend=0)), [])
        self.assertIn("lock_cmd = bbkos-lock", self.conf(dim=0, lock=0, screenOff=0, suspend=0))   # sleep still locks

    def test_dim_also_switches_the_keyboard_light(self):
        self.assertEqual(timeouts(self.conf(dim=60))[:2], [60, 60])

    def test_values_snap_to_30_seconds_and_clamp(self):
        s, warns = S.validate({"version": 1, "idle": {"dim": 100, "lock": 99999, "screenOff": -5}})
        self.assertEqual((s["idle"]["dim"], s["idle"]["lock"], s["idle"]["screenOff"]), (90, 3600, 0))
        self.assertTrue(warns)


class ReloadTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.state = self.dir / "state"
        self.state.mkdir()
        self.log = self.dir / "calls.log"
        bin_ = self.dir / "bin"
        bin_.mkdir()
        f = bin_ / "systemctl"
        f.write_text(f'#!/bin/sh\necho "$*" >> {self.log}\ncase "$*" in *is-active*) exit ${{FAKE_ACTIVE:-0}};; esac\n')
        f.chmod(0o755)
        self.env = {"PATH": f"{bin_}:/usr/bin:/bin", "HOME": str(self.dir)}

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_restarts_when_the_running_file_differs(self):
        (self.state / "hypridle.conf").write_text("general {\n}\n# new\n")
        (self.state / "hypridle-active.conf").write_text("general {\n}\n# old\n")
        self.assertEqual(R.reload_hypridle(self.state, self.env, real_home=self.dir), [])
        self.assertIn("--user restart hypridle.service", self.calls())

    def test_never_restarts_the_live_unit_from_a_temporary_home(self):
        (self.state / "hypridle.conf").write_text("general {\n}\n")
        R.reload_hypridle(self.state, self.env)                      # no HOME in env
        R.reload_hypridle(self.state, {**self.env, "HOME": str(self.dir)})   # a home that is not the real one
        self.assertEqual(self.calls(), [])

    def test_nothing_when_unchanged_or_missing(self):
        self.assertEqual(R.reload_hypridle(self.state, self.env, real_home=self.dir), [])
        (self.state / "hypridle.conf").write_text("general {\n}\n")
        (self.state / "hypridle-active.conf").write_text("general {\n}\n")
        R.reload_hypridle(self.state, self.env, real_home=self.dir)
        self.assertEqual(self.calls(), [])

    def test_no_restart_when_hypridle_is_not_running(self):
        (self.state / "hypridle.conf").write_text("general {\n}\n")
        R.reload_hypridle(self.state, {**self.env, "FAKE_ACTIVE": "3"}, real_home=self.dir)
        self.assertEqual([c for c in self.calls() if "restart" in c], [])


class ScriptTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.state = self.dir / "state"
        self.state.mkdir()
        self.log = self.dir / "hypridle.log"
        bin_ = self.dir / "bin"
        bin_.mkdir()
        f = bin_ / "hypridle"
        f.write_text(f'#!/bin/sh\necho "$*" > {self.log}\n')
        f.chmod(0o755)
        self.env = {"PATH": f"{bin_}:/usr/bin:/bin", "BBKOS_STATE_DIR": str(self.state)}

    def run_script(self):
        subprocess.run([str(IDLE_SCRIPT)], env=self.env, check=True, timeout=10)
        return self.log.read_text().strip()

    def test_uses_the_generated_file_and_records_it(self):
        (self.state / "hypridle.conf").write_text("general {\n}\n")
        self.assertEqual(self.run_script(), f"-c {self.state / 'hypridle.conf'}")
        self.assertEqual((self.state / "hypridle-active.conf").read_text(), "general {\n}\n")

    def test_falls_back_to_the_static_config(self):
        self.assertEqual(self.run_script(), "")
        (self.state / "hypridle.conf").write_text("garbage\n")
        self.assertEqual(self.run_script(), "")
        self.assertFalse((self.state / "hypridle-active.conf").exists())


if __name__ == "__main__":
    unittest.main()
