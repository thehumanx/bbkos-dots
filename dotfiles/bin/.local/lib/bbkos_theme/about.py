"""About this computer (the settings page "About and updates", docs/modules/about.md): read-only facts, as JSON.

    bbkos-about            JSON: {"rows": [[label, value], ...], "update": {"last": "...", "kernel": "..."}}
"""
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

TIMEOUT = 4


def _read(path, default=""):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return default


def _run(cmd, env):
    try:
        res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL)
        return res.stdout.strip() if res.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def os_name(root="/etc/os-release"):
    for line in _read(root).splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip('"')
    return "Linux"


def cpu_model(root="/proc/cpuinfo"):
    for line in _read(root).splitlines():
        if line.startswith("model name"):
            return " ".join(line.split(":", 1)[1].split())
    return ""


def memory_gib(root="/proc/meminfo"):
    for line in _read(root).splitlines():
        if line.startswith("MemTotal:"):
            return round(int(line.split()[1]) / 1048576, 1)
    return 0.0


def uptime_text(seconds):
    d, rem = divmod(int(seconds), 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    return " ".join(p for p in (f"{d} d" if d else "", f"{h} h" if h else "", f"{m} min") if p)


def battery(root="/sys/class/power_supply"):
    """('NN % of its design capacity', 'N cycles') of the first battery, or ('', '')."""
    for bat in sorted(Path(root).glob("BAT*")):
        full, design = _read(bat / "energy_full"), _read(bat / "energy_full_design")
        if not full.isdigit() or not design.isdigit() or int(design) == 0:
            full, design = _read(bat / "charge_full"), _read(bat / "charge_full_design")
        health = f"{round(100 * int(full) / int(design))} % of its design capacity" if full.isdigit() and design.isdigit() and int(design) else ""
        cycles = _read(bat / "cycle_count")
        return health, (f"{cycles} cycles" if cycles.isdigit() else "")
    return "", ""


def last_update(log="/var/log/pacman.log"):
    """When the last pacman transaction started, as 'YYYY-MM-DD HH:MM', or ''."""
    last = ""
    try:
        with open(log, encoding="utf-8", errors="replace") as f:
            for line in f:
                if "[ALPM] transaction started" in line:
                    last = line[1:17]
    except OSError:
        return ""
    return last.replace("T", " ")


def bbkos_version(repo, env):
    if not (Path(repo) / ".git").exists():
        return ""
    return _run(["git", "-C", str(repo), "log", "-1", "--format=%h, %cs"], env)


def rows(env):
    home = Path(env.get("HOME", "~")).expanduser()
    uname = platform.uname()
    bat_health, bat_cycles = battery()
    disk = shutil.disk_usage("/")
    hypr = _run(["hyprctl", "version", "-j"], env)
    try:
        hypr = json.loads(hypr).get("tag", "") if hypr else ""
    except ValueError:
        hypr = ""
    qs = _run(["quickshell", "--version"], env).split()
    qs = qs[1] if len(qs) > 1 else ""                       # "Quickshell 0.3.2 (revision ...)"
    try:
        up = uptime_text(float(_read("/proc/uptime", "0").split()[0]))
    except (ValueError, IndexError):
        up = ""
    out = [
        ("Computer", " ".join(x for x in (_read("/sys/class/dmi/id/sys_vendor"), _read("/sys/class/dmi/id/product_version")) if x)),
        ("Model code", _read("/sys/class/dmi/id/product_name")),
        ("Firmware", _read("/sys/class/dmi/id/bios_version")),
        ("Processor", cpu_model()),
        ("Memory", f"{memory_gib()} GiB"),
        ("Disk", f"{disk.used / 2**30:.0f} of {disk.total / 2**30:.0f} GiB used"),
        ("Battery health", ", ".join(x for x in (bat_health, bat_cycles) if x)),
        ("System", os_name()),
        ("Kernel", uname.release),
        ("Hyprland", hypr),
        ("Quickshell", qs),
        ("bbkOS", bbkos_version(home / "bbkOS", env)),
        ("Up for", up),
    ]
    return [[k, v] for k, v in out if v]


def status(env):
    return {"rows": rows(env), "update": {"last": last_update()}}


def main(argv, env=None):
    env = dict(os.environ if env is None else env)
    if argv:
        print("usage: bbkos-about", file=sys.stderr)
        return 2
    print(json.dumps(status(env)))
    return 0
