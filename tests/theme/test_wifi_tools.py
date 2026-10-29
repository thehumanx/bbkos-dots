"""bbkos-wifi-qr and bbkos-speedtest against fake nmcli, qrencode, curl and ip (no network, no secrets)."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parents[2] / "dotfiles/bin/.local/bin"


def fake(dirpath, name, body):
    p = Path(dirpath, name)
    p.write_text("#!/usr/bin/env bash\n" + body)
    p.chmod(0o755)


class WifiQrTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        self.fields = ["Café;Net", "wpa-psk", 'pa:ss,w"d', "no", ""]

    def run_qr(self, *args, qrencode=True):
        lines = "\n".join(self.fields)
        fake(self.d, "nmcli", f"""
case "$*" in
  *"device status"*) echo "wlan0:wifi:connected" ;;
  *"device show"*) echo "uuid-1" ;;
  *"connection show uuid uuid-1"*) printf '%s\\n' {' '.join(repr(f) if f else "''" for f in self.fields)} ;;
esac
""")
        if qrencode:
            # Records what arrives on stdin and its own argv, prints a 2x2 module pattern in ASCII (2 chars per module).
            fake(self.d, "qrencode", f'cat > {self.d}/stdin; echo "$*" > {self.d}/argv; printf "##  \\n  ##\\n"\n')
        env = dict(os.environ, PATH=f"{self.d}:/usr/bin:/bin")
        return subprocess.run([str(BIN / "bbkos-wifi-qr"), *args], env=env, capture_output=True, text=True, timeout=10)

    def test_payload_is_escaped_and_piped_not_an_argument(self):
        r = self.run_qr()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.d / "stdin").read_text(), r'WIFI:T:WPA;S:Café\;Net;P:pa\:ss\,w\"d;;')
        self.assertNotIn("pa", (self.d / "argv").read_text())          # the password is never on a command line
        out = r.stdout.splitlines()
        self.assertEqual(out[0], "meta\tWPA\tCafé;Net")
        self.assertEqual(out[1:], ["10", "01"])

    def test_open_network_has_no_password_field(self):
        self.fields = ["Open", "", "", "yes", ""]
        r = self.run_qr()
        self.assertEqual((self.d / "stdin").read_text(), "WIFI:T:nopass;S:Open;H:true;;")

    def test_enterprise_is_refused(self):
        self.fields = ["Work", "wpa-eap", "", "no", ""]
        r = self.run_qr()
        self.assertEqual(r.returncode, 1)
        self.assertIn("Enterprise", r.stderr)

    def test_missing_qrencode_says_how_to_install(self):
        r = self.run_qr(qrencode=False)
        if Path("/usr/bin/qrencode").exists():
            self.skipTest("qrencode is installed system-wide")
        self.assertEqual(r.returncode, 3)
        self.assertIn("pacman -S qrencode", r.stderr)

    def test_password_mode_prints_only_the_password(self):
        r = self.run_qr("--password")
        self.assertEqual(r.stdout, 'pa:ss,w"d\n')


class SpeedtestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        fake(self.d, "curl", 'case "$*" in *time_connect*) echo 0.0${RANDOM:0:1}5 ;; *) exec sleep 30 ;; esac\n')

    def run_st(self, *args):
        env = dict(os.environ, PATH=f"{self.d}:/usr/bin:/bin", BBKOS_SPEEDTEST_SECONDS="2")
        return subprocess.run([str(BIN / "bbkos-speedtest"), *args], env=env, capture_output=True, text=True, timeout=20)

    def test_ping_prints_a_whole_number_of_ms(self):
        r = self.run_st("ping")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout.strip(), r"^\d+$")

    def test_down_prints_one_rate_a_second_and_leaves_no_workers(self):
        r = self.run_st("down")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(r.stdout.splitlines()), 2)
        for line in r.stdout.splitlines():
            float(line)
        left = subprocess.run(["pgrep", "-f", f"{self.d}/curl"], capture_output=True, text=True).stdout
        self.assertEqual(left, "")

    def test_usage(self):
        self.assertEqual(self.run_st("sideways").returncode, 2)


if __name__ == "__main__":
    unittest.main()
