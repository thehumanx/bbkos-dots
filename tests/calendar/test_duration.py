"""components/Duration.js under node: what a typed timer duration means, and how a time is shown."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

JS = Path(__file__).resolve().parents[2] / "dotfiles/quickshell/.config/quickshell/components/Duration.js"


def run(expr):
    src = JS.read_text().replace(".pragma library", "")
    out = subprocess.run(["node", "-e", src + f"\nprocess.stdout.write(JSON.stringify({expr}))"],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@unittest.skipUnless(shutil.which("node"), "node not installed")
class DurationTest(unittest.TestCase):
    def test_parse(self):
        cases = {"5": 300000, " 10 ": 600000, "5:30": 330000, "0:45": 45000, "1:05:00": 3900000, "90s": 90000,
                 "5m": 300000, "5min": 300000, "1h": 3600000, "1h30m": 5400000, "1h 30m 10s": 5410000,
                 "2M": 120000, "99:00:00": 356400000}
        for text, ms in cases.items():
            self.assertEqual(run(f"parse({json.dumps(text)})"), ms, text)

    def test_parse_rejects(self):
        for text in ("", "   ", "0", "0:00", "abc", "5x", "-5", "1:75", "5:", ":30", "1.5", "100h", "m5", "99:00:01", "1h h", "1 2"):
            self.assertIsNone(run(f"parse({json.dumps(text)})"), text)

    def test_format(self):
        cases = {0: "00:00", 1: "00:01", 999: "00:01", 1000: "00:01", 1001: "00:02", 59000: "00:59", 60000: "01:00",
                 3599000: "59:59", 3600000: "1:00:00", 3661000: "1:01:01", -5: "00:00"}
        for ms, text in cases.items():
            self.assertEqual(run(f"format({ms})"), text, ms)

    def test_approx(self):
        cases = {0: "0 min", 29: "0 min", 30: "1 min", 2100: "35 min", 3569: "59 min", 3570: "1 h 0 min",
                 3900: "1 h 5 min", 7260: "2 h 1 min"}
        for sec, text in cases.items():
            self.assertEqual(run(f"approx({sec})"), text, sec)


if __name__ == "__main__":
    unittest.main()
