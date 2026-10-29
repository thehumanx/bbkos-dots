"""Night light: the generated hyprsunset.conf, the validation of the times, and when hyprsunset.service is started, restarted
or stopped. Fake systemctl and hyprsunset in PATH record the calls, so the live unit is never touched."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dotfiles/bin/.local/lib"))
from bbkos_theme import reload as R, render, settings as S  # noqa: E402


def settings(**night):
    s, _ = S.validate({"version": 1, "nightlight": night})
    return s


class RenderTest(unittest.TestCase):
    def test_off_is_a_neutral_profile(self):
        text = render.render_hyprsunset_conf(settings())
        self.assertIn("identity = true", text)
        self.assertNotIn("temperature", text)

    def test_on_is_one_warm_profile_all_day(self):
        text = render.render_hyprsunset_conf(settings(mode="on", temperature=3500))
        self.assertEqual(text.count("profile {"), 1)
        self.assertIn("time = 00:00", text)
        self.assertIn("temperature = 3500", text)

    def test_schedule_is_a_neutral_profile_at_the_end_and_a_warm_one_at_the_start(self):
        text = render.render_hyprsunset_conf(settings(mode="schedule", start="22:30", end="6:45", temperature=3000))
        self.assertEqual(text.count("profile {"), 2)
        self.assertIn("time = 6:45\n    identity = true", text)
        self.assertIn("time = 22:30\n    temperature = 3000", text)

    def test_bad_times_and_ranges_are_refused_or_clamped(self):
        for bad in ("25:00", "7", "07:60", "07:00; rm", "", "7:5"):
            s, warns = S.validate({"version": 1, "nightlight": {"start": bad}})
            self.assertEqual(s["nightlight"]["start"], "21:00", bad)
            self.assertTrue(warns)
        s, _ = S.validate({"version": 1, "nightlight": {"temperature": 100, "mode": "sometimes"}})
        self.assertEqual((s["nightlight"]["temperature"], s["nightlight"]["mode"]), (2500, "off"))


class ReloadTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.state = self.dir / "state"
        self.state.mkdir()
        (self.dir / ".config/hypr").mkdir(parents=True)
        self.conf = self.dir / ".config/hypr/hyprsunset.conf"
        self.conf.write_text("profile {\n}\n")
        self.log = self.dir / "calls.log"
        bin_ = self.dir / "bin"
        bin_.mkdir()
        f = bin_ / "systemctl"
        f.write_text(f'#!/bin/sh\necho "$*" >> {self.log}\n'
                     'case "$*" in *is-active*) exit ${FAKE_ACTIVE:-3};; *is-enabled*) exit ${FAKE_ENABLED:-1};; esac\n')
        f.chmod(0o755)
        (bin_ / "hyprsunset").write_text("#!/bin/sh\n")
        (bin_ / "hyprsunset").chmod(0o755)
        self.env = {"PATH": f"{bin_}:/usr/bin:/bin", "HOME": str(self.dir)}

    def run_reload(self, mode, **env):
        return R.reload_nightlight(self.state, {**self.env, **env}, settings(mode=mode), real_home=self.dir)

    def calls(self):
        return [c for c in (self.log.read_text().splitlines() if self.log.exists() else []) if "is-" not in c]

    def test_on_and_not_running_enables_and_starts(self):
        self.assertEqual(self.run_reload("on"), [])
        self.assertEqual(self.calls(), ["--user enable hyprsunset.service", "--user start hyprsunset.service"])
        self.assertEqual((self.state / "nightlight-active.conf").read_text(), "profile {\n}\n")

    def test_nothing_while_running_with_the_same_file(self):
        (self.state / "nightlight-active.conf").write_text("profile {\n}\n")
        self.run_reload("schedule", FAKE_ACTIVE="0")
        self.assertEqual(self.calls(), [])

    def test_a_changed_file_restarts(self):
        (self.state / "nightlight-active.conf").write_text("old\n")
        self.run_reload("on", FAKE_ACTIVE="0")
        self.assertEqual(self.calls(), ["--user enable hyprsunset.service", "--user restart hyprsunset.service"])

    def test_off_stops_and_disables_only_when_needed(self):
        self.run_reload("off")
        self.assertEqual(self.calls(), [])
        self.run_reload("off", FAKE_ACTIVE="0")
        self.assertEqual(self.calls(), ["--user disable --now hyprsunset.service"])

    def test_off_disables_an_enabled_unit_that_is_not_running(self):
        self.run_reload("off", FAKE_ENABLED="0")
        self.assertEqual(self.calls(), ["--user disable --now hyprsunset.service"])

    def test_never_touches_the_live_unit_from_a_temporary_home_or_without_hyprsunset(self):
        R.reload_nightlight(self.state, self.env, settings(mode="on"))                 # HOME is not the real home
        R.reload_nightlight(self.state, {**self.env, "PATH": "/usr/bin:/bin"}, settings(mode="on"), real_home=self.dir,
                            which=lambda name, path=None: None if name == "hyprsunset" else "/usr/bin/" + name)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
