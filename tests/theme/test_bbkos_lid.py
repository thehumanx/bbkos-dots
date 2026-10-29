"""bbkos-lid check: when the lid is closed and no external screen is left, it does what logind would have done (the Lid and
power page's choice for the power source). Dry run: BBKOS_DRY_RUN prints the actions instead of doing them."""
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "dotfiles/bin/.local/bin/bbkos-lid"


class LidCheckTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.conf = Path(tmp.name) / "bbkos.conf"

    def check(self, ac, battery_action=None, power_action=None, lid="closed", external="0"):
        if battery_action:
            self.conf.write_text(f"[Login]\nHandleLidSwitch={battery_action}\nHandleLidSwitchExternalPower={power_action}\n")
        env = {"PATH": "/usr/bin:/bin", "BBKOS_DRY_RUN": "1", "BBKOS_LID_STATE": lid, "BBKOS_EXTERNAL_COUNT": external,
               "BBKOS_LOGIND_CONF": str(self.conf), "BBKOS_ON_AC": ac}
        r = subprocess.run([str(SCRIPT), "check"], env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def test_without_the_file_it_suspends_then_hibernates_as_before(self):
        self.assertEqual(self.check("0"), "DRY: systemctl suspend-then-hibernate")

    def test_it_follows_the_choice_for_the_power_source(self):
        self.assertEqual(self.check("0", "hibernate", "ignore"), "DRY: systemctl hibernate")
        self.assertEqual(self.check("1", "hibernate", "ignore"), "lid action is ignore: nothing to do")
        self.assertEqual(self.check("1", "hibernate", "suspend"), "DRY: systemctl suspend")

    def test_lock_only_locks(self):
        self.assertEqual(self.check("0", "lock", "lock"), "DRY: loginctl lock-session")

    def test_nothing_when_the_lid_is_open_or_a_screen_remains(self):
        self.assertEqual(self.check("0", lid="open"), "nothing to do")
        self.assertEqual(self.check("0", external="1"), "nothing to do")


if __name__ == "__main__":
    unittest.main()
