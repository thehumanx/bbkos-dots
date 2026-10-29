import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))

from bbkos_theme import settings as S  # noqa: E402


def load_helper():
    """The helper has no .py extension (it is installed as a command), so load it by path."""
    path = str(ROOT / "power/bbkos-power-apply")
    loader = importlib.machinery.SourceFileLoader("bbkos_power_apply", path)
    spec = importlib.util.spec_from_loader("bbkos_power_apply", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


H = load_helper()
AVAILABLE = "default performance balance_performance balance_power power"


class Fake:
    """A fake /sys tree (22 CPUs, turbo, the MMIO RAPL limit) plus a run directory, in temp dirs."""

    def __init__(self, test):
        self.sysfs = tempfile.mkdtemp()
        self.run_dir = tempfile.mkdtemp()
        test.addCleanup(shutil.rmtree, self.sysfs, True)
        test.addCleanup(shutil.rmtree, self.run_dir, True)
        for i in range(22):
            d = Path(self.sysfs, f"devices/system/cpu/cpu{i}/cpufreq")
            d.mkdir(parents=True)
            (d / "energy_performance_preference").write_text("balance_power\n")
            (d / "energy_performance_available_preferences").write_text(AVAILABLE + "\n")
        p = Path(self.sysfs, "devices/system/cpu/intel_pstate")
        p.mkdir(parents=True)
        (p / "no_turbo").write_text("0\n")
        m = Path(self.sysfs, "class/powercap/intel-rapl-mmio:0")
        m.mkdir(parents=True)
        (m / "constraint_0_power_limit_uw").write_text("28000000\n")
        b = Path(self.sysfs, "class/power_supply/BAT0")
        b.mkdir(parents=True)
        (b / "charge_types").write_text("[Fast] Standard Long_Life\n")

    def epp(self, i):
        return Path(self.sysfs, f"devices/system/cpu/cpu{i}/cpufreq/energy_performance_preference").read_text().strip()

    def all_epp(self):
        return {self.epp(i) for i in range(22)}

    def set_available(self, text):
        for i in range(22):
            Path(self.sysfs, f"devices/system/cpu/cpu{i}/cpufreq/energy_performance_available_preferences").write_text(text + "\n")

    @property
    def turbo_file(self):
        return Path(self.sysfs, "devices/system/cpu/intel_pstate/no_turbo")

    @property
    def cap_file(self):
        return Path(self.sysfs, "class/powercap/intel-rapl-mmio:0/constraint_0_power_limit_uw")

    @property
    def charge_file(self):
        return Path(self.sysfs, "class/power_supply/BAT0/charge_types")

    def charge(self):
        return self.charge_file.read_text().strip()

    def turbo(self):
        return self.turbo_file.read_text().strip()

    def cap(self):
        return int(self.cap_file.read_text().strip())

    def state(self):
        return json.loads(Path(self.run_dir, "orig.json").read_text())

    def apply(self, power, profile):
        return H.apply_power(power, profile, self.sysfs, self.run_dir)


def power(**over):
    p = dict(S.DEFAULTS["power"])
    p.update(over)
    return p


class HelperTest(unittest.TestCase):
    def setUp(self):
        self.f = Fake(self)

    def test_enum_lists_match_settings_store(self):
        self.assertEqual(tuple(H.EPP_VALUES), S.POWER_EPP)
        self.assertEqual(tuple(H.TURBO_VALUES), S.POWER_TURBO)
        self.assertEqual(tuple(H.CHARGE_VALUES), S.POWER_CHARGE)
        self.assertEqual(H.PROFILE_PREFIX, {"power-saver": "saver", "balanced": "balanced", "performance": "performance"})

    def test_default_writes_nothing(self):
        res = self.f.apply(power(), "balanced")
        self.assertEqual(res["applied"], {"epp": None, "turbo": None, "cap": None, "charge": None})
        self.assertEqual(self.f.all_epp(), {"balance_power"})
        self.assertEqual((self.f.turbo(), self.f.cap()), ("0", 28000000))
        self.assertEqual(self.f.charge(), "[Fast] Standard Long_Life")
        self.assertEqual(res["errors"], [])

    def test_epp_written_to_every_cpu(self):
        res = self.f.apply(power(balancedEpp="power"), "balanced")
        self.assertEqual(self.f.all_epp(), {"power"})
        self.assertEqual(res["applied"]["epp"], "power")
        self.assertEqual(res["profile"], "balanced")

    def test_setting_belongs_to_its_own_profile(self):
        self.f.apply(power(balancedEpp="power"), "performance")
        self.assertEqual(self.f.all_epp(), {"balance_power"})

    def test_epp_not_in_available_list_is_skipped(self):
        self.f.set_available("default performance balance_performance power")
        res = self.f.apply(power(balancedEpp="balance_power"), "balanced")
        self.assertEqual(self.f.all_epp(), {"balance_power"})
        self.assertEqual(res["errors"], [])
        self.assertTrue(any("balance_power" in s for s in res["skipped"]))
        self.assertIsNone(res["applied"]["epp"])

    def test_missing_cpu_dirs_are_skipped(self):
        for i in (20, 21):
            shutil.rmtree(Path(self.f.sysfs, f"devices/system/cpu/cpu{i}/cpufreq"))
        res = self.f.apply(power(balancedEpp="power"), "balanced")
        self.assertEqual({self.f.epp(i) for i in range(20)}, {"power"})
        self.assertTrue(any("2 CPUs" in s for s in res["skipped"]))
        self.assertEqual(res["errors"], [])

    def test_turbo_off_then_default_restores(self):
        res = self.f.apply(power(performanceTurbo="off"), "performance")
        self.assertEqual((self.f.turbo(), res["applied"]["turbo"]), ("1", "off"))
        self.assertTrue(self.f.state()["turbo_set"])
        res = self.f.apply(power(performanceTurbo="default"), "performance")
        self.assertEqual((self.f.turbo(), res["applied"]["turbo"]), ("0", "on"))

    def test_turbo_default_never_writes_without_our_state(self):
        self.f.turbo_file.write_text("1\n")                      # someone else turned turbo off
        res = self.f.apply(power(performanceTurbo="default"), "performance")
        self.assertEqual(self.f.turbo(), "1")
        self.assertIsNone(res["applied"]["turbo"])

    def test_cap_clamps_and_never_exceeds_original(self):
        res = self.f.apply(power(saverCap=18), "power-saver")
        self.assertEqual((self.f.cap(), res["applied"]["cap"]), (18000000, 18))
        self.assertEqual(self.f.state()["pl1_uw"], 28000000)
        self.f.apply(power(saverCap=28), "power-saver")
        self.assertEqual(self.f.cap(), 28000000)
        Path(self.f.run_dir, "orig.json").write_text(json.dumps({"pl1_uw": 20000000, "turbo_set": False}))
        self.f.apply(power(saverCap=28), "power-saver")
        self.assertEqual(self.f.cap(), 20000000)

    def test_cap_zero_restores_original_only_if_changed(self):
        res = self.f.apply(power(saverCap=0), "power-saver")
        self.assertIsNone(res["applied"]["cap"])
        self.f.apply(power(saverCap=18), "power-saver")
        res = self.f.apply(power(saverCap=0), "power-saver")
        self.assertEqual((self.f.cap(), res["applied"]["cap"]), (28000000, 0))

    def test_missing_mmio_file_is_skipped(self):
        shutil.rmtree(Path(self.f.sysfs, "class/powercap/intel-rapl-mmio:0"))
        res = self.f.apply(power(saverCap=18), "power-saver")
        self.assertIsNone(res["applied"]["cap"])
        self.assertTrue(any("power cap" in s for s in res["skipped"]))
        self.assertEqual(res["errors"], [])

    def test_charge_mode_is_written_for_every_profile(self):
        for mode, profile in (("Long_Life", "power-saver"), ("Standard", "balanced"), ("Fast", "performance")):
            self.f.charge_file.write_text("[Fast] Standard Long_Life\n" if mode != "Fast" else "Standard [Long_Life] Fast\n")
            res = self.f.apply(power(chargeMode=mode), profile)
            self.assertEqual((self.f.charge(), res["applied"]["charge"]), (mode, mode))
            self.assertEqual(res["errors"], [])

    def test_charge_mode_already_set_is_not_rewritten(self):
        self.f.charge_file.write_text("Standard [Fast] Long_Life\n")
        res = self.f.apply(power(chargeMode="Fast"), "balanced")
        self.assertEqual(self.f.charge(), "Standard [Fast] Long_Life")     # no write: the file still has its brackets
        self.assertEqual(res["applied"]["charge"], "Fast")

    def test_charge_mode_not_offered_is_skipped(self):
        self.f.charge_file.write_text("[Standard] Long_Life\n")
        res = self.f.apply(power(chargeMode="Fast"), "balanced")
        self.assertEqual(self.f.charge(), "[Standard] Long_Life")
        self.assertIsNone(res["applied"]["charge"])
        self.assertTrue(any("Fast" in s for s in res["skipped"]))
        self.assertEqual(res["errors"], [])

    def test_missing_charge_types_is_skipped(self):
        shutil.rmtree(Path(self.f.sysfs, "class/power_supply/BAT0"))
        res = self.f.apply(power(chargeMode="Long_Life"), "balanced")
        self.assertIsNone(res["applied"]["charge"])
        self.assertTrue(any("charge mode" in s for s in res["skipped"]))
        self.assertEqual(res["errors"], [])
        self.assertEqual(self.f.apply(power(), "balanced")["skipped"], [])  # default: nothing to report


class CrashSafetyTest(unittest.TestCase):
    """The firmware's original values must survive a helper that dies between a write and the end of the run."""

    def setUp(self):
        self.f = Fake(self)

    def kill_on_write_to(self, suffix):
        real = H._write

        def write(path, text):
            if str(path).endswith(suffix):
                raise SystemExit("killed mid-run")           # what a watchdog SIGTERM amounts to
            return real(path, text)
        return mock.patch.object(H, "_write", side_effect=write)

    def test_original_cap_is_saved_before_the_cap_write(self):
        with self.kill_on_write_to("constraint_0_power_limit_uw"), self.assertRaises(SystemExit):
            self.f.apply(power(saverCap=18), "power-saver")
        self.assertEqual(self.f.state()["pl1_uw"], 28000000)

    def test_turbo_state_is_saved_before_the_turbo_write(self):
        with self.kill_on_write_to("no_turbo"), self.assertRaises(SystemExit):
            self.f.apply(power(performanceTurbo="off"), "performance")
        self.assertTrue(self.f.state()["turbo_set"])

    def test_a_second_run_waits_for_the_lock_and_then_gives_up(self):
        import fcntl
        os.makedirs(self.f.run_dir, exist_ok=True)
        fd = os.open(os.path.join(self.f.run_dir, "lock"), os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX)
        with mock.patch.object(H, "LOCK_WAIT_S", 0.2):
            res = self.f.apply(power(saverCap=18), "power-saver")
        self.assertTrue(any("lock" in e for e in res["errors"]))
        self.assertEqual(self.f.cap(), 28000000)                # nothing was written

    def test_the_lock_is_released_after_a_run(self):
        import fcntl
        self.f.apply(power(saverCap=18), "power-saver")
        fd = os.open(os.path.join(self.f.run_dir, "lock"), os.O_RDWR)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)          # raises BlockingIOError if still held


class SettingsFileTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.uid = os.getuid()

    def write(self, text, name="settings.json"):
        p = Path(self.d, name)
        p.write_text(text)
        return str(p)

    def test_invalid_files_are_refused(self):
        real = self.write("{}")
        big = self.write(" " * 70000, "big.json")
        bad = self.write("{not json", "bad.json")
        for path, uid in ((self.d, self.uid), (big, self.uid), (real, self.uid + 1), (bad, self.uid),
                          (str(Path(self.d, "missing.json")), self.uid)):
            with self.assertRaises(H.SettingsError, msg=path):
                H.read_power_settings(path, uid)

    def test_symlink_to_the_users_own_file_is_followed(self):
        # ~/.config/bbkos/settings.json is a stow symlink into the repo: refusing symlinks would refuse the real file
        real = self.write('{"power": {"balancedEpp": "power"}}', "real.json")
        link = Path(self.d, "link.json")
        link.symlink_to(real)
        self.assertEqual(H.read_power_settings(str(link), self.uid)["balancedEpp"], "power")

    def test_symlink_to_a_file_of_another_owner_is_refused(self):
        link = Path(self.d, "passwd.json")
        link.symlink_to("/etc/passwd")                       # owned by root, not by the invoking user
        with self.assertRaises(H.SettingsError):
            H.read_power_settings(str(link), self.uid)

    def test_file_is_read_with_the_users_rights_when_root(self):
        calls = []
        real = self.write("{}")
        with mock.patch.object(H.os, "geteuid", return_value=0), \
             mock.patch.object(H.os, "seteuid", side_effect=lambda u: calls.append(u)):
            H.read_power_settings(real, self.uid)
        self.assertEqual(calls, [self.uid, 0])               # drops to the user, then back to root

    def test_missing_or_garbage_values_become_defaults(self):
        defaults = dict(S.DEFAULTS["power"])
        self.assertEqual(H.read_power_settings(self.write("{}"), self.uid), defaults)
        self.assertEqual(H.read_power_settings(self.write('{"power": {"balancedEpp": 7}}'), self.uid), defaults)
        self.assertEqual(H.read_power_settings(self.write('{"power": "x"}'), self.uid), defaults)

    def test_valid_values_are_kept_and_caps_clamped(self):
        got = H.read_power_settings(self.write(json.dumps({"power": {
            "balancedEpp": "power", "saverCap": 5, "performanceCap": 99, "balancedCap": "x", "saverTurbo": "off",
            "chargeMode": "Long_Life"}})), self.uid)
        self.assertEqual((got["balancedEpp"], got["saverCap"], got["performanceCap"], got["balancedCap"], got["saverTurbo"],
                          got["chargeMode"]), ("power", 10, 28, 0, "off", "Long_Life"))
        for bad in ("long_life", "Fast\n", 1, None, "[Fast]"):
            got = H.read_power_settings(self.write(json.dumps({"power": {"chargeMode": bad}})), self.uid)
            self.assertEqual(got["chargeMode"], "default")


class MainTest(unittest.TestCase):
    def setUp(self):
        self.f = Fake(self)
        self.settings = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.settings, True)
        self.path = str(Path(self.settings, "settings.json"))

    def env(self, profile="balanced", **extra):
        e = {"BBKOS_POWER_SYSFS": self.f.sysfs, "BBKOS_POWER_RUN": self.f.run_dir,
             "BBKOS_POWER_SETTINGS": self.path, "BBKOS_POWER_PROFILE": profile}
        e.update(extra)
        return e

    def run_main(self, argv, env):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch.object(H.os, "geteuid", return_value=1000):
            code = H.main(argv, env)
        lines = out.getvalue().strip().splitlines()
        return code, (json.loads(lines[-1]) if lines else None)

    def test_main_applies_for_the_active_profile(self):
        Path(self.path).write_text(json.dumps({"power": {"balancedEpp": "power"}}))
        code, res = self.run_main([], self.env("balanced"))
        self.assertEqual(code, 0)
        self.assertEqual(res["applied"]["epp"], "power")
        self.assertEqual(self.f.all_epp(), {"power"})

    def test_main_rejects_arguments_and_unknown_profile(self):
        Path(self.path).write_text(json.dumps({"power": {"balancedEpp": "power"}}))
        self.assertEqual(self.run_main(["x"], self.env())[0], 2)
        code, res = self.run_main([], self.env("balanced-battery"))
        self.assertEqual(code, 2)
        self.assertTrue(res["errors"])
        self.assertEqual(self.f.all_epp(), {"balance_power"})

    def test_main_refuses_a_bad_settings_file(self):
        Path(self.path).write_text("{broken")
        code, res = self.run_main([], self.env())
        self.assertEqual(code, 2)
        self.assertTrue(res["errors"])
        self.assertEqual(self.f.all_epp(), {"balance_power"})

    def test_main_needs_sudo_user_without_overrides(self):
        with contextlib.redirect_stdout(io.StringIO()), mock.patch.object(H.os, "geteuid", return_value=0):
            self.assertEqual(H.main([], {}), 2)

    def test_overrides_are_ignored_as_root(self):
        env = self.env()
        with mock.patch.object(H.os, "geteuid", return_value=0):
            self.assertEqual(H.resolve_paths(env), ("/sys", "/run/bbkos-power", None, None))
        with mock.patch.object(H.os, "geteuid", return_value=1000):
            self.assertEqual(H.resolve_paths(env), (self.f.sysfs, self.f.run_dir, self.path, "balanced"))


if __name__ == "__main__":
    unittest.main()
