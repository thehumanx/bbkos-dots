"""Branding settings: the screensaver listener in the generated hypridle.conf, and the branding files."""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))
from bbkos_theme import branding, render, settings as S  # noqa: E402


def commands(text):
    return [l.split("=", 1)[1].strip() for l in text.splitlines() if l.strip().startswith("on-timeout")]


def timeouts(text):
    return [int(l.split("=")[1]) for l in text.splitlines() if l.strip().startswith("timeout")]


class IdleScreensaverTest(unittest.TestCase):
    def conf(self, idle=None, branding=None):
        s, _ = S.validate({"version": 1, "idle": idle or {}, "branding": branding or {}})
        return render.render_hypridle(s)

    def test_defaults_add_screensaver_and_drop_dim(self):
        text = self.conf()
        self.assertEqual(timeouts(text), [150, 150, 300, 330, 900])
        cmds = commands(text)
        self.assertEqual(cmds[0], "bbkos-awake idle-screensaver")
        self.assertNotIn("bbkos-awake idle-dim", cmds)
        self.assertIn("bbkos-awake idle-kbd", cmds)

    def test_screensaver_off_restores_dim(self):
        cmds = commands(self.conf(branding={"screensaver": False}))
        self.assertIn("bbkos-awake idle-dim", cmds)
        self.assertNotIn("bbkos-awake idle-screensaver", cmds)

    def test_zero_timer_has_no_screensaver_listener(self):
        cmds = commands(self.conf(idle={"screensaver": 0}))
        self.assertNotIn("bbkos-awake idle-screensaver", cmds)
        self.assertIn("bbkos-awake idle-dim", cmds)

    def test_keyboard_light_follows_the_screensaver_step(self):
        text = self.conf(idle={"screensaver": 210, "dim": 0})
        pairs = list(zip(timeouts(text), commands(text)))
        self.assertIn((210, "bbkos-awake idle-kbd"), pairs)
        self.assertIn((210, "bbkos-awake idle-screensaver"), pairs)

    def test_keyboard_light_follows_dim_when_the_screensaver_is_off(self):
        text = self.conf(idle={"dim": 90}, branding={"screensaver": False})
        self.assertIn((90, "bbkos-awake idle-kbd"), list(zip(timeouts(text), commands(text))))

    def test_effects_default_to_decrypt(self):
        s, warns = S.validate({"version": 1})
        self.assertEqual(s["branding"]["effects"], ["decrypt"])
        self.assertEqual(warns, [])

    def test_effects_keep_the_list_order_and_drop_unknown_and_repeated(self):
        s, warns = S.validate({"version": 1, "branding": {"effects": ["waves", "nope", "beams", "waves"]}})
        self.assertEqual(s["branding"]["effects"], ["beams", "waves"])
        self.assertTrue(warns)

    def test_the_old_single_effect_key_becomes_the_list(self):
        s, warns = S.validate({"version": 1, "branding": {"screensaver": True, "effect": "rain"}})
        self.assertEqual(s["branding"]["effects"], ["rain"])
        self.assertEqual(warns, [])                      # no "unknown key" warning for the old name

    def test_the_new_key_wins_over_the_old_one(self):
        s, _ = S.validate({"version": 1, "branding": {"effect": "rain", "effects": ["matrix"]}})
        self.assertEqual(s["branding"]["effects"], ["matrix"])

    def test_an_unknown_old_effect_falls_back(self):
        s, warns = S.validate({"version": 1, "branding": {"effect": "nope"}})
        self.assertEqual(s["branding"]["effects"], ["decrypt"])
        self.assertTrue(warns)

    def test_an_empty_list_falls_back_to_decrypt(self):
        s, warns = S.validate({"version": 1, "branding": {"effects": []}})
        self.assertEqual(s["branding"]["effects"], ["decrypt"])
        self.assertTrue(warns)

    def test_set_from_the_command_line(self):
        s = S.set_value(S.DEFAULTS, "branding.effects", "matrix, decrypt")
        self.assertEqual(s["branding"]["effects"], ["decrypt", "matrix"])
        self.assertEqual(S.DEFAULTS["branding"]["effects"], ["decrypt"])      # the defaults are not shared or changed
        with self.assertRaises(ValueError):
            S.set_value(S.DEFAULTS, "branding.effects", "decrypt,nope")
        with self.assertRaises(ValueError):
            S.set_value(S.DEFAULTS, "branding.effects", "")


class FilesTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.dir = self.home / ".config/bbkos/branding"

    def test_missing_file_falls_back_to_the_default(self):
        self.assertEqual(branding.read("about", self.home), branding.default("about"))
        self.assertTrue(branding.default("about").strip())

    def test_whitespace_only_file_is_empty(self):
        self.dir.mkdir(parents=True)
        (self.dir / "screensaver.txt").write_text("  \n\n \t\n")
        self.assertEqual(branding.read("screensaver", self.home), "")

    def test_set_text_copies_file(self):
        src = self.home / "mine.txt"
        src.write_text("HELLO\n")
        branding.set_text("about", src, self.home)
        self.assertEqual(branding.read("about", self.home), "HELLO\n")

    def test_reset_restores_default(self):
        self.dir.mkdir(parents=True)
        (self.dir / "about.txt").write_text("x\n")
        branding.reset("about", self.home)
        self.assertEqual(branding.read("about", self.home), branding.default("about"))

    def test_unknown_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            branding.read("lock", self.home)

    def test_words_drops_unknown_characters_and_reports(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            art = branding.words("Hi 5!")
        self.assertEqual(len(art.rstrip("\n").splitlines()), 5)
        self.assertIn("5", err.getvalue())
        self.assertIn("!", err.getvalue())

    def test_double_width_detected(self):
        self.assertFalse(branding.is_single_width("ab\n漢字\n"))
        self.assertFalse(branding.is_single_width("😀"))
        self.assertTrue(branding.is_single_width("⣿⣿ ab\n██\n"))


if __name__ == "__main__":
    unittest.main()
