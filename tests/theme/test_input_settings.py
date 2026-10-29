"""keyboard.*, mouse.* and cursor.*: the input lines of hypr-theme.lua, validation (nothing can break out of a Lua string),
and the cursor reload. Fake hyprctl and gsettings in PATH record the calls, so the live cursor is never touched."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dotfiles/bin/.local/lib"))
from bbkos_theme import reload as R, render, settings as S  # noqa: E402


def settings(**sections):
    s, _ = S.validate({"version": 1, **sections})
    return s


class RenderTest(unittest.TestCase):
    def test_defaults_render_the_old_static_values(self):
        text = "\n".join(render.render_input_extra(settings()))
        for line in ('kb_layout = "us"', 'kb_variant = ""', 'kb_options = ""', "repeat_rate = 25", "repeat_delay = 600",
                     "numlock_by_default = false", "sensitivity = 0", "natural_scroll = false", "left_handed = false"):
            self.assertIn(line, text)
        self.assertNotIn("accel_profile", text)

    def test_choices_reach_the_lines(self):
        s = settings(keyboard={"layout": "us,np", "variant": "dvorak,", "options": "caps:escape", "repeatRate": 40,
                               "numlock": True},
                     mouse={"accelProfile": "flat", "leftHanded": True, "sensitivity": -0.3})
        text = "\n".join(render.render_input_extra(s))
        for line in ('kb_layout = "us,np"', 'kb_variant = "dvorak,"', 'kb_options = "caps:escape"', "repeat_rate = 40",
                     "numlock_by_default = true", 'accel_profile = "flat"', "left_handed = true", "sensitivity = -0.3"):
            self.assertIn(line, text)

    def test_the_input_block_is_in_the_generated_file_and_has_the_cursor_env(self):
        lua = render.render_hypr_lua(_tokens(), settings(cursor={"size": 32}))
        self.assertIn('kb_layout = "us"', lua)
        self.assertIn('hl.env("XCURSOR_SIZE", "32")', lua)
        self.assertIn('hl.env("HYPRCURSOR_THEME", "Afterglow-cursors")', lua)

    def test_values_that_could_break_a_lua_string_are_refused(self):
        for key, bad in (("layout", 'us"}); os.execute("x")'), ("layout", "US"), ("layout", ""), ("variant", 'a"b')):
            s, warns = S.validate({"version": 1, "keyboard": {key: bad}})
            self.assertEqual(s["keyboard"][key], S.KEYBOARD_DEFAULTS[key], (key, bad))
            self.assertTrue(warns)
        s, warns = S.validate({"version": 1, "cursor": {"theme": 'x"y'}, "keyboard": {"options": "grp:alt_shift_toggle"}})
        self.assertEqual((s["cursor"]["theme"], s["keyboard"]["options"]), ("Afterglow-cursors", "none"))

    def test_ranges(self):
        s, _ = S.validate({"version": 1, "keyboard": {"repeatRate": 500, "repeatDelay": 20}, "mouse": {"sensitivity": 5},
                           "cursor": {"size": 50}})
        self.assertEqual((s["keyboard"]["repeatRate"], s["keyboard"]["repeatDelay"], s["mouse"]["sensitivity"],
                          s["cursor"]["size"]), (60, 150, 1.0, 48))


def _tokens():
    from bbkos_theme import palette as P
    pal = {role: "#808080" for role in P.ROLES}
    return render.tokens(pal, S.validate({"version": 1})[0])


class CursorReloadTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.state = self.dir / "state"
        self.state.mkdir()
        self.log = self.dir / "calls.log"
        bin_ = self.dir / "bin"
        bin_.mkdir()
        for name in ("hyprctl", "gsettings"):
            f = bin_ / name
            f.write_text(f'#!/bin/sh\necho "{name} $*" >> {self.log}\n')
            f.chmod(0o755)
        self.env = {"PATH": f"{bin_}:/usr/bin:/bin", "HOME": str(self.dir), "HYPRLAND_INSTANCE_SIGNATURE": "x"}

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_applies_once_and_again_when_the_choice_changes(self):
        s = settings(cursor={"size": 28})
        self.assertEqual(R.reload_cursor(self.state, self.env, s, real_home=self.dir), [])
        self.assertIn("hyprctl setcursor Afterglow-cursors 28", self.calls())
        self.assertIn("gsettings set org.gnome.desktop.interface cursor-size 28", self.calls())
        n = len(self.calls())
        R.reload_cursor(self.state, self.env, s, real_home=self.dir)
        self.assertEqual(len(self.calls()), n)
        R.reload_cursor(self.state, self.env, settings(cursor={"size": 32}), real_home=self.dir)
        self.assertIn("hyprctl setcursor Afterglow-cursors 32", self.calls())

    def test_never_touches_the_live_session_from_a_temporary_home_or_without_hyprland(self):
        s = settings(cursor={"size": 28})
        R.reload_cursor(self.state, self.env, s)                                   # HOME is not the real home
        R.reload_cursor(self.state, {**self.env, "HYPRLAND_INSTANCE_SIGNATURE": ""}, s, real_home=self.dir)
        R.reload_cursor(self.state, self.env, None, real_home=self.dir)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
