import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))

from bbkos_theme import keybind_actions as A  # noqa: E402
from bbkos_theme import keybinds as K  # noqa: E402

DEFAULTS = ROOT / "dotfiles/bin/.local/lib/bbkos_theme/keybinds.defaults.json"
FIXTURE = ROOT / "tests/keybinds/fixtures/expected-hypr-binds.lua"


class DefaultsTest(unittest.TestCase):
    def setUp(self):
        self.binds = json.loads(DEFAULTS.read_text())["binds"]

    def test_render_matches_fixture(self):
        out = K.render_lua(self.binds)
        got = sorted(ln for ln in out.splitlines() if ln.startswith("hl.bind("))
        want = sorted(ln for ln in FIXTURE.read_text().splitlines() if ln.strip())
        self.assertEqual(got, want)

    def test_dictation_bind_is_super_ctrl_x_and_not_locked(self):
        b = next(b for b in self.binds if b["id"] == "dictation-toggle")
        self.assertEqual(b["keys"], {"mods": ["SUPER", "CTRL"], "key": "X"})
        self.assertEqual(b["action"], {"type": "preset", "id": "dictation-toggle"})
        self.assertIs(b["flags"]["locked"], False)            # never fires on the lock screen
        self.assertEqual(K.find_conflicts(self.binds), [])

    def test_hyprland_lua_loads_bind_file_and_keeps_lid_binds(self):
        text = (ROOT / "dotfiles/hypr/.config/hypr/hyprland.lua").read_text()
        self.assertIn("hypr-binds.lua", text)
        self.assertIn('"switch:on:Lid Switch"', text)
        self.assertIn('"switch:off:Lid Switch"', text)
        self.assertIn('hl.on("monitor.removed"', text)
        self.assertIn('hl.on("monitor.added"', text)
        self.assertNotIn('hl.bind(mainMod .. " + Q"', text)

    def test_hyprland_lua_binds_only_lid_switch(self):
        text = (ROOT / "dotfiles/hypr/.config/hypr/hyprland.lua").read_text()
        binds = [ln for ln in text.splitlines() if ln.startswith("hl.bind(")]
        self.assertEqual(len(binds), 2)
        self.assertTrue(all("Lid Switch" in ln for ln in binds), binds)

    def test_ids_unique(self):
        ids = [b["id"] for b in self.binds]
        self.assertEqual(len(ids), len(set(ids)))

    def test_no_duplicate_combos(self):
        combos = [K.canonical_combo(b["keys"]) for b in self.binds]
        self.assertEqual(len(combos), len(set(combos)))

    def test_presets_exist(self):
        for b in self.binds:
            if b["action"]["type"] == "preset":
                self.assertIn(b["action"]["id"], A.ACTIONS)


if __name__ == "__main__":
    unittest.main()
