"""notifications.* settings: ranges, defaults and the reset section."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dotfiles/bin/.local/lib"))
from bbkos_theme import cli, settings as S  # noqa: E402


class NotificationSettingsTest(unittest.TestCase):
    def test_defaults_keep_todays_behaviour(self):
        n = S.DEFAULTS["notifications"]
        self.assertEqual((n["timeout"], n["maxPopups"], n["historySize"], n["position"]), (6, 5, 100, "auto"))
        self.assertTrue(n["senderTimeout"] and n["criticalSticky"] and n["showPictures"])

    def test_toasts_default_on_and_take_booleans(self):
        keys = ("toastCharger", "toastAudio", "toastVpn")
        self.assertTrue(all(S.DEFAULTS["notifications"][k] for k in keys))
        out = S.set_value(S.validate({"version": 1})[0], "notifications.toastVpn", "false")
        self.assertEqual([out["notifications"][k] for k in keys], [True, True, False])

    def test_values_are_clamped_and_snapped(self):
        s, warns = S.validate({"version": 1, "notifications": {"timeout": 99, "maxPopups": 0, "historySize": 55,
                                                              "position": "middle"}})
        n = s["notifications"]
        self.assertEqual((n["timeout"], n["maxPopups"], n["historySize"], n["position"]), (30, 1, 60, "auto"))
        self.assertEqual(len(warns), 4)

    def test_corner_choices(self):
        s, warns = S.validate({"version": 1, "notifications": {"position": "bottom-left"}})
        self.assertEqual((s["notifications"]["position"], warns), ("bottom-left", []))

    def test_muted_apps_default_is_empty_and_not_shared(self):
        self.assertEqual(S.DEFAULTS["notifications"]["mutedApps"], [])
        s, _ = S.validate({"version": 1})
        s["notifications"]["mutedApps"].append("x")
        self.assertEqual(S.DEFAULTS["notifications"]["mutedApps"], [])

    def test_muted_apps_are_cleaned(self):
        s, warns = S.validate({"version": 1, "notifications": {"mutedApps": [" Slack ", "Slack", "", "a,b", "x" * 65, 5, "Spotify"]}})
        self.assertEqual(s["notifications"]["mutedApps"], ["Slack", "Spotify"])
        self.assertEqual(len(warns), 1)
        s, warns = S.validate({"version": 1, "notifications": {"mutedApps": "Slack"}})
        self.assertEqual((s["notifications"]["mutedApps"], len(warns)), ([], 1))

    def test_muted_apps_cli_text(self):
        out = S.set_value(S.validate({"version": 1})[0], "notifications.mutedApps", "Slack,Spotify")
        self.assertEqual(out["notifications"]["mutedApps"], ["Slack", "Spotify"])
        out = S.set_value(out, "notifications.mutedApps", "")
        self.assertEqual(out["notifications"]["mutedApps"], [])
        with self.assertRaises(ValueError):
            S.set_value(out, "notifications.mutedApps", "Slack,Slack")

    def test_reset_knows_the_section(self):
        self.assertIn("notifications", cli.SECTIONS)
        self.assertIn("idle", cli.SECTIONS)


if __name__ == "__main__":
    unittest.main()
