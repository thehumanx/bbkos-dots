import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))

from bbkos_theme import keybinds as K  # noqa: E402
from bbkos_theme.reload import lua_quote  # noqa: E402


def bind(action, mods=("SUPER",), key="Q", enabled=True, **flags):
    f = {"locked": False, "repeating": False, "mouse": False}
    f.update(flags)
    return {"id": "x", "keys": {"mods": list(mods), "key": key}, "action": action,
            "flags": f, "enabled": enabled}


def exec_bind(cmd, **kw):
    return bind({"type": "exec", "command": cmd}, **kw)


def bind_lines(text):
    return [ln for ln in text.splitlines() if ln.startswith("hl.bind(")]


class RenderTest(unittest.TestCase):
    def test_quoted_command_round_trips(self):
        cmd = 'echo "a\\b; c" && printf \'é\''
        out = K.render_lua([exec_bind(cmd)])
        self.assertIn(lua_quote(cmd), out)

    def test_header_comment_first_and_trailing_newline(self):
        out = K.render_lua([exec_bind("true")])
        self.assertTrue(out.startswith("-- "))
        self.assertIn("generated", out.splitlines()[0].lower())
        self.assertTrue(out.endswith("\n"))

    def test_disabled_bind_not_rendered(self):
        out = K.render_lua([exec_bind("a"), exec_bind("b", enabled=False)])
        self.assertEqual(len(bind_lines(out)), 1)
        self.assertNotIn('"b"', out)

    def test_mouse_flag_renders_mouse_option(self):
        out = K.render_lua([bind({"type": "dispatch", "name": "window.drag", "args": {}},
                                 key="mouse:272", mouse=True)])
        self.assertEqual(bind_lines(out), [
            'hl.bind("SUPER + mouse:272", hl.dsp.window.drag(), { mouse = true })'])

    def test_flag_order_and_omission(self):
        out = K.render_lua([exec_bind("a", repeating=True, locked=True), exec_bind("b")])
        l1, l2 = bind_lines(out)
        self.assertTrue(l1.endswith('), { locked = true, repeating = true })'), l1)
        self.assertTrue(l2.endswith('exec_cmd("b"))'), l2)

    def test_mods_in_canonical_order(self):
        out = K.render_lua([exec_bind("a", mods=("SHIFT", "SUPER"))])
        self.assertIn('"SUPER + SHIFT + Q"', out)

    def test_dispatch_args(self):
        d = lambda n, **a: bind({"type": "dispatch", "name": n, "args": a})  # noqa: E731
        out = K.render_lua([
            d("focus", workspace=3),
            d("window.move", workspace="special:magic"),
            d("layout", layout="togglesplit"),
            d("workspace.toggle_special", name="magic"),
            d("window.float", action="toggle")])
        self.assertEqual([ln.split(", ", 1)[1][:-1] for ln in bind_lines(out)], [
            "hl.dsp.focus({ workspace = 3 })",
            'hl.dsp.window.move({ workspace = "special:magic" })',
            'hl.dsp.layout("togglesplit")',
            'hl.dsp.workspace.toggle_special("magic")',
            'hl.dsp.window.float({ action = "toggle" })'])

    def test_directional_focus_cycles_when_the_layout_is_monocle(self):
        # Stage mode stacks a workspace's windows, so left/up and right/down cycle them; any other layout is unchanged.
        out = K.render_lua([bind({"type": "dispatch", "name": "focus", "args": {"direction": "left"}}),
                            bind({"type": "dispatch", "name": "focus", "args": {"direction": "down"}})])
        left, down = bind_lines(out)
        self.assertIn('ws.tiled_layout == "monocle"', left)
        self.assertIn('hl.dsp.layout("cycleprev")', left)
        self.assertIn('hl.dsp.focus({ direction = "left" })', left)
        self.assertIn('hl.dsp.layout("cyclenext")', down)
        self.assertIn('hl.dsp.focus({ direction = "down" })', down)

    def test_window_cycle_is_most_recently_used_and_ends_on_modifier_release(self):
        out = K.render_lua([bind({"type": "dispatch", "name": "window.cycle", "args": {"direction": "next"}}, mods=("ALT",), key="Tab"),
                            bind({"type": "dispatch", "name": "window.cycle", "args": {"direction": "prev"}}, mods=("ALT", "SHIFT"), key="Tab")])
        nxt, prev = bind_lines(out)
        self.assertIn("function() bbkos_cycle(1) end", nxt)
        self.assertIn("function() bbkos_cycle(-1) end", prev)
        self.assertIn("BBKOS_MRU", out)
        self.assertIn('hl.on("window.active"', out)
        # Only the held modifier ends the cycle (Shift only picks the direction): Alt_L 64 and Alt_R 108, on key release.
        self.assertIn("local cycle_mods = { [64] = true, [108] = true }", out)
        self.assertIn('hl.on("input.keyboard.key"', out)
        self.assertIn("state == 0 and cycle_mods[code]", out)

    def test_window_cycle_without_a_held_modifier_ends_at_once(self):
        out = K.render_lua([bind({"type": "dispatch", "name": "window.cycle", "args": {"direction": "next"}}, mods=("SHIFT",), key="Tab")])
        self.assertEqual(bind_lines(out), ["hl.bind(\"SHIFT + Tab\", function() bbkos_cycle(1); bbkos_cycle_end() end)"])

    def test_lua_function_binds_look_at_the_live_window_or_config(self):
        d = lambda n: bind({"type": "dispatch", "name": n, "args": {}})  # noqa: E731
        tiled, opaque, gaps = bind_lines(K.render_lua([d("window.tiled_fullscreen"), d("window.toggle_opaque"), d("window.toggle_gaps")]))
        self.assertIn("hl.get_active_window()", tiled)
        self.assertIn("fullscreen_state({ internal = 0, client = (w.fullscreen_client == 2) and 0 or 2 })", tiled)
        self.assertIn('prop = "opaque", value = "toggle"', opaque)
        self.assertIn('"address:" .. w.address', opaque)
        self.assertIn("BBKOS_GAPS", gaps)
        self.assertIn("gaps_in = 0, gaps_out = 0", gaps)

    def test_preset_is_expanded(self):
        out = K.render_lua([bind({"type": "preset", "id": "launch-terminal"})])
        self.assertIn('exec_cmd("uwsm app -T")', out)


if __name__ == "__main__":
    unittest.main()
