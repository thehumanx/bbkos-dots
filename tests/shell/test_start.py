"""The test shell starts clean, leaves the live shell alone, and cleans up after a crashed run (layer 2)."""
import json
import subprocess
import time
import unittest

from tests.shell import harness
from tests.shell.harness import TestShell, skip_unless_session


def live_pid():
    return subprocess.run(["systemctl", "--user", "show", "quickshell", "-p", "MainPID", "--value"],
                          capture_output=True, text=True).stdout.strip()


@skip_unless_session()
class StartTest(unittest.TestCase):
    def test_starts_clean(self):
        shell = TestShell().start()
        self.addCleanup(shell.stop)
        status = json.loads(shell.ipc("panel", "status"))
        self.assertEqual(status["open"], "")
        log = shell.log()
        self.assertEqual(harness.unexpected_warnings(log), [], log)
        self.assertEqual([l for l in log.splitlines() if "ERROR" in l], [], log)

    def test_live_shell_untouched(self):
        before = live_pid()
        shell = TestShell().start()
        shell.stop()
        self.assertNotIn(before, ("", "0"))
        self.assertEqual(live_pid(), before)

    def test_start_acts_on_nothing(self):
        """Every command the shell would have run on the machine by itself at start is a stand-in on the allowed list."""
        shell = TestShell().start()
        self.addCleanup(shell.stop)
        time.sleep(5)
        names = {c.split()[0] for c in shell.calls() if c.strip()}
        self.assertTrue(names <= harness.ALLOWED_AT_START, f"unexpected at start: {sorted(names - harness.ALLOWED_AT_START)}")

    def test_nothing_left_after_stop(self):
        """No process of the test shell outlives it (2026-10-29: every run left the camera watcher's inotifywait)."""
        shell = TestShell().start()
        home = str(shell.home)
        shell.stop()
        time.sleep(0.5)
        self.assertEqual(harness.processes_with_home(home), [])

    def test_leftover_is_cleaned(self):
        stray = harness.start_compositor_for_test_only()        # a nested Hyprland left behind by a "crashed" run
        # The owner may be using the desktop during a run, so the check is that the stray does not hold the focus,
        # not that the focus is where it was.
        self.assertNotEqual(harness._active_pid(), stray.pid, "the stray nested Hyprland holds the focus")
        try:
            shell = TestShell().start()
            self.addCleanup(shell.stop)
            time.sleep(0.5)
            self.assertIsNotNone(stray.poll(), "the leftover nested Hyprland is still running")
            self.assertEqual(len(harness.nested_pids()), 1)
        finally:
            if stray.poll() is None:
                stray.kill()


if __name__ == "__main__":
    unittest.main()
