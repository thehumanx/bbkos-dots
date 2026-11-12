"""calendar.zones (the world clocks of the date popup) and bbkos-zones (zone list and offsets)."""
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dotfiles/bin/.local/lib"))
from bbkos_theme import settings as S, zones as Z  # noqa: E402


class ZonesSettingTest(unittest.TestCase):
    def test_default_is_empty_and_not_shared(self):
        self.assertEqual(S.DEFAULTS["calendar"]["zones"], [])
        s, _ = S.validate({"version": 1})
        s["calendar"]["zones"].append("Asia/Tokyo")
        self.assertEqual(S.DEFAULTS["calendar"]["zones"], [])

    def test_zones_are_cleaned(self):
        s, warns = S.validate({"version": 1, "calendar": {"zones": ["Asia/Tokyo", "Asia/Tokyo", "Mars/Base", "", 5, "Europe/London"]}})
        self.assertEqual(s["calendar"]["zones"], ["Asia/Tokyo", "Europe/London"])
        self.assertEqual(len(warns), 1)
        s, warns = S.validate({"version": 1, "calendar": {"zones": "Asia/Tokyo"}})
        self.assertEqual((s["calendar"]["zones"], len(warns)), ([], 1))

    def test_at_most_eight(self):
        names = ["Asia/Tokyo", "Asia/Seoul", "Asia/Kolkata", "Asia/Dubai", "Europe/London", "Europe/Paris", "America/New_York", "America/Chicago", "America/Denver"]
        s, warns = S.validate({"version": 1, "calendar": {"zones": names}})
        self.assertEqual(s["calendar"]["zones"], names[:8])
        self.assertEqual(len(warns), 1)

    def test_cli_text(self):
        out = S.set_value(S.validate({"version": 1})[0], "calendar.zones", "Asia/Tokyo,America/New_York")
        self.assertEqual(out["calendar"]["zones"], ["Asia/Tokyo", "America/New_York"])
        out = S.set_value(out, "calendar.zones", "")
        self.assertEqual(out["calendar"]["zones"], [])
        with self.assertRaises(ValueError):
            S.set_value(out, "calendar.zones", "Mars/Base")


class ZonesToolTest(unittest.TestCase):
    NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)

    def test_offsets_follow_daylight_saving(self):
        rows = {r["zone"]: r for r in Z.now(["Asia/Tokyo", "Asia/Kolkata", "America/New_York", "Asia/Kathmandu"], self.NOW)}
        self.assertEqual(rows["Asia/Tokyo"]["offset"], 540)
        self.assertEqual(rows["Asia/Kolkata"]["offset"], 330)
        self.assertEqual(rows["Asia/Kathmandu"]["offset"], 345)
        self.assertEqual(rows["America/New_York"]["offset"], -300)          # EST on 2 Nov 2026
        summer = {r["zone"]: r for r in Z.now(["America/New_York"], datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc))}
        self.assertEqual(summer["America/New_York"]["offset"], -240)
        self.assertEqual(rows["America/New_York"]["city"], "New York")

    def test_the_list_has_real_places_only(self):
        names = Z.all_names()
        self.assertIn("Asia/Kathmandu", names)
        self.assertIn("UTC", names)
        self.assertFalse([n for n in names if n.startswith(("Etc/", "posix/", "right/", "US/"))])
        self.assertEqual(names, sorted(set(names)))

    def test_the_picker_hides_legacy_aliases_but_saved_ones_still_work(self):
        names = Z.all_names()
        for alias in ("Australia/ACT", "Australia/NSW", "America/Argentina/ComodRivadavia"):
            self.assertNotIn(alias, names)
        for real in ("Australia/Sydney", "Europe/Amsterdam", "Asia/Kolkata", "America/Argentina/Buenos_Aires"):
            self.assertIn(real, names)
        s, warns = S.validate({"version": 1, "calendar": {"zones": ["Australia/ACT"]}})     # saved before: kept, not dropped
        self.assertEqual((s["calendar"]["zones"], warns), (["Australia/ACT"], []))
        self.assertEqual(Z.now(["Australia/ACT"], self.NOW)[0]["offset"], 660)

    def test_main_prints_json_and_refuses_bad_names(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(Z.main(["now", "Asia/Tokyo"]), 0)
        self.assertEqual(json.loads(buf.getvalue())[0]["zone"], "Asia/Tokyo")
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(Z.main(["list"]), 0)
        self.assertIn({"zone": "Asia/Tokyo", "city": "Tokyo", "region": "Asia"}, json.loads(buf.getvalue()))
        self.assertEqual(Z.main(["now", "../etc/passwd"]), 1)
        self.assertEqual(Z.main(["bogus"]), 2)


if __name__ == "__main__":
    unittest.main()
