import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))

from bbkos_theme import keybinds as K  # noqa: E402

DEFAULTS = ROOT / "dotfiles/bin/.local/lib/bbkos_theme/keybinds.defaults.json"


def bind(id_="b", mods=("SUPER",), key="Q", action=None, flags=None, enabled=True):
    return {
        "id": id_,
        "keys": {"mods": list(mods), "key": key},
        "action": action or {"type": "exec", "command": "true"},
        "flags": flags or {"locked": False, "repeating": False, "mouse": False},
        "enabled": enabled,
    }


class ComboTest(unittest.TestCase):
    def test_modifier_order_is_the_same_combo(self):
        a = K.canonical_combo({"mods": ["SHIFT", "SUPER"], "key": "S"})
        b = K.canonical_combo({"mods": ["SUPER", "SHIFT"], "key": "s"})
        self.assertEqual(a, b)
        self.assertEqual(a, (("SUPER", "SHIFT"), "S"))

    def test_alias_is_the_same_combo(self):
        self.assertEqual(K.canonical_combo({"mods": [], "key": "Enter"}),
                         K.canonical_combo({"mods": [], "key": "Return"}))

    def test_aliases(self):
        self.assertEqual(K.key_alias("Prior"), "Page_Up")
        self.assertEqual(K.key_alias(","), "comma")
        self.assertEqual(K.key_alias("q"), "Q")
        self.assertEqual(K.key_alias("7"), "7")
        self.assertEqual(K.key_alias("Print"), "Print")

    def test_punctuation_keys_the_recorder_can_produce_are_known(self):
        # components/KeyCapture.qml names these keys; the validator must accept each of them.
        for name in ("semicolon", "period", "minus", "equal", "slash", "backslash", "apostrophe", "bracketleft",
                     "bracketright", "grave", "Insert"):
            self.assertIn(K.key_alias(name), K.KNOWN_KEYS, name)
        self.assertEqual(K.key_alias(";"), "semicolon")
        self.assertEqual(K.key_alias("SEMICOLON"), "semicolon")


class ValidateTest(unittest.TestCase):
    ACTIONS = {"launch-terminal"}

    def v(self, raw):
        return K.validate_bind(raw, self.ACTIONS)

    def test_good_bind_is_clean(self):
        clean, warns = self.v(bind(key="q"))
        self.assertEqual(clean["keys"]["key"], "Q")
        self.assertEqual(warns, [])

    def test_errors(self):
        cases = {
            "no id": {**bind(), "id": None},
            "non-object": "x",
            "key int": bind(key=7),
            "unknown mod": bind(mods=("HYPER",)),
            "unknown key": bind(key="Bogus"),
            "unknown flag": bind(flags={"locked": False, "turbo": True}),
            "bad action type": bind(action={"type": "nope"}),
            "unknown preset": bind(action={"type": "preset", "id": "zzz"}),
            "empty command": bind(action={"type": "exec", "command": "  "}),
            "multi-line": bind(action={"type": "exec", "command": "a\nb"}),
            "too long": bind(action={"type": "exec", "command": "x" * 513}),
            "mouse without flag": bind(key="mouse:272"),
        }
        for name, raw in cases.items():
            with self.subTest(name):
                clean, errs = self.v(raw)
                self.assertIsNone(clean)
                self.assertTrue(errs)

    def test_unknown_dispatcher_is_rejected(self):
        clean, errs = self.v(bind(action={"type": "dispatch", "name": "no.such", "args": {}}))
        self.assertIsNone(clean)
        self.assertEqual(errs, ["b: unknown dispatcher no.such"])
        clean, _ = self.v(bind(action={"type": "dispatch", "name": "window.close", "args": {}}))
        self.assertIsNotNone(clean)

    def test_reserved_combos_warn_but_pass(self):
        for mods, key in ((("ALT",), "f4"), (("ALT", "CTRL"), "Delete"),
                          (("SHIFT",), "Tab")):
            clean, warns = self.v(bind(mods=mods, key=key))
            self.assertIsNotNone(clean)
            reserved = key.lower() != "tab"
            self.assertEqual(bool(warns), reserved, (mods, key))
        for key in ("BackSpace", "Escape"):
            clean, warns = self.v(bind(mods=("CTRL", "ALT"), key=key))
            self.assertIsNotNone(clean)
            self.assertEqual(len(warns), 1)

    def test_locked_flag_rules(self):
        locked = {"locked": True}
        clean, warns = self.v(bind(key="Q", flags=locked))
        self.assertIsNotNone(clean)
        self.assertEqual(len(warns), 1)
        clean, warns = self.v(bind(mods=(), key="XF86AudioRaiseVolume", flags=locked))
        self.assertIsNotNone(clean)
        self.assertEqual(warns, [])
        clean, errs = self.v(bind(mods=(), key="XF86PowerOff", flags=locked))
        self.assertIsNone(clean)
        self.assertTrue(errs)
        self.assertIsNotNone(self.v(bind(mods=(), key="XF86PowerOff"))[0])

    def test_none_actions_skips_preset_check(self):
        raw = bind(action={"type": "preset", "id": "anything"})
        self.assertIsNotNone(K.validate_bind(raw, None)[0])

    def test_load_surfaces_bind_warnings(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "keybinds.json"
            p.write_text(json.dumps({"version": 1, "binds": [
                bind("w", mods=("ALT",), key="F4")]}))
            binds, warns = K.load_binds(p, DEFAULTS)
        self.assertEqual(len(binds), 1)
        self.assertEqual(len(warns), 1)

    def test_keys_must_be_exactly_mods_and_key(self):
        raw = bind()
        raw["keys"]["extra"] = 1
        self.assertIsNone(self.v(raw)[0])

    def test_boundary_and_valid_triggers(self):
        self.assertIsNotNone(self.v(bind(action={"type": "exec", "command": "x" * 512}))[0])
        self.assertIsNotNone(self.v(bind(key="mouse:272", flags={"mouse": True}))[0])
        self.assertIsNotNone(self.v(bind(key="switch:on:Lid Switch", mods=()))[0])
        self.assertIsNotNone(self.v(bind(action={"type": "preset", "id": "launch-terminal"}))[0])

    def test_defaults_validate_with_their_own_preset_ids(self):
        data = json.loads(DEFAULTS.read_text())
        ids = {b["action"]["id"] for b in data["binds"] if b["action"]["type"] == "preset"}
        for raw in data["binds"]:
            clean, errs = K.validate_bind(raw, ids)
            self.assertIsNotNone(clean, (raw["id"], errs))


class LoadTest(unittest.TestCase):
    def test_missing_file_reads_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            binds, warns = K.load_binds(Path(d) / "keybinds.json", DEFAULTS)
        self.assertEqual(len(binds), 74)
        self.assertEqual(warns, [])

    def test_malformed_row_is_skipped_rest_loads(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "keybinds.json"
            p.write_text(json.dumps({"version": 1, "binds": [
                bind("good"), {**bind("bad"), "keys": {"mods": [], "key": 7}}]}))
            binds, warns = K.load_binds(p, DEFAULTS)
        self.assertEqual([b["id"] for b in binds], ["good"])
        self.assertEqual(len(warns), 1)
        self.assertIn("bad", warns[0])

    def test_non_object_file_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "keybinds.json"
            p.write_text("[]")
            binds, warns = K.load_binds(p, DEFAULTS)
        self.assertEqual(len(binds), 74)
        self.assertEqual(len(warns), 1)
        self.assertIn("keybinds.json", warns[0])

    def test_unparseable_file_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "keybinds.json"
            p.write_text("{nope")
            binds, warns = K.load_binds(p, DEFAULTS)
        self.assertEqual(len(binds), 74)
        self.assertIn("keybinds.json", warns[0])


class ConflictTest(unittest.TestCase):
    def test_conflict_detected_and_disabled_row_ignored(self):
        a = bind("a", key="Q")
        b = bind("b", mods=("SUPER",), key="q")
        c = bind("c", key="Q", enabled=False)
        d = bind("d", key="W")
        self.assertEqual(K.find_conflicts([a, b, c, d]), [("a", "b")])

    def test_defaults_have_no_conflicts(self):
        binds, _ = K.load_binds(Path("/nonexistent/x.json"), DEFAULTS)
        self.assertEqual(K.find_conflicts(binds), [])


class SaveTest(unittest.TestCase):
    def test_save_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sub" / "keybinds.json"
            K.save_atomic(p, [bind("a")])
            self.assertEqual(json.loads(p.read_text())["binds"][0]["id"], "a")
            self.assertTrue(p.read_text().endswith("\n"))
            binds, warns = K.load_binds(p, DEFAULTS)
        self.assertEqual([b["id"] for b in binds], ["a"])


if __name__ == "__main__":
    unittest.main()
