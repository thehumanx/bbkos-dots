"""The harness's own pure parts, without a compositor (runs everywhere): the `with` form of TestShell and the bar
check's desktop colour."""
import unittest
from unittest import mock

from tests.shell import harness
from tests.shell.harness import TestShell


class WithTest(unittest.TestCase):
    def test_with_starts_and_stops(self):
        with mock.patch.object(TestShell, "start", autospec=True, side_effect=lambda self, **kw: self) as start, \
                mock.patch.object(TestShell, "stop", autospec=True) as stop:
            with TestShell(settings={"shell": {"barPosition": "bottom"}}) as shell:
                self.assertIsInstance(shell, TestShell)
                start.assert_called_once_with(shell, settings={"shell": {"barPosition": "bottom"}}, remove=())
                stop.assert_not_called()
            stop.assert_called_once_with(shell)

    def test_with_stops_after_an_error(self):
        with mock.patch.object(TestShell, "start", autospec=True, side_effect=lambda self, **kw: self), \
                mock.patch.object(TestShell, "stop", autospec=True) as stop:
            with self.assertRaises(ValueError):
                with TestShell():
                    raise ValueError("a failing test")
            stop.assert_called_once()


def image(w, h, base, blocks=()):
    """An rgb buffer w x h filled with `base`, with (x0, y0, x1, y1, colour) blocks painted over it."""
    rgb = bytearray(base * (w * h))
    for x0, y0, x1, y1, c in blocks:
        for y in range(y0, y1):
            for x in range(x0, x1):
                i = (y * w + x) * 3
                rgb[i:i + 3] = c
    return bytes(rgb)


class DesktopColourTest(unittest.TestCase):
    DESK, OSD, TEXT = b"\x13\x13\x13", b"\x40\x40\x40", b"\xff\xff\xff"

    def test_a_block_at_the_centre_is_not_the_desktop(self):
        from tests.shell.test_setting_reaches_shell import desktop_colour
        w, h = 400, 300
        rgb = image(w, h, self.DESK, [(150, 120, 250, 180, self.OSD)])      # an OSD-like card over the centre
        self.assertEqual(desktop_colour(w, h, rgb), self.DESK)

    def test_bar_share_with_a_centre_block(self):
        from tests.shell.test_setting_reaches_shell import bar_share
        w, h = 400, 300
        rgb = image(w, h, self.DESK, [(150, 120, 250, 180, self.OSD), (0, 0, 40, 40, self.TEXT)])   # "text" in the top band
        self.assertGreater(bar_share(w, h, rgb, 0, 40), 0.01)
        self.assertEqual(bar_share(w, h, rgb, h - 40, h), 0)


if __name__ == "__main__":
    unittest.main()
