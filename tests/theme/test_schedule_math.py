"""components/ScheduleMath.js (the automatic light and dark schedule), run under node, and the colors.* schedule keys."""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / "dotfiles/quickshell/.config/quickshell/components/ScheduleMath.js"
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))
from bbkos_theme import settings as S  # noqa: E402


def js(expr):
    src = JS.read_text().replace(".pragma library", "", 1)
    out = subprocess.run(["node", "-e", src + "\nconsole.log(JSON.stringify(" + expr + "))"], capture_output=True, text=True, timeout=10)
    if out.returncode != 0:
        raise AssertionError(out.stderr)
    return json.loads(out.stdout)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class MathTest(unittest.TestCase):
    def test_parse_clock(self):
        self.assertEqual(js('[parseClock("07:30"), parseClock("7:30"), parseClock("23:59"), parseClock("24:00"), parseClock("7"), parseClock("")]'),
                         [450, 450, 1439, -1, -1, -1])

    def test_a_normal_day(self):
        got = js('[0, 419, 420, 720, 1139, 1140, 1439].map(m => isLight(m, "07:00", "19:00"))')
        self.assertEqual(got, [False, False, True, True, True, False, False])

    def test_a_schedule_that_wraps_past_midnight(self):
        got = js('[0, 359, 360, 1000, 1259, 1260, 1439].map(m => isLight(m, "21:00", "06:00"))')
        self.assertEqual(got, [True, True, False, False, False, True, True])

    def test_bad_and_equal_times(self):
        self.assertEqual(js('[isLight(720, "x", "y"), isLight(60, "x", "y"), isLight(5, "08:00", "08:00")]'), [True, False, True])


class KeysTest(unittest.TestCase):
    def test_defaults_keep_the_mode_by_hand(self):
        c = S.DEFAULTS["colors"]
        self.assertEqual((c["auto"], c["lightFrom"], c["darkFrom"]), (False, "07:00", "19:00"))

    def test_bad_times_are_refused(self):
        s, warns = S.validate({"version": 1, "colors": {"lightFrom": "25:00", "darkFrom": "6pm", "auto": True}})
        self.assertEqual((s["colors"]["lightFrom"], s["colors"]["darkFrom"], s["colors"]["auto"]), ("07:00", "19:00", True))
        self.assertEqual(len(warns), 2)


if __name__ == "__main__":
    unittest.main()
