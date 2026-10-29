import colorsys
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dotfiles/bin/.local/lib"))

from bbkos_theme import contrast as C  # noqa: E402


def hls(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hls(r, g, b)


class ContrastTest(unittest.TestCase):
    def test_ratio_black_white_is_21(self):
        self.assertAlmostEqual(C.ratio("#000000", "#ffffff"), 21.0, places=6)
        self.assertAlmostEqual(C.ratio("#ffffff", "#000000"), 21.0, places=6)
        self.assertAlmostEqual(C.ratio("#777777", "#777777"), 1.0, places=6)

    def test_ensure_contrast_unchanged_when_ok(self):
        self.assertEqual(C.ensure_contrast("#FFFFFF", "#000000", 4.5), "#ffffff")

    def test_ensure_contrast_meets_floor_and_keeps_hue(self):
        fg, bg = "#3a5fa0", "#11140f"
        out = C.ensure_contrast(fg, bg, 4.5)
        self.assertGreaterEqual(C.ratio(out, bg), 4.5)
        self.assertNotEqual(out, fg)
        self.assertLess(abs(hls(out)[0] - hls(fg)[0]), 0.02)
        self.assertGreater(hls(out)[1], hls(fg)[1])

    def test_ensure_contrast_darkens_on_light_bg(self):
        out = C.ensure_contrast("#a0c0ff", "#fafafa", 4.5)
        self.assertGreaterEqual(C.ratio(out, "#fafafa"), 4.5)
        self.assertLess(hls(out)[1], hls("#a0c0ff")[1])

    def test_ensure_contrast_unreachable_stops_at_extreme(self):
        out = C.ensure_contrast("#808080", "#808080", 30.0)
        self.assertIn(out, ("#ffffff", "#000000"))
        self.assertRegex(out, r"^#[0-9a-f]{6}$")

    def test_oklch_roundtrip(self):
        for h in ("#11140f", "#a5d395", "#ffb595", "#808080", "#ffffff", "#000000"):
            self.assertEqual(C.from_oklch(*C.to_oklch(h)), h)

    def test_oklch_out_of_gamut_loses_chroma_keeps_hue(self):
        L, c, hue = C.to_oklch("#1f5fff")
        out = C.from_oklch(0.95, c * 1.5, hue)  # far outside sRGB
        L2, c2, h2 = C.to_oklch(out)
        self.assertLess(c2, c * 1.5)
        self.assertLess(min(abs(h2 - hue), 360 - abs(h2 - hue)), 6)

    def test_ensure_contrast_keeps_oklch_hue_and_chroma(self):
        fg, bg = "#6a7fb0", "#11140f"
        out = C.ensure_contrast(fg, bg, 7.0)
        a, b = C.to_oklch(fg), C.to_oklch(out)
        self.assertLess(abs(a[2] - b[2]), 3)
        self.assertLessEqual(b[1], a[1] + 0.01)


if __name__ == "__main__":
    unittest.main()
