"""The Voxtype config shipped as the Stow package `voxtype` (docs/modules/dictation.md)."""
import tomllib
import unittest
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[2] / "dotfiles/voxtype/.config/voxtype/config.toml"


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.cfg = tomllib.loads(CONFIG.read_text())

    def test_hotkey_is_off(self):
        self.assertIs(self.cfg["hotkey"]["enabled"], False)       # the key is a Hyprland bind, not Voxtype's evdev reader

    def test_english_small_model(self):
        self.assertEqual(self.cfg["whisper"]["model"], "small.en")
        self.assertEqual(self.cfg["whisper"]["language"], "en")
        self.assertIs(self.cfg["whisper"]["translate"], False)

    def test_types_with_clipboard_fallback(self):
        self.assertEqual(self.cfg["output"]["mode"], "type")
        self.assertIs(self.cfg["output"]["fallback_to_clipboard"], True)

    def test_pauses_media_and_caps_length(self):
        self.assertIs(self.cfg["audio"]["pause_media"], True)
        self.assertEqual(self.cfg["audio"]["max_duration_secs"], 60)

    def test_model_loads_on_demand(self):
        self.assertIs(self.cfg["whisper"]["on_demand_loading"], True)    # about 600 MB of memory back between dictations

    def test_osd_is_off(self):
        self.assertIs(self.cfg["osd"]["enabled"], False)        # the GTK4 waveform panel keeps a ~75 MB process resident

    def test_state_file_auto(self):
        self.assertEqual(self.cfg["state_file"], "auto")


if __name__ == "__main__":
    unittest.main()
