"""components/ScreenBreak.js (the break reminder's stretch counting), run under node, and the wellbeing.* key."""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / "dotfiles/quickshell/.config/quickshell/components/ScreenBreak.js"
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))
from bbkos_theme import cli, settings as S  # noqa: E402


def js(expr):
    src = JS.read_text().replace(".pragma library", "", 1)
    out = subprocess.run(["node", "-e", src + "\nconsole.log(JSON.stringify(" + expr + "))"], capture_output=True, text=True, timeout=10)
    if out.returncode != 0:
        raise AssertionError(out.stderr)
    return json.loads(out.stdout)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class StepTest(unittest.TestCase):
    def test_a_stretch_grows_while_the_screen_is_on(self):
        self.assertEqual(js("step({streak: 100, off: 0}, true, 30000, 30000, 30)"), {"streak": 130, "off": 0, "remind": False})

    def test_it_reminds_at_the_limit_and_starts_again(self):
        self.assertEqual(js("step({streak: 1790, off: 0}, true, 30000, 30000, 30)"), {"streak": 0, "off": 0, "remind": True})

    def test_reminders_off_never_remind(self):
        self.assertFalse(js("step({streak: 99999, off: 0}, true, 30000, 30000, 0)")["remind"])

    def test_five_minutes_off_is_a_break_but_a_short_lock_is_not(self):
        s = {"streak": 600, "off": 0}
        for _ in range(9):                                                  # 270 s off
            s = js(f"step({json.dumps(s)}, false, 30000, 30000, 30)")
        self.assertEqual((s["streak"], round(s["off"])), (600, 270))
        s = js(f"step({json.dumps(s)}, false, 30000, 30000, 30)")           # 300 s
        self.assertEqual(s["streak"], 0)
        self.assertEqual(js("step({streak: 600, off: 200}, true, 30000, 30000, 30)")["off"], 0)     # back on: the off time is forgotten

    def test_a_long_gap_is_a_break(self):
        self.assertEqual(js("step({streak: 1500, off: 10}, true, 120000, 30000, 30)"), {"streak": 0, "off": 0, "remind": False})

    def test_the_first_sample_adds_nothing(self):
        self.assertEqual(js("step({streak: 0, off: 0}, true, 0, 30000, 30)")["streak"], 0)


class KeyTest(unittest.TestCase):
    def test_default_is_off_and_snaps_to_five(self):
        self.assertEqual(S.DEFAULTS["wellbeing"], {"breakEvery": 0})
        s, _ = S.validate({"version": 1, "wellbeing": {"breakEvery": 47}})
        self.assertEqual(s["wellbeing"]["breakEvery"], 45)
        s, _ = S.validate({"version": 1, "wellbeing": {"breakEvery": 999}})
        self.assertEqual(s["wellbeing"]["breakEvery"], 120)
        self.assertIn("wellbeing", cli.SECTIONS)


if __name__ == "__main__":
    unittest.main()
