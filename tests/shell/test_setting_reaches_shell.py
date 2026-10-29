"""A setting change reaches the test shell, a key missing from settings.json shows its built-in default (layer 2), and,
opt-in with BBKOS_SHELLTEST_VISIBLE=1, the nested output can be screenshotted: a hidden nested Hyprland does not draw, so
that test leaves its window on the owner's screen while it runs. Pixels are read from grim's PPM output."""
import os
import json
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from tests.shell.harness import TestShell, skip_unless_session

BAND = 40


def read_ppm(path: str):
    """(width, height, rgb bytes) of a binary PPM (P6, maxval 255)."""
    data = Path(path).read_bytes()
    fields, pos = [], 0
    while len(fields) < 4:
        while data[pos:pos + 1].isspace():
            pos += 1
        if data[pos:pos + 1] == b"#":
            pos = data.index(b"\n", pos) + 1
            continue
        end = pos
        while not data[end:end + 1].isspace():
            end += 1
        fields.append(data[pos:end])
        pos = end
    assert fields[0] == b"P6" and fields[3] == b"255", fields
    return int(fields[1]), int(fields[2]), data[pos + 1:]


def shot(shell: TestShell, tmp: str):
    path = str(Path(tmp) / f"shot-{time.monotonic_ns()}.ppm")
    subprocess.run(["grim", "-t", "ppm", path], env=shell._env(), capture_output=True, timeout=10, check=True)
    return read_ppm(path)


def pixel(w: int, rgb: bytes, x: int, y: int) -> bytes:
    i = (y * w + x) * 3
    return rgb[i:i + 3]


def desktop_colour(w: int, h: int, rgb: bytes) -> bytes:
    """The most common colour in the middle of the screen (the inner 60 %, every 8 px): the empty desktop of a fresh
    home, even when something (an OSD, a dialog) sits on the very centre."""
    from collections import Counter
    samples = Counter(pixel(w, rgb, x, y) for y in range(h // 5, h * 4 // 5, 8) for x in range(w // 5, w * 4 // 5, 8))
    return samples.most_common(1)[0][0]


def bar_share(w: int, h: int, rgb: bytes, y0: int, y1: int) -> float:
    """Share of sampled pixels in rows y0..y1 that differ from the desktop colour. A fresh home has no wallpaper and the
    bar's background is the desktop colour too, so only the bar's text and icons differ: measured about 0.03 for the
    bar's band, exactly 0 for an empty band."""
    desk = desktop_colour(w, h, rgb)
    samples = [pixel(w, rgb, x, y) for y in range(y0, y1, 4) for x in range(0, w, 8)]
    return sum(s != desk for s in samples) / len(samples)


def has_bar(top: float, bottom: float, at_top: bool) -> bool:
    """The bar's band has text and icons (over 1 % non-desktop), the other band is flat (under 0.3 %)."""
    bar, other = (top, bottom) if at_top else (bottom, top)
    return bar > 0.01 and other < 0.003


def bands(shell, tmp):
    w, h, rgb = shot(shell, tmp)
    return bar_share(w, h, rgb, 0, BAND), bar_share(w, h, rgb, h - BAND, h)


VISIBLE = os.environ.get("BBKOS_SHELLTEST_VISIBLE") == "1"


@skip_unless_session()
class ReachTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bbkos-shelltest-shots-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    @unittest.skipUnless(VISIBLE, "needs a visible test window: BBKOS_SHELLTEST_VISIBLE=1")
    def test_screenshot_is_the_output(self):
        shell = TestShell(visible=True).start()
        self.addCleanup(shell.stop)
        w, h, rgb = shot(shell, self.tmp)
        mon = json.loads(subprocess.run(["hyprctl", "monitors", "-j"], env=shell._env(), capture_output=True, text=True,
                                        timeout=5).stdout)[0]
        self.assertEqual((w, h), (mon["width"], mon["height"]))     # a nested output takes its window's size
        # a grid every 8 rows and 32 columns: the desktop of a fresh home is one colour (no wallpaper), the bar is not
        colours = {rgb[(y * w + x) * 3:(y * w + x) * 3 + 3] for y in range(0, h, 8) for x in range(0, w, 32)}
        self.assertGreater(len(colours), 1, "the nested output is one flat colour")

    def test_bar_moves_to_bottom(self):
        """Through the bar's own status hook (no pixels: the hidden test window does not draw)."""
        shell = TestShell().start()
        self.addCleanup(shell.stop)

        def positions():
            return {b["position"] for b in json.loads(shell.ipc("bar", "status"))}
        self.assertEqual(positions(), {"top"})
        shell.set("shell.barPosition", "bottom")
        end = time.monotonic() + 5
        while positions() != {"bottom"} and time.monotonic() < end:
            time.sleep(0.2)
        self.assertEqual(positions(), {"bottom"})

    @unittest.skipUnless(VISIBLE, "needs a visible test window: BBKOS_SHELLTEST_VISIBLE=1")
    def test_bar_moves_on_screen(self):
        """The same, seen in pixels (opt-in: the window shows on the owner's screen while it runs)."""
        shell = TestShell(visible=True).start()
        self.addCleanup(shell.stop)

        def settle(want_top: bool):
            end = time.monotonic() + 5
            while True:
                top, bottom = bands(shell, self.tmp)
                if has_bar(top, bottom, want_top) or time.monotonic() > end:
                    return top, bottom
                time.sleep(0.3)
        top, bottom = settle(want_top=True)
        self.assertTrue(has_bar(top, bottom, True), f"bar not at the top: top band {top:.2f}, bottom band {bottom:.2f} non-desktop")
        shell.set("shell.barPosition", "bottom")
        top, bottom = settle(want_top=False)
        self.assertTrue(has_bar(top, bottom, False), f"bar did not move: top band {top:.2f}, bottom band {bottom:.2f} non-desktop")

    def test_missing_key_shows_default(self):
        shell = TestShell().start(remove=["power.chargeMode"])
        self.addCleanup(shell.stop)
        settings = json.loads((shell.home / ".config/bbkos/settings.json").read_text())
        self.assertNotIn("chargeMode", settings["power"])
        shell.ipc("settings", "toggle")
        shell.ipc("settings", "page", "power/profiles")
        end = time.monotonic() + 5
        while json.loads(shell.ipc("settings", "shown", "power.chargeMode")) is None and time.monotonic() < end:
            time.sleep(0.2)
        self.assertEqual(json.loads(shell.ipc("settings", "shown", "power.chargeMode")), "default")


if __name__ == "__main__":
    unittest.main()
