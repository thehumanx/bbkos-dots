"""components/CalendarMath.js under node: the grid, week numbers, year progress, moon."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

JS = Path(__file__).resolve().parents[2] / "dotfiles/quickshell/.config/quickshell/components/CalendarMath.js"


def run(expr):
    """Evaluate a JS expression with the library's functions in scope; returns the JSON result."""
    src = JS.read_text().replace(".pragma library", "")
    prog = src + f"\nprocess.stdout.write(JSON.stringify({expr}))"
    out = subprocess.run(["node", "-e", prog], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@unittest.skipUnless(shutil.which("node"), "node not installed")
class CalendarMathTest(unittest.TestCase):
    def test_grid_shape(self):
        for ws in (0, 1, 6):
            cells = run(f"grid(2026,9,{ws})")
            self.assertEqual(len(cells), 42)
            first = [c for c in cells if c["inMonth"]][0]
            self.assertEqual(first["d"], 1)
            self.assertEqual(sum(c["inMonth"] for c in cells), 31)
        # October 2026 starts on a Thursday: Monday-first leaves three leading days
        self.assertEqual(run("grid(2026,9,1).findIndex(c => c.inMonth)"), 3)
        self.assertEqual(run("grid(2026,9,0).findIndex(c => c.inMonth)"), 4)

    def test_leap_february(self):
        self.assertEqual(run("daysInMonth(2028,1)"), 29)
        self.assertEqual(run("daysInMonth(2026,1)"), 28)

    def test_iso_week(self):
        self.assertEqual(run("isoWeek(2026,9,21)"), 43)
        self.assertEqual(run("isoWeek(2026,0,1)"), 1)
        self.assertEqual(run("isoWeek(2021,0,3)"), 53)      # Sunday 3 Jan 2021 still belongs to 2020's week 53

    def test_year_progress(self):
        p = run("yearProgress(new Date(2026, 9, 21, 12, 0, 0))")
        self.assertEqual((p["day"], p["total"], p["left"]), (294, 365, 71))
        self.assertAlmostEqual(p["fraction"], 293.5 / 365, places=6)
        self.assertEqual(run("yearProgress(new Date(2028, 11, 31, 23, 59, 59))")["left"], 0)
        self.assertEqual(run("yearProgress(new Date(2028, 0, 1, 0, 0, 0))")["fraction"], 0)

    def test_moon(self):
        full = run("moon(2026,9,26)")                       # full moon 26 Oct 2026
        self.assertEqual(full["name"], "Full moon")
        self.assertGreater(full["lit"], 0.95)
        self.assertEqual(run("moon(2026,9,10)")["name"], "New moon")   # new moon 10 Oct 2026



if __name__ == "__main__":
    unittest.main()
