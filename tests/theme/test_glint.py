"""The About window's glint: frames that repaint only the logo cells and leave them as they were. A tiny virtual screen
applies the escape sequences, so the tests check what a terminal would show."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))
from bbkos_theme import glint  # noqa: E402

LOGO = "████  ██\n█  █  █ \n████  ██\n"
BASE = "\x1b[0m"
TOKEN = re.compile(r"\x1b\[(\d+);(\d+)H|(\x1b\[[0-9;]*m)|([^\x1b]+)")


def screen_after(frames, start=None):
    """cell (row, col) -> the SGR in effect when its character was written, and the characters themselves."""
    cells, chars = dict(start or {}), {}
    row = col = 0
    sgr = ""
    for frame in frames:
        for m in TOKEN.finditer(frame):
            if m.group(1):
                row, col = int(m.group(1)), int(m.group(2))
            elif m.group(3):
                sgr = m.group(3)
            else:
                for ch in m.group(4):
                    cells[(row, col)] = sgr
                    chars[(row, col)] = ch
                    col += 1
    return cells, chars


class GlintTest(unittest.TestCase):
    def frames(self, **kw):
        args = dict(logo=LOGO, row=3, col=5, base_sgr=BASE, width=40)
        args.update(kw)
        return glint.frames(**args)

    def test_double_width_logo_is_not_animated(self):
        self.assertEqual(self.frames(logo="漢字\n"), [])

    def test_no_color_is_not_animated(self):
        self.assertEqual(self.frames(no_color=True), [])

    def test_blank_logo_is_not_animated(self):
        self.assertEqual(self.frames(logo="  \n"), [])

    def test_some_cell_is_lit_during_the_sweep(self):
        cells, _ = screen_after(self.frames())
        lit = {glint.GLINT_SGR}
        seen = set()
        for frame in self.frames():
            seen |= {c for c in screen_after([frame])[0].values()}
        self.assertTrue(lit & seen)

    def test_last_frame_leaves_every_cell_in_the_base_colour(self):
        cells, chars = screen_after(self.frames())
        self.assertTrue(cells)
        self.assertEqual({v for v in cells.values()}, {BASE})

    def test_frames_only_touch_logo_cells(self):
        _, chars = screen_after(self.frames())
        lines = LOGO.splitlines()
        for (row, col), ch in chars.items():
            r, c = row - 3, col - 5
            self.assertTrue(0 <= r < len(lines) and 0 <= c < len(lines[r]), (row, col))
            self.assertEqual(ch, lines[r][c])

    def test_text_beyond_the_width_is_not_touched(self):
        _, chars = screen_after(self.frames(width=3))
        self.assertTrue(all(col - 5 < 3 for (_, col) in chars))


class LocateTest(unittest.TestCase):
    def test_finds_the_logo_in_the_rendered_text(self):
        plain = "\n\n  ████  ██     Hardware\n  █  █  █      CPU\n  ████  ██\n"
        self.assertEqual(glint.locate(plain, LOGO), (3, 3))

    def test_missing_logo_is_none(self):
        self.assertIsNone(glint.locate("nothing here\n", LOGO))


if __name__ == "__main__":
    unittest.main()
