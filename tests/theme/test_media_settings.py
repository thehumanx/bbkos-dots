"""The media.* keys (the bar's music widget), the clock's hoverDate key, and the media bar widget."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dotfiles" / "bin" / ".local" / "lib"))
from bbkos_theme import cli, settings as S  # noqa: E402


class MediaSettingsTest(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(S.DEFAULTS["media"], {"maxWidth": 220})
        self.assertIs(S.DEFAULTS["clock"]["hoverDate"], True)
        self.assertNotIn("island", S.DEFAULTS)

    def test_max_width_is_clamped_and_the_old_progress_key_is_dropped(self):
        s, w = S.validate({"version": 1, "media": {"maxWidth": 9999, "progress": True}})
        self.assertEqual(s["media"]["maxWidth"], 400)
        self.assertNotIn("progress", s["media"])
        self.assertTrue(w)

    def test_media_is_a_cli_section(self):
        self.assertIn("media", cli.SECTIONS)
        self.assertNotIn("island", cli.SECTIONS)

    def test_the_widget_sits_beside_the_clock(self):
        order = [e for e in S.BAR_LAYOUT_DEFAULT if e.startswith("center:")]
        self.assertEqual(order[order.index("center:clock") + 1], "center:media")


if __name__ == "__main__":
    unittest.main()
