"""bbkos-lock-test: lock, capture, unlock. Fake bbkos-lock, grim and loginctl in PATH; the lock process is a script
named `fakelock` (BBKOS_LOCK_PROC), so nothing real is locked."""
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "dotfiles/bin/.local/bin/bbkos-lock-test"


class LockTestTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = Path(tmp.name)
        self.dir = d
        self.run_dir = d / "run"
        self.run_dir.mkdir()
        self.calls = d / "calls.log"
        bin_ = d / "bin"
        bin_.mkdir()

        def tool(name, body):
            p = bin_ / name
            p.write_text("#!/bin/sh\n" + body)
            p.chmod(0o755)

        # the "lock": a process whose name is fakelock; USR1 ends it unless FAKE_IGNORE_USR1 is set
        tool("fakelock", 'if [ -z "$FAKE_IGNORE_USR1" ]; then trap "exit 0" USR1; else trap "" USR1; fi\n'
                         'while :; do sleep 0.1; done\n')
        tool("bbkos-lock", f'echo "lock" >> {self.calls}\n[ -n "$FAKE_NO_LOCK" ] && exit 0\nexec fakelock\n')
        tool("grim", f'echo "grim $*" >> {self.calls}\n: > "$1"\n')
        tool("loginctl", f'echo "loginctl $*" >> {self.calls}\n'
                         '[ -n "$FAKE_IGNORE_UNLOCK" ] || pkill -x fakelock\nexit 0\n')
        # faillock lists the account's recent failed logins: FAKE_FAILS valid ("V") rows, FAKE_STALE expired ("I") rows
        tool("faillock", 'echo "bbk:"\necho "When                Type  Source                                           Valid"\n'
                         'i=0; while [ "$i" -lt "${FAKE_FAILS:-0}" ]; do\n'
                         '  echo "2026-10-19 19:1$i:48 SVC   hyprlock                                             V"; i=$((i+1)); done\n'
                         'i=0; while [ "$i" -lt "${FAKE_STALE:-0}" ]; do\n'
                         '  echo "2026-10-19 18:1$i:48 SVC   hyprlock                                             I"; i=$((i+1)); done\n')
        self.env = {"PATH": f"{bin_}:/usr/bin:/bin", "XDG_RUNTIME_DIR": str(self.run_dir),
                    "BBKOS_LOCK_PROC": "fakelock", "BBKOS_LOCK_TEST_WAIT": "1", "HOME": str(d)}
        self.addCleanup(lambda: subprocess.run(["pkill", "-x", "fakelock"]))

    def run_script(self, *args, **extra):
        return subprocess.run([str(SCRIPT), *args], env={**self.env, **extra}, capture_output=True, text=True,
                              timeout=30)

    def calls_list(self):
        return self.calls.read_text().splitlines() if self.calls.exists() else []

    def alive(self):
        return subprocess.run(["pgrep", "-x", "fakelock"], capture_output=True).returncode == 0

    def test_lock_capture_unlock_in_order(self):
        r = self.run_script("1")
        self.assertEqual(r.returncode, 0, r.stderr)
        png = self.run_dir / "bbkos-lock-test.png"
        self.assertEqual(self.calls_list(), ["lock", f"grim {png}", "loginctl unlock-session"])
        self.assertEqual(r.stdout.strip(), str(png))
        self.assertTrue(png.exists())
        self.assertFalse(self.alive())

    def test_delay_must_be_a_whole_number_of_seconds_1_to_30(self):
        for bad in ("0", "abc", "31", "-1", "1.5", ""):
            r = self.run_script(bad)
            self.assertEqual(r.returncode, 2, bad)
        self.assertEqual(self.calls_list(), [])

    def test_no_lock_means_no_unlock_and_no_capture(self):
        r = self.run_script("1", FAKE_NO_LOCK="1")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("loginctl unlock-session", self.calls_list())
        self.assertFalse(any(c.startswith("grim") for c in self.calls_list()))

    def test_already_locked_is_left_alone(self):
        # a lock someone else started (hypridle, the lid): never photographed, never unlocked
        other = subprocess.Popen([str(self.dir / "bin" / "fakelock")], env=self.env)
        self.addCleanup(other.kill)
        time.sleep(0.3)
        r = self.run_script("1")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.calls_list(), [])
        self.assertTrue(self.alive())
        self.assertIn("already", r.stderr.lower())

    def test_refuses_when_failed_logins_are_on_record(self):
        # each test ends the lock from outside and PAM counts that as a failed login: 3 in 10 minutes lock the account
        for n in ("1", "2"):
            r = self.run_script("1", FAKE_FAILS=n)
            self.assertEqual(r.returncode, 3, n)
            self.assertIn("failed login", r.stderr.lower())
        self.assertEqual(self.calls_list(), [])

    def test_expired_failed_logins_do_not_block(self):
        r = self.run_script("1", FAKE_STALE="2")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_runs_without_faillock(self):
        # a PATH with the fakes and symlinks to only the tools the script needs, so this machine's real faillock
        # (and whatever failed logins it lists) cannot leak in
        (self.dir / "bin" / "faillock").unlink()
        tools = self.dir / "tools"
        tools.mkdir()
        for name in ("bash", "env", "sh", "awk", "wc", "pgrep", "pkill", "sleep", "id", "date"):
            (tools / name).symlink_to(shutil.which(name))
        r = self.run_script("1", PATH=f"{self.dir / 'bin'}:{tools}")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_unlock_ignored_falls_back_to_sigusr1(self):
        r = self.run_script("1", FAKE_IGNORE_UNLOCK="1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.alive())

    def test_still_locked_reports_failure(self):
        r = self.run_script("1", FAKE_IGNORE_UNLOCK="1", FAKE_IGNORE_USR1="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("still", r.stderr.lower())


if __name__ == "__main__":
    unittest.main()
