"""clock.* settings: defaults keep the old bar clock, values are booleans, and the reset section exists."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dotfiles/bin/.local/lib"))
from bbkos_theme import cli, settings as S  # noqa: E402


class ClockSettingsTest(unittest.TestCase):
    def test_defaults_are_the_old_clock(self):
        self.assertEqual(S.DEFAULTS["clock"], {"hour24": True, "seconds": False, "date": True, "hoverDate": True})

    def test_only_booleans_are_accepted(self):
        s, warns = S.validate({"version": 1, "clock": {"hour24": "no", "seconds": 1, "date": False}})
        self.assertEqual(s["clock"], {"hour24": True, "seconds": False, "date": False, "hoverDate": True})
        self.assertEqual(len(warns), 2)

    def test_reset_section(self):
        self.assertIn("clock", cli.SECTIONS)


if __name__ == "__main__":
    unittest.main()
