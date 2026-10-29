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
GROUPS = {"Shell", "Audio", "Display", "Screenshots", "Apps", "Windows",
          "Workspaces", "Mouse", "Custom"}


class CatalogueTest(unittest.TestCase):
    def test_every_preset_id_is_unique_and_has_a_group(self):
        ids = [e["id"] for e in A.CATALOGUE]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), set(A.ACTIONS))
        for e in A.CATALOGUE:
            self.assertIn(e["group"], GROUPS, e["id"])
            self.assertTrue(e["label"], e["id"])

    def test_defaults_only_reference_catalogue_ids(self):
        data = json.loads(DEFAULTS.read_text())
        for b in data["binds"]:
            if b["action"]["type"] == "preset":
                self.assertIn(b["action"]["id"], A.ACTIONS, b["id"])

    def test_expand_preset_returns_its_action(self):
        self.assertEqual(A.expand({"type": "preset", "id": "volume-up"})["type"], "exec")

    def test_expand_passes_through_exec_and_dispatch(self):
        ex = {"type": "exec", "command": "true"}
        dp = {"type": "dispatch", "name": "window.close", "args": {}}
        self.assertEqual(A.expand(ex), ex)
        self.assertEqual(A.expand(dp), dp)

    def test_missing_tools_reports_absent_command(self):
        self.assertEqual(A.missing_tools(A.ACTIONS["volume-up"], which=lambda c: None), ["wpctl"])
        self.assertEqual(A.missing_tools(A.ACTIONS["volume-up"], which=lambda c: "/x"), [])
        self.assertEqual(A.missing_tools(A.ACTIONS["close-window"], which=lambda c: None), [])

    def test_needs(self):
        for i in ("volume-up", "volume-down", "volume-mute", "mic-mute"):
            self.assertEqual(A.ACTIONS[i]["needs"], "wpctl")
        for i in ("media-next", "media-play-pause", "media-prev"):
            self.assertEqual(A.ACTIONS[i]["needs"], "playerctl")
        for i in ("brightness-up", "brightness-down"):
            self.assertEqual(A.ACTIONS[i]["needs"], "bbkos-brightness")
        for i in ("screenshot-region",):
            self.assertEqual(A.ACTIONS[i]["needs"], "omasnap")
        self.assertEqual(A.ACTIONS["record-menu"]["needs"], "bbkos-record")
        self.assertEqual(A.ACTIONS["ocr-text"]["needs"], "bbkos-ocr")
        for i in ("volume-up-precise", "volume-down-precise"):
            self.assertEqual(A.ACTIONS[i]["needs"], "wpctl")
        for i in ("brightness-up-precise", "brightness-down-precise"):
            self.assertEqual(A.ACTIONS[i]["needs"], "bbkos-brightness")
        for i in ("launcher", "clipboard", "settings-window", "power-panel", "emoji-picker", "toggle-bar"):
            self.assertEqual(A.ACTIONS[i]["needs"], "qs")

    def test_apps_presets(self):
        self.assertEqual(A.ACTIONS["launch-terminal"]["action"]["command"], "uwsm app -T")
        self.assertEqual(A.ACTIONS["launch-files"]["action"]["command"], "uwsm app -- thunar")
        self.assertEqual(A.ACTIONS["claude-bbkos"]["action"]["command"],
                         'uwsm app -- kitty --directory "$HOME/.local/share/bbkos/repo" claude')

    def test_dictation_preset(self):
        e = A.ACTIONS["dictation-toggle"]
        self.assertEqual(e["action"]["command"],
                         'voxtype record toggle || notify-send -a bbkos "Dictation" "Voxtype is not running: systemctl --user status voxtype"')
        self.assertEqual(e["needs"], "voxtype")
        self.assertEqual(e["group"], "Shell")

    def test_dispatch_args_cover_every_dispatcher_used(self):
        names = {e["action"]["name"] for e in A.CATALOGUE if e["action"]["type"] == "dispatch"}
        for n in names:
            self.assertIn(n, A.DISPATCH_ARGS)
        for e in A.CATALOGUE:
            a = e["action"]
            if a["type"] == "dispatch":
                self.assertLessEqual(set(a["args"]), set(A.DISPATCH_ARGS[a["name"]]), e["id"])
        for n in ("exec_cmd", "focus", "window.close", "window.float", "window.pseudo",
                  "window.move", "window.drag", "window.resize", "layout",
                  "workspace.toggle_special"):
            self.assertIn(n, A.DISPATCH_ARGS)

    def test_exec_commands_match_fixture(self):
        fixture = FIXTURE.read_text()
        for e in A.CATALOGUE:
            if e["action"]["type"] == "exec":
                self.assertIn('exec_cmd(%s)' % json.dumps(e["action"]["command"]),
                              fixture, e["id"])

    def test_locked_ok_matches_defaults_locked_flag(self):
        data = json.loads(DEFAULTS.read_text())
        for b in data["binds"]:
            if b["flags"]["locked"]:
                self.assertTrue(A.ACTIONS[b["action"]["id"]].get("locked_ok"), b["id"])

    def test_dispatch_args_keys_are_strings(self):
        for k, v in A.DISPATCH_ARGS.items():
            self.assertIsInstance(v, tuple)
            self.assertTrue(all(isinstance(x, str) for x in v), k)

    def test_known_keys_importable(self):
        self.assertTrue(K.KNOWN_KEYS)


if __name__ == "__main__":
    unittest.main()
