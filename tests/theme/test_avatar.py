import copy
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cli import Cli, png, S  # noqa: E402


class AvatarTest(unittest.TestCase):
    """`bbkos-theme avatar set FILE` / `avatar clear`: the lock screen picture is a copy named by its content, recorded
    in lock.avatar and written into hyprlock.conf; the shipped picture (a Stow link into the repo) is never written."""

    def ok(self, r):
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def fails_one_line(self, r, code=1):
        self.assertEqual(r.returncode, code, (r.stdout, r.stderr))
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)

    def folder(self, c):
        return c.base / "home/.local/share/bbkos/avatar"

    def test_set_copies_records_and_renders(self):
        c = Cli(self)
        a = c.src / "Me (1).png"
        png(a, pixel=b"\x01\x02\x03")
        self.ok(c.run("avatar", "set", "--", str(a)))
        want = self.folder(c) / f"avatar-{hashlib.sha256(a.read_bytes()).hexdigest()[:12]}.png"
        self.assertEqual(c.load()["lock"]["avatar"], str(want))
        self.assertEqual(want.read_bytes(), a.read_bytes())
        self.assertIn(f"    path = {want}\n", (c.state / "hyprlock.conf").read_text())

    def test_a_new_picture_replaces_the_old_copy_and_clear_goes_back(self):
        c = Cli(self)
        a, b = c.src / "a.png", c.src / "b.jpg"
        png(a, pixel=b"\x01\x01\x01")
        png(b, pixel=b"\x02\x02\x02")
        self.ok(c.run("avatar", "set", str(a)))
        self.ok(c.run("avatar", "set", str(b)))
        self.assertEqual([p.suffix for p in self.folder(c).iterdir()], [".jpg"])
        self.ok(c.run("avatar", "set", str(b)))                       # the same picture again keeps its copy
        self.assertEqual(len(list(self.folder(c).iterdir())), 1)
        self.ok(c.run("avatar", "clear"))
        self.assertEqual(c.load()["lock"]["avatar"], "")
        self.assertEqual(list(self.folder(c).iterdir()), [])
        self.assertIn("/.config/hypr/lock-avatar.png\n", (c.state / "hyprlock.conf").read_text())

    def test_refusals_change_nothing(self):
        c = Cli(self)
        a = c.src / "a.png"
        png(a)
        self.ok(c.run("avatar", "set", str(a)))
        before = c.settings.read_bytes()
        bad = c.src / "notes.txt"
        bad.write_text("x")
        self.fails_one_line(c.run("avatar", "set", str(bad)))
        self.fails_one_line(c.run("avatar", "set", str(c.src / "missing.png")))
        self.fails_one_line(c.run("set", "lock.avatar", str(a)))      # only `avatar set` makes the copy
        self.fails_one_line(c.run("avatar"), code=2)
        self.fails_one_line(c.run("avatar", "clear", "x"), code=2)
        self.assertEqual(c.settings.read_bytes(), before)
        self.assertEqual(len(list(self.folder(c).iterdir())), 1)

    def test_reset_of_the_key_goes_back_to_the_shipped_picture(self):
        c = Cli(self)
        a = c.src / "a.webp"
        a.write_bytes(b"RIFF....WEBP")
        self.ok(c.run("avatar", "set", str(a)))
        self.ok(c.run("reset", "lock.avatar"))
        self.assertEqual(c.load()["lock"]["avatar"], "")

    def test_hand_edited_values_are_refused(self):
        for value in ("/home/u/Pictures/me.png", "/home/u/x#y/avatar-0123456789ab.png",
                      "/a/avatar-0123456789ab.png\nimage {", "avatar-0123456789ab.png"):
            raw = copy.deepcopy(S.DEFAULTS)
            raw["lock"]["avatar"] = value
            out, warns = S.validate(raw)
            self.assertEqual(out["lock"]["avatar"], "", value)
        raw = copy.deepcopy(S.DEFAULTS)
        raw["lock"]["avatar"] = "/home/u/.local/share/bbkos/avatar/avatar-0123456789ab.png"
        self.assertEqual(S.validate(raw)[0]["lock"]["avatar"], raw["lock"]["avatar"])


if __name__ == "__main__":
    unittest.main()
