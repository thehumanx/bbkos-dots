"""components/CalendarMath.js under node: the Bikram Sambat table, the grid, week numbers, year progress, moon."""
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
    def test_known_new_years(self):
        # 1 Baisakh: 14 April of 2025, 2026, 2007 (the table start)
        for y, bs in ((2025, 2082), (2026, 2083), (2007, 2064)):
            self.assertEqual(run(f"toBS({y},3,14)"), {"year": bs, "month": 0, "day": 1})
        self.assertEqual(run("toBS(2026,3,13)"), {"year": 2082, "month": 11, "day": 30})

    def test_today_reference(self):
        # 21 Oct 2026 is 4 Kartik 2083 (Kartik began on 18 Oct)
        self.assertEqual(run("toBS(2026,9,21)"), {"year": 2083, "month": 6, "day": 4})

    def test_outside_the_table_is_null(self):
        self.assertIsNone(run("toBS(2007,3,13)"))
        self.assertEqual(run("toBS(2028,3,12)")["year"], 2084)
        self.assertIsNone(run("toBS(2028,3,13)"))

    def test_every_day_chains_without_gap(self):
        # walking AD day by day, the BS date advances by one day or rolls to day 1 of the next month, never skips
        bad = run("""(() => { let prev = null, bad = 0;
            for (let n = dayNum(2007,3,14); n < dayNum(2028,3,13); n++) {
              const d = new Date(n*86400000), b = toBS(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
              if (!b) { bad++; continue }
              if (prev) { const ok = (b.year===prev.year && b.month===prev.month && b.day===prev.day+1) ||
                                     (b.day===1 && ((b.month===prev.month+1 && b.year===prev.year) || (b.month===0 && prev.month===11 && b.year===prev.year+1)));
                          if (!ok) bad++ }
              prev = b }
            return bad })()""")
        self.assertEqual(bad, 0)

    def test_month_lengths_are_29_to_32(self):
        self.assertTrue(run("BS_LENGTHS.every(y => y.length === 12 && y.every(l => l >= 29 && l <= 32))"))

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

    def test_bs_progress(self):
        # 29 Oct 2026 is Kartik (month 6) 12, 2083 BS; at midnight the day itself is not yet gone for the year,
        # as yearProgress; the month counts today, as monthProgress.
        row = run("BS_LENGTHS[2083 - BS_FIRST_YEAR]")
        day = sum(row[:6]) + 12
        self.assertEqual(run("bsMonthProgress(new Date(2026, 9, 29, 0, 0, 0))"), {"fraction": 12 / row[6], "left": row[6] - 12})
        self.assertEqual(run("bsYearProgress(new Date(2026, 9, 29, 0, 0, 0))"),
                         {"fraction": (day - 1) / sum(row), "left": sum(row) - day})
        noon = run("bsYearProgress(new Date(2026, 9, 29, 12, 0, 0)).fraction")
        self.assertAlmostEqual(noon, (day - 0.5) / sum(row))

    def test_bs_progress_outside_the_table_is_null(self):
        self.assertIsNone(run("bsYearProgress(new Date(2000, 0, 1, 12, 0, 0))"))
        self.assertIsNone(run("bsMonthProgress(new Date(2000, 0, 1, 12, 0, 0))"))

    def test_moon(self):
        full = run("moon(2026,9,26)")                       # full moon 26 Oct 2026
        self.assertEqual(full["name"], "Full moon")
        self.assertGreater(full["lit"], 0.95)
        self.assertEqual(run("moon(2026,9,10)")["name"], "New moon")   # new moon 10 Oct 2026

    def test_titles(self):
        self.assertEqual(run("bsTitle(2026,9,false)"), "Ashwin - Kartik 2083")
        self.assertEqual(run("bsTitle(2026,3,false)"), "Chaitra 2082 - Baisakh 2083")
        self.assertEqual(run("bsTitle(2026,4,false)"), "Baisakh - Jestha 2083")
        self.assertEqual(run("bsTitle(2040,0,false)"), "")
        self.assertEqual(run("nepaliDigits(2083)"), "२०८३")


if __name__ == "__main__":
    unittest.main()
