"""Fake adb and scrcpy for the android tests: no test reaches a real phone.

FakeBin(tmp) writes executable `adb` and `scrcpy` scripts into tmp/bin. Each run appends its argv (one JSON list per
line) to tmp/calls.log, then answers with the first rule whose words all appear in the argv, in order of `rules`.
A rule is (words, stdout, returncode, sleep_seconds); stdout starting with "@" names a file in fixtures/.
"""
import json
import os
import stat
import sys
from pathlib import Path

FIX = Path(__file__).resolve().parent / "fixtures"

SCRIPT = """#!{python}
import json, sys, time
from pathlib import Path
here = Path({tmp!r})
argv = [{name!r}] + sys.argv[1:]
words_of = argv[3:] if argv[1:2] == ["-s"] else argv[1:]     # "-s SERIAL" is not pm's -s
with open(here / "calls.log", "a") as f:
    f.write(json.dumps(argv) + "\\n")
for words, out, rc, sleep in json.loads((here / "rules.json").read_text()):
    if words[0] == argv[0] and all(w in words_of for w in words[1:]):
        time.sleep(sleep)
        if out.startswith("@"):
            out = Path({fix!r}, out[1:]).read_text()
        sys.stdout.write(out)
        sys.exit(rc)
sys.stderr.write("fake: no rule for " + " ".join(argv) + "\\n")
sys.exit(1)
"""

# The phone of the recordings, alone, over USB-less Wi-Fi with one serial.
ONE_DEVICE = "List of devices attached\n192.168.1.31:45833     device product:V2503i model:V2503 device:V2503 transport_id:7\n\n"
SERIAL = "192.168.1.31:45833"


def default_rules(devices=ONE_DEVICE):
    return [
        (["adb", "devices"], devices, 0, 0),
        (["adb", "start-server"], "", 0, 0),
        (["adb", "getprop"], "@getprop.txt", 0, 0),
        (["adb", "dumpsys", "package"], "@dumpsys_compass.txt", 0, 0),        # a factory copy in /system: restorable
        (["adb", "list", "packages", "-u", "-s"], "@pm_system.txt", 0, 0),
        (["adb", "list", "packages", "-u", "-3"], "@pm_third.txt", 0, 0),
        (["adb", "list", "packages", "-u"], "@pm_all.txt", 0, 0),
        (["adb", "list", "packages", "-d"], "@pm_disabled.txt", 0, 0),
        (["adb", "list", "packages"], "@pm_installed.txt", 0, 0),
        (["scrcpy", "--list-apps"], "@scrcpy_apps.txt", 0, 0),
    ]


class FakeBin:
    def __init__(self, tmp, rules=None):
        self.tmp = Path(tmp)
        self.bin = self.tmp / "bin"
        self.bin.mkdir(parents=True, exist_ok=True)
        for name in ("adb", "scrcpy"):
            p = self.bin / name
            p.write_text(SCRIPT.format(python=sys.executable, tmp=str(self.tmp), name=name, fix=str(FIX)))
            p.chmod(p.stat().st_mode | stat.S_IXUSR)
        self.set_rules(rules if rules is not None else default_rules())

    def set_rules(self, rules):
        (self.tmp / "rules.json").write_text(json.dumps([list(r) for r in rules]))

    def prepend(self, *rules):
        cur = json.loads((self.tmp / "rules.json").read_text())
        self.set_rules([list(r) for r in rules] + cur)

    def calls(self):
        log = self.tmp / "calls.log"
        return [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []

    def env(self):
        home = self.tmp / "home"
        home.mkdir(exist_ok=True)
        return {"PATH": f"{self.bin}{os.pathsep}/usr/bin", "HOME": str(home),
                "XDG_CACHE_HOME": str(home / ".cache"), "XDG_STATE_HOME": str(home / ".local/state")}
