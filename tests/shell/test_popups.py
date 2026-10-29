"""Every bar popup opens and closes in the test shell; the Wi-Fi scanner runs only while its popup is open; the owner's
settings and state are not touched by any of it (layer 2)."""
import hashlib
import json
import time
import unittest
from pathlib import Path

from tests.shell import harness
from tests.shell.harness import TestShell, skip_unless_session

POPUPS = ["wifi", "bluetooth", "audio", "display", "battery", "calendar", "timer", "power", "record"]
# The owner's bbkOS settings and state. ~/.local/state/quickshell is left out on purpose: the live shell itself writes
# screentime.json there every 30 s, so its digest would change during any run.
OWNER = [Path.home() / ".config/bbkos", Path.home() / ".local/state/bbkos"]


def owner_digest() -> dict:
    """sha256 of every file under the owner's bbkOS settings and state."""
    out = {}
    for root in OWNER:
        for p in sorted(root.rglob("*")) if root.exists() else []:
            if p.is_file():
                out[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def wait_for(fn, timeout=2.0):
    end = time.monotonic() + timeout
    while True:
        value = fn()
        if value or time.monotonic() >= end:
            return value
        time.sleep(0.1)


@skip_unless_session()
class PopupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = owner_digest()
        cls.shell = TestShell().start()

    @classmethod
    def tearDownClass(cls):
        cls.shell.stop()
        after = owner_digest()
        changed = sorted(k for k in set(cls.before) | set(after) if cls.before.get(k) != after.get(k))
        if changed:
            raise AssertionError(f"the owner's files changed during the popup tests: {changed}")

    def status(self) -> dict:
        return json.loads(self.shell.ipc("panel", "status"))

    def test_each_opens_and_closes(self):
        for name in POPUPS:
            with self.subTest(popup=name):
                self.shell.ipc("panel", "toggle", name)
                self.assertTrue(wait_for(lambda: self.status()["open"] == name), f"{name} did not open: {self.status()}")
                self.shell.ipc("panel", "close")
                self.assertTrue(wait_for(lambda: self.status()["open"] == ""), f"{name} did not close: {self.status()}")

    def test_wifi_scans_only_while_open(self):
        self.shell.ipc("panel", "toggle", "wifi")
        self.assertTrue(wait_for(lambda: self.status()["wifiScanning"] is True), self.status())
        self.shell.ipc("panel", "close")
        self.assertTrue(wait_for(lambda: self.status()["wifiScanning"] is False), self.status())

    def test_zz_no_new_errors(self):                       # runs last in the class (alphabetical order)
        log = self.shell.log()
        self.assertEqual(harness.unexpected_warnings(log), [], log)
        self.assertEqual([l for l in log.splitlines() if "ERROR" in l], [], log)


if __name__ == "__main__":
    unittest.main()
