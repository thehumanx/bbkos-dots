"""bbkos-about (read-only facts) and bbkos-network (saved connections, Wi-Fi, Tailscale, the mirror). Fake nmcli, tailscale
and bbkos-mirror in PATH answer and record, so no real connection is ever changed."""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dotfiles/bin/.local/lib"))
from bbkos_theme import about as A, network as N  # noqa: E402


class AboutTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def test_os_cpu_memory(self):
        (self.dir / "os-release").write_text('NAME="Arch Linux"\nPRETTY_NAME="Arch Linux"\n')
        (self.dir / "cpuinfo").write_text("processor\t: 0\nmodel name\t: Intel(R)   Core(TM) Ultra 7\n")
        (self.dir / "meminfo").write_text("MemTotal:       32314368 kB\n")
        self.assertEqual(A.os_name(self.dir / "os-release"), "Arch Linux")
        self.assertEqual(A.cpu_model(self.dir / "cpuinfo"), "Intel(R) Core(TM) Ultra 7")
        self.assertEqual(A.memory_gib(self.dir / "meminfo"), 30.8)
        self.assertEqual((A.os_name(self.dir / "none"), A.cpu_model(self.dir / "none"), A.memory_gib(self.dir / "none")),
                         ("Linux", "", 0.0))

    def test_uptime_text(self):
        self.assertEqual(A.uptime_text(59), "0 min")
        self.assertEqual(A.uptime_text(3600 * 5 + 60 * 32), "5 h 32 min")
        self.assertEqual(A.uptime_text(86400 * 2 + 3600), "2 d 1 h 0 min")

    def test_battery_health_and_cycles(self):
        bat = self.dir / "BAT0"
        bat.mkdir()
        (bat / "energy_full").write_text("43000000\n")
        (bat / "energy_full_design").write_text("50000000\n")
        (bat / "cycle_count").write_text("504\n")
        self.assertEqual(A.battery(self.dir), ("86 % of its design capacity", "504 cycles"))
        self.assertEqual(A.battery(self.dir / "empty"), ("", ""))

    def test_last_update_is_the_last_transaction(self):
        log = self.dir / "pacman.log"
        log.write_text("[2026-10-23T21:00:01+0545] [ALPM] transaction started\n[2026-10-24T07:48:55+0545] [ALPM] transaction started\n"
                       "[2026-10-24T07:49:00+0545] [ALPM] transaction completed\n")
        self.assertEqual(A.last_update(log), "2026-10-24 07:48")
        self.assertEqual(A.last_update(self.dir / "none"), "")

    def test_status_shape_and_usage(self):
        env = {"HOME": str(self.dir), "PATH": "/usr/bin:/bin"}
        st = A.status(env)
        self.assertTrue(all(len(r) == 2 and r[1] for r in st["rows"]))
        self.assertIn("Kernel", [r[0] for r in st["rows"]])
        self.assertEqual(A.main(["x"], env), 2)


class NetworkTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.log = self.dir / "calls.log"
        bin_ = self.dir / "bin"
        bin_.mkdir()
        nm = bin_ / "nmcli"
        nm.write_text(f'''#!/bin/sh
echo "nmcli $*" >> {self.log}
case "$*" in
  "radio wifi") echo enabled;;
  "-t -f NAME connection show --active") printf 'Home Wi-Fi\\nlo\\n';;
  "-t -f NAME,TYPE,AUTOCONNECT connection show")
    printf 'Home Wi-Fi:802-11-wireless:yes\\nCafe\\\\: free:802-11-wireless:no\\nlo:loopback:yes\\ntailscale0:tun:yes\\nWork:vpn:no\\n';;
esac
[ -n "$FAKE_FAIL" ] && {{ echo "$FAKE_FAIL" >&2; exit 4; }}
exit 0
''')
        nm.chmod(0o755)
        ts = bin_ / "tailscale"
        ts.write_text(f'''#!/bin/sh
case "$*" in
  "status --json") echo '{{"BackendState":"Running","Self":{{"TailscaleIPs":["100.1.2.3","fd7a::1"]}},"Peer":{{"a":{{}},"b":{{}}}}}}';;
  "debug prefs") echo '{{"WantRunning":true,"OperatorUser":"'"$FAKE_OPERATOR"'"}}';;
  *) echo "tailscale $*" >> {self.log}
     [ -n "$FAKE_TS_FAIL" ] && {{ printf '%s\\n\\nUse sudo.\\n' "$FAKE_TS_FAIL" >&2; exit 1; }};;
esac
exit 0
''')
        ts.chmod(0o755)
        mi = bin_ / "bbkos-mirror"
        mi.write_text('#!/bin/sh\ncase "$1" in status) echo off;; address) echo 100.1.2.3:5900;; esac\n')
        mi.chmod(0o755)
        self.env = {"PATH": f"{bin_}:/usr/bin:/bin"}

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_terse_split_handles_escaped_colons(self):
        self.assertEqual(N.split_terse(r"Cafe\: free:802-11-wireless:no"), ["Cafe: free", "802-11-wireless", "no"])
        self.assertEqual(N.split_terse(r"a\\b:c"), ["a\\b", "c"])

    def test_status(self):
        st = N.status(self.env)
        self.assertTrue(st["wifi"])
        self.assertEqual([(c["name"], c["kind"], c["autoconnect"], c["active"]) for c in st["connections"]],
                         [("Home Wi-Fi", "wifi", True, True), ("Work", "vpn", False, False), ("Cafe: free", "wifi", False, False)])
        self.assertEqual(st["tailscale"], {"state": "Running", "address": "100.1.2.3", "peers": 2, "operator": False})
        me = __import__("getpass").getuser()
        self.assertTrue(N.status({**self.env, "FAKE_OPERATOR": me})["tailscale"]["operator"])
        self.assertEqual(st["mirror"], {"state": "off", "address": "100.1.2.3:5900"})

    def test_commands(self):
        self.assertEqual(N.main(["wifi", "off"], self.env), 0)
        self.assertEqual(N.main(["forget", "Cafe: free"], self.env), 0)
        self.assertEqual(N.main(["autoconnect", "Work", "yes"], self.env), 0)
        self.assertEqual(self.calls(), ["nmcli radio wifi off", "nmcli connection delete id Cafe: free",
                                        "nmcli connection modify id Work connection.autoconnect yes"])

    def test_tailscale_on_and_off(self):
        self.assertEqual(N.main(["tailscale", "off"], self.env), 0)
        self.assertEqual(N.main(["tailscale", "on"], self.env), 0)
        self.assertEqual(self.calls(), ["tailscale down", "tailscale up"])

    def test_tailscale_without_operator_rights_says_how_to_get_them(self):
        err = io.StringIO()
        from contextlib import redirect_stderr
        with redirect_stderr(err):
            self.assertEqual(N.main(["tailscale", "off"], {**self.env, "FAKE_TS_FAIL": "Access denied: prefs write access denied"}), 1)
            self.assertEqual(N.main(["tailscale", "on"], {**self.env, "FAKE_TS_FAIL": "backend error: timeout"}), 1)
        self.assertEqual(err.getvalue().splitlines(), [N.OPERATOR_HINT, "backend error: timeout"])

    def test_bad_input_is_refused_without_calling_nmcli(self):
        for argv in (["forget", "--help"], ["forget", ""], ["forget", "a\nb"], ["wifi", "maybe"], ["autoconnect", "x", "perhaps"],
                     ["tailscale", "maybe"], ["tailscale"], ["bogus"]):
            self.assertGreater(N.main(argv, self.env), 0, argv)
        self.assertEqual(self.calls(), [])

    def test_a_failing_nmcli_reports_its_first_line(self):
        err = io.StringIO()
        from contextlib import redirect_stderr
        with redirect_stderr(err):
            self.assertEqual(N.main(["forget", "Work"], {**self.env, "FAKE_FAIL": "Error: not authorized\nsecond"}), 1)
        self.assertEqual(err.getvalue().strip(), "Error: not authorized")

    def test_status_prints_json(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(N.main(["status"], self.env), 0)
        self.assertTrue(json.loads(buf.getvalue())["wifi"])


if __name__ == "__main__":
    unittest.main()
