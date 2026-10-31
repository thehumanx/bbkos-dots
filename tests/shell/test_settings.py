"""The settings window in the test shell: every page and tab of Pages.js opens, and the search lands on its row (layer 2)."""
import json
import subprocess
import time
import unittest

from tests.shell import harness
from tests.shell.harness import SHELL_DIR, TestShell, skip_unless_session

PAGES_JS = SHELL_DIR / "modules/settings/Pages.js"


def places() -> list:
    """Every "page/tab" place, read from Pages.js under node."""
    src = PAGES_JS.read_text().replace(".pragma library", "")
    prog = src + "\nprocess.stdout.write(JSON.stringify(PAGES.flatMap(p => p.tabs.map(t => p.id + '/' + t.id))))"
    out = subprocess.run(["node", "-e", prog], capture_output=True, text=True, check=True, timeout=30).stdout
    return json.loads(out)


def wait_for(fn, timeout=3.0):
    end = time.monotonic() + timeout
    while True:
        value = fn()
        if value or time.monotonic() >= end:
            return value
        time.sleep(0.1)


@skip_unless_session()
class SettingsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shell = TestShell().start()
        try:
            cls.shell.ipc("settings", "toggle")
            if not wait_for(lambda: json.loads(cls.shell.ipc("settings", "status"))["open"]):
                raise RuntimeError("the settings window did not open")
        except BaseException:
            cls.shell.stop()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.shell.stop()

    def where(self) -> str:
        return self.shell.ipc("settings", "where")

    def test_places_are_read(self):
        p = places()
        self.assertIn("bar/layout", p)
        self.assertIn("power/profiles", p)
        self.assertGreaterEqual(len(p), 16)

    def test_every_page_opens(self):
        for place in places():
            with self.subTest(place=place):
                self.shell.ipc("settings", "page", place)
                self.assertTrue(wait_for(lambda: self.where() == place), f"{place}: at {self.where()}")

    def test_search_lands_on_the_row(self):
        self.shell.ipc("settings", "page", "about/about")
        self.shell.ipc("settings", "search", "Hug the widgets")     # "Thickness" is also on bbkOS › Rail (2026-10-31)
        time.sleep(0.5)
        self.shell.ipc("settings", "pick")
        self.assertTrue(wait_for(lambda: self.where() == "bar/layout"), self.where())
        self.shell.ipc("settings", "search", "")

    def test_zz_no_new_errors(self):
        log = self.shell.log()
        self.assertEqual(harness.unexpected_warnings(log), [], log)
        self.assertEqual([l for l in log.splitlines() if "ERROR" in l], [], log)


if __name__ == "__main__":
    unittest.main()
