"""components/DisplayText.js under node: the Display popup's monitor line and scale labels, with units."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

JS = Path(__file__).resolve().parents[2] / "dotfiles/quickshell/.config/quickshell/components/DisplayText.js"


def run(expr):
    src = JS.read_text().replace(".pragma library", "")
    out = subprocess.run(["node", "-e", src + f"\nprocess.stdout.write(JSON.stringify({expr}))"],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@unittest.skipUnless(shutil.which("node"), "node not installed")
class DisplayTextTest(unittest.TestCase):
    def test_scale_label(self):
        self.assertEqual(run("scaleLabel(1.0666667)"), "1.07×")
        self.assertEqual(run("scaleLabel(1)"), "1×")
        self.assertEqual(run("scaleLabel(1.25)"), "1.25×")
        self.assertEqual(run("scaleLabel(1.1)"), "1.1×")

    def test_mode_line(self):
        self.assertEqual(run('modeLine("1920x1200@60", 1.0666667)'), "1920 × 1200 · 60 Hz · 1.07×")
        self.assertEqual(run('modeLine("2560x1440@143.97", 1)'), "2560 × 1440 · 144 Hz · 1×")
        self.assertEqual(run('modeLine("", 1.5)'), "1.5×")          # no mode known: the scale alone
        self.assertEqual(run('modeLine("weird", 1)'), "weird · 1×")  # an unparsed mode is shown as it is

    def test_missing_scale_is_left_out(self):
        self.assertEqual(run("scaleLabel(undefined)"), "")
        self.assertEqual(run("scaleLabel(NaN)"), "")
        self.assertEqual(run('modeLine("1920x1200@60", undefined)'), "1920 × 1200 · 60 Hz")
        self.assertEqual(run('modeLine("", null)'), "")


if __name__ == "__main__":
    unittest.main()
