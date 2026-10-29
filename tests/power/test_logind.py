"""power/bbkos-logind-apply: the lid and power-button drop-in. Everything runs in temp dirs; systemctl is never called."""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))
from bbkos_theme import settings as S  # noqa: E402


def load_helper():
    path = str(ROOT / "power/bbkos-logind-apply")
    loader = importlib.machinery.SourceFileLoader("bbkos_logind_apply", path)
    spec = importlib.util.spec_from_loader("bbkos_logind_apply", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


H = load_helper()


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.conf = os.path.join(self.dir, "logind.conf.d")
        self.settings = os.path.join(self.dir, "settings.json")

    def write_settings(self, session):
        Path(self.settings).write_text(json.dumps({"version": 1, "session": session}))

    def run_main(self, **env):
        base = {"BBKOS_LOGIND_DIR": self.conf, "BBKOS_LOGIND_SETTINGS": self.settings, "BBKOS_LOGIND_NORELOAD": "1"}
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = H.main([], {**base, **env})
        return rc, json.loads(out.getvalue())


class ValuesTest(Base):
    def test_the_word_lists_match_the_settings_schema(self):
        self.assertEqual(H.LID_ACTIONS, S.LID_ACTIONS)
        self.assertEqual(H.POWERKEY_ACTIONS, S.POWERKEY_ACTIONS)
        self.assertEqual(H.DEFAULTS, S.SESSION_DEFAULTS)

    def test_defaults_render_the_file_task09_wrote(self):
        text = H.render(H.DEFAULTS)
        for line in ("HandleLidSwitch=suspend-then-hibernate", "HandleLidSwitchExternalPower=suspend-then-hibernate",
                     "HandleLidSwitchDocked=ignore", "HandlePowerKey=ignore", "HandlePowerKeyLongPress=poweroff"):
            self.assertIn(line, text.splitlines())

    def test_nothing_but_the_allowed_words_reaches_the_file(self):
        self.write_settings({"lidBattery": "ignore\nHandlePowerKey=poweroff", "lidPower": "poweroff", "powerKeyLong": ["x"]})
        rc, res = self.run_main()
        self.assertEqual(rc, 0)
        text = Path(self.conf, "bbkos.conf").read_text()
        self.assertEqual(res["applied"], H.DEFAULTS)                 # the hostile word, the unlisted action and the list: all defaults
        self.assertEqual(text.count("HandlePowerKey="), 1)
        self.assertIn("HandlePowerKey=ignore", text)

    def test_choices_reach_logind_keys(self):
        self.write_settings({"lidBattery": "hibernate", "lidPower": "ignore", "powerKeyLong": "suspend"})
        self.run_main()
        lines = Path(self.conf, "bbkos.conf").read_text().splitlines()
        for line in ("HandleLidSwitch=hibernate", "HandleLidSwitchExternalPower=ignore", "HandlePowerKeyLongPress=suspend"):
            self.assertIn(line, lines)


class WriteTest(Base):
    def test_written_once_and_reloaded_only_when_changed(self):
        self.write_settings({"lidPower": "ignore"})
        with mock.patch.object(H, "reload_logind", return_value=None) as rl:
            res = H.apply_session(H.read_session_settings(self.settings, os.getuid()), self.conf)
            self.assertEqual((res["changed"], rl.call_count), (True, 1))
            res = H.apply_session(H.read_session_settings(self.settings, os.getuid()), self.conf)
            self.assertEqual((res["changed"], rl.call_count), (False, 1))
        self.assertEqual(oct(os.stat(os.path.join(self.conf, "bbkos.conf")).st_mode & 0o777), "0o644")
        self.assertEqual([f for f in os.listdir(self.conf)], ["bbkos.conf"])           # no temp file left

    def test_a_failed_reload_is_reported_but_the_file_stays(self):
        with mock.patch.object(H, "reload_logind", return_value="cannot reload logind: boom"):
            res = H.apply_session(dict(H.DEFAULTS), self.conf)
        self.assertEqual(res["errors"], ["cannot reload logind: boom"])
        self.assertTrue(os.path.isfile(os.path.join(self.conf, "bbkos.conf")))

    def test_reload_uses_systemctl_reload_and_reports_its_first_line(self):
        calls = []

        def runner(cmd, **kw):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 1, "", "Failed to reload\nsecond\n")
        self.assertEqual(H.reload_logind(runner), "cannot reload logind: Failed to reload")
        self.assertEqual(calls, [["/usr/bin/systemctl", "reload", "systemd-logind.service"]])


class SettingsFileTest(Base):
    def test_a_symlink_is_followed_but_a_foreign_owner_is_refused(self):
        self.write_settings({"lidBattery": "lock"})
        link = os.path.join(self.dir, "link.json")
        os.symlink(self.settings, link)
        self.assertEqual(H.read_session_settings(link, os.getuid())["lidBattery"], "lock")
        with self.assertRaises(H.SettingsError):
            H.read_session_settings(self.settings, os.getuid() + 1)

    def test_bad_files_are_errors_not_defaults(self):
        rc, res = self.run_main()
        self.assertEqual(rc, 2)
        self.assertIn("cannot read", res["errors"][0])
        Path(self.settings).write_text("[1, 2]")
        self.assertEqual(self.run_main()[0], 2)
        Path(self.settings).write_text("x" * 70000)
        self.assertEqual(self.run_main()[0], 2)
        self.assertFalse(os.path.exists(self.conf))                        # nothing is written when the settings cannot be read

    def test_arguments_are_refused_and_a_missing_section_means_defaults(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(H.main(["x"], {}), 2)
        Path(self.settings).write_text(json.dumps({"version": 1}))
        rc, res = self.run_main()
        self.assertEqual((rc, res["applied"]), (0, H.DEFAULTS))

    def test_the_environment_cannot_redirect_a_root_run(self):
        with mock.patch.object(H.os, "geteuid", return_value=0):
            self.assertEqual(H.resolve_paths({"BBKOS_LOGIND_DIR": "/tmp/x", "BBKOS_LOGIND_SETTINGS": "/tmp/y"}),
                             (H.DEFAULT_DIR, None, True))


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.prefix, True)

    def run_script(self, *args):
        return subprocess.run(["bash", str(ROOT / "scripts/install-logind-helper.sh"), *args], capture_output=True, text=True)

    def test_install_and_uninstall(self):
        r = self.run_script("--prefix", self.prefix, "--user", "alice")
        self.assertEqual(r.returncode, 0, r.stderr)
        helper = Path(self.prefix, "usr/local/sbin/bbkos-logind-apply")
        self.assertEqual(helper.read_bytes(), (ROOT / "power/bbkos-logind-apply").read_bytes())
        self.assertEqual(Path(self.prefix, "etc/sudoers.d/bbkos-logind").read_text(),
                         'alice ALL=(root) NOPASSWD: /usr/local/sbin/bbkos-logind-apply ""\n')
        self.assertEqual(self.run_script("--uninstall", "--prefix", self.prefix).returncode, 0)
        self.assertFalse(helper.exists())

    def test_refuses_real_install_without_root_and_bad_user_names(self):
        self.assertIn("needs root", self.run_script("--user", "alice").stderr)
        self.assertNotEqual(self.run_script("--prefix", self.prefix, "--user", "root").returncode, 0)
        self.assertNotEqual(self.run_script("--prefix", self.prefix, "--user", "a b").returncode, 0)


if __name__ == "__main__":
    unittest.main()
