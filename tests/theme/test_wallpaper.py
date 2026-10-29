import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))

from bbkos_theme import wallpaper as W  # noqa: E402


class WallpaperTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.share = self.base / "share"

    def test_set_copies_and_replaces_other_extensions(self):
        a = self.base / "A.PNG"
        a.write_bytes(b"png-bytes")
        dest = W.set_wallpaper(a, self.share)
        self.assertEqual(dest, self.share.absolute() / "current.png")
        self.assertEqual(dest.read_bytes(), b"png-bytes")
        b = self.base / "b.jpeg"
        b.write_bytes(b"jpeg-bytes")
        (self.share / "current.gif.new").write_bytes(b"stale")
        dest = W.set_wallpaper(b, self.share)
        self.assertEqual(sorted(p.name for p in self.share.iterdir()), ["current.jpeg", "previous.png"])
        self.assertEqual((self.share / "previous.png").read_bytes(), b"png-bytes")
        b.unlink()  # a copy: the original can go away
        self.assertEqual(dest.read_bytes(), b"jpeg-bytes")
        W.clear_wallpaper(self.share)
        self.assertEqual([p.name for p in self.share.iterdir()], ["previous.jpeg"])
        self.assertEqual((self.share / "previous.jpeg").read_bytes(), b"jpeg-bytes")
        W.clear_wallpaper(self.share)  # nothing current: the previous copy stays
        self.assertEqual([p.name for p in self.share.iterdir()], ["previous.jpeg"])
        W.clear_wallpaper(self.base / "never-created")

    def test_set_twice_same_extension_keeps_one_previous_copy(self):
        for i in range(3):
            src = self.base / f"p{i}.png"
            src.write_bytes(b"bytes-%d" % i)
            W.set_wallpaper(src, self.share)
        self.assertEqual(sorted(p.name for p in self.share.iterdir()), ["current.png", "previous.png"])
        self.assertEqual((self.share / "current.png").read_bytes(), b"bytes-2")
        self.assertEqual((self.share / "previous.png").read_bytes(), b"bytes-1")

    def test_previous_is_never_taken_for_the_current_copy(self):
        self.share.mkdir()
        (self.share / "previous.png").write_bytes(b"old")
        (self.share / "current.new.jpg").write_bytes(b"staged leftover")
        self.assertIsNone(W.retire_current(self.share))  # no current copy: nothing moves
        self.assertEqual((self.share / "previous.png").read_bytes(), b"old")
        W.remove_others(self.share, keep=self.share / "current.png")
        self.assertEqual([p.name for p in self.share.iterdir()], ["previous.png"])
        # the documented undo: setting previous.<ext> as the wallpaper swaps the two copies
        a = self.base / "a.jpg"
        a.write_bytes(b"new")
        W.set_wallpaper(a, self.share)
        W.set_wallpaper(self.share / "previous.png", self.share)
        self.assertEqual(sorted(p.name for p in self.share.iterdir()), ["current.png", "previous.jpg"])
        self.assertEqual((self.share / "current.png").read_bytes(), b"old")
        self.assertEqual((self.share / "previous.jpg").read_bytes(), b"new")

    def test_stage_keeps_image_extension_last_and_discard_removes_it(self):
        a = self.base / "x.webp"
        a.write_bytes(b"w")
        staged, final = W.stage(a, self.share)
        self.assertEqual(staged.name, "current.new.webp")
        self.assertEqual(final.name, "current.webp")
        self.assertFalse(final.exists())
        W.discard(staged)
        W.discard(staged)
        self.assertEqual(list(self.share.iterdir()), [])

    def test_check_source_rejects(self):
        (self.base / "d.png").mkdir()
        (self.base / "t.txt").write_text("x")
        (self.base / "noext").write_text("x")
        big = self.base / "big.gif"
        with open(big, "wb") as f:
            f.truncate(W.MAX_BYTES + 1)
        ok = self.base / "ok.BMP"
        ok.write_bytes(b"x")
        self.assertEqual(W.check_source(ok)[1], "bmp")
        for name, why in (("missing.png", "No such file"), ("d.png", "not a regular file"),
                          ("t.txt", "not a supported image type"), ("noext", "not a supported"),
                          ("big.gif", "too large")):
            with self.assertRaises(W.WallpaperError, msg=name) as cm:
                W.check_source(self.base / name)
            self.assertIn(why, str(cm.exception))
            self.assertIn(name, str(cm.exception))
        self.assertFalse(self.share.exists())


if __name__ == "__main__":
    unittest.main()
