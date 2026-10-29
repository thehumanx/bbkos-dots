"""behavior.* and windows.animationSpeed: the Hyprland lines they render, their ranges, and the defaults that keep the old
behaviour (focus follows the mouse, apps may take focus)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dotfiles/bin/.local/lib"))
from bbkos_theme import render, settings as S  # noqa: E402


def settings(**sections):
    s, _ = S.validate({"version": 1, **sections})
    return s


class BehaviorTest(unittest.TestCase):
    def test_defaults_keep_the_old_behaviour(self):
        b = S.DEFAULTS["behavior"]
        self.assertEqual((b["followMouse"], b["focusOnActivate"], b["workspaceBackAndForth"], b["cursorWarps"], b["snap"]),
                         ("hover", True, False, True, False))
        self.assertEqual(S.DEFAULTS["windows"]["animationSpeed"], 1.0)

    def test_follow_mouse_maps_to_hyprlands_numbers(self):
        for name, number in S.FOLLOW_MOUSE.items():
            self.assertIn(f"follow_mouse = {number},", "\n".join(render.render_input_extra(settings(behavior={"followMouse": name}))))
        self.assertEqual(render.S_FOLLOW, S.FOLLOW_MOUSE)

    def test_behavior_entries(self):
        text = render.render_behavior(settings(behavior={"workspaceBackAndForth": True, "hideCursorWhenTyping": True,
                                                         "cursorHideAfter": 5, "cursorWarps": False}))
        for line in ("workspace_back_and_forth = true", "hide_on_key_press = true", "inactive_timeout = 5", "no_warps = true"):
            self.assertIn(line, text)

    def test_snap_and_focus_on_activate_reach_the_theme_file(self):
        from bbkos_theme import palette as P
        s = settings(behavior={"snap": True, "snapGap": 25, "focusOnActivate": False})
        lua = render.render_hypr_lua(render.tokens({r: "#808080" for r in P.ROLES}, s), s)
        self.assertIn("snap = { enabled = true, window_gap = 25, monitor_gap = 25 }", lua)
        self.assertIn("focus_on_activate = false", lua)

    def test_ranges(self):
        s = settings(behavior={"cursorHideAfter": 99, "snapGap": 7, "followMouse": "x"}, windows={"animationSpeed": 9})
        self.assertEqual((s["behavior"]["cursorHideAfter"], s["behavior"]["snapGap"], s["behavior"]["followMouse"],
                          s["windows"]["animationSpeed"]), (20, 5, "hover", 2.0))

    def test_animation_speed_divides_every_duration_and_one_changes_nothing(self):
        base, fast = render.render_motion(False, 1.0), render.render_motion(False, 2.0)
        self.assertIn('leaf = "workspaces", enabled = true, speed = 2.6,', base)
        self.assertIn('leaf = "workspaces", enabled = true, speed = 1.3,', fast)
        self.assertIn('leaf = "global", enabled = true, speed = 1.0,', fast)


if __name__ == "__main__":
    unittest.main()
