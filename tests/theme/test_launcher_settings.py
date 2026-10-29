"""launcher.* settings: defaults keep today's menu, values are validated, and Launcher.qml reads every key."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))
from bbkos_theme import cli, settings as S  # noqa: E402

QML = (ROOT / "dotfiles/quickshell/.config/quickshell/modules/launcher/Launcher.qml").read_text()


class LauncherSettingsTest(unittest.TestCase):
    def test_defaults_are_todays_menu(self):
        self.assertEqual(S.DEFAULTS["launcher"], {"webSearch": "duckduckgo", "calculator": True, "maxResults": 40, "commands": True, "learn": True})

    def test_values_are_validated(self):
        s, warns = S.validate({"version": 1, "launcher": {"webSearch": "altavista", "maxResults": 3, "calculator": "yes", "learn": False}})
        self.assertEqual(s["launcher"], {"webSearch": "duckduckgo", "calculator": True, "maxResults": 10, "commands": True, "learn": False})
        self.assertEqual(len(warns), 3)

    def test_every_engine_has_an_address_in_the_menu(self):
        for name in S.WEB_SEARCH:
            if name != "off":
                self.assertIn(f"{name}: {{ name:", QML, name)

    def test_the_menu_reads_every_key_and_reset_knows_the_section(self):
        for key in S.LAUNCHER_DEFAULTS:
            self.assertIn(f"cfg.{key}", QML, key)
        self.assertIn("launcher", cli.SECTIONS)


if __name__ == "__main__":
    unittest.main()
