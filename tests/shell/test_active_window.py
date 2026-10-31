"""The bar's window title (docs/modules/dock.md, "Window title") in a fresh test shell (layer 2). Regression (2026-10-31):
on a workspace with no windows the title still showed the last window (the owner saw "Figma" on an empty workspace 3).
Quickshell keeps Hyprland.activeToplevel when Hyprland sends `activewindowv2` with an empty address, so services/ActiveWindow
clears it on that event."""
import json
import subprocess
import time
import unittest

from tests.shell.harness import TestShell, skip_unless_session


@skip_unless_session()
class ActiveWindowTest(unittest.TestCase):
    def _wait(self, shell, want, timeout=15):
        state = {}
        end = time.time() + timeout
        while time.time() < end:
            state = json.loads(shell.ipc("activewindow", "status"))
            if want(state):
                return state
            time.sleep(0.3)
        self.fail(f"active window never matched: {state}")

    def test_an_empty_workspace_has_no_title(self):
        with TestShell() as shell:
            env = shell._env()
            term = subprocess.Popen(["foot"], env=env, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, start_new_session=True)
            try:
                self._wait(shell, lambda s: s["class"] == "foot")
                r = subprocess.run(["hyprctl", "dispatch", "hl.dsp.focus({ workspace = 7 })"], env=env,
                                   capture_output=True, text=True, timeout=5)
                self.assertEqual(r.stdout.strip(), "ok", r.stdout + r.stderr)
                self._wait(shell, lambda s: s["title"] == "" and s["class"] == "")
            finally:
                term.kill()
