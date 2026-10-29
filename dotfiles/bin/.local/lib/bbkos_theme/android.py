"""bbkos-android: disable, remove and restore apps on an Android phone over adb (docs/modules/android.md).

Follows UAD-ng (Universal Android Debloater, next generation): its package list gives each package a safety rating, and
its commands are used for user 0 only. App names come from `scrcpy --list-apps`. Output is JSON for the window in
modules/android/.
"""
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

LIST_URL = ("https://raw.githubusercontent.com/Universal-Debloater-Alliance/universal-android-debloater/main/"
            "resources/assets/uad_lists.json")
RATINGS = ("Recommended", "Advanced", "Expert", "Unsafe")
QUICK = 5          # seconds: one pm call, getprop, adb devices
SLOW = 60          # seconds: pm list packages, scrcpy --list-apps
NET = 30           # seconds: adb pair / connect
FETCH = 20         # seconds: the list download
PKG_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+")


# ---------------------------------------------------------------- parsers

def valid_package(name):
    return isinstance(name, str) and PKG_RE.fullmatch(name) is not None


def parse_devices(text):
    """`adb devices -l` -> [{serial, state, model, transport}]; Wi-Fi serials are host:port or an mDNS name."""
    devs = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2 or line.startswith("List of devices") or line.startswith("*"):
            continue
        serial, state = parts[0], parts[1]
        fields = dict(p.split(":", 1) for p in parts[2:] if ":" in p)
        wifi = ":" in serial or "._adb-tls-connect." in serial
        devs.append({"serial": serial, "state": state, "model": fields.get("model", ""),
                     "transport": "wifi" if wifi else "usb"})
    return devs


def parse_packages(text):
    """`pm list packages` -> set of package names."""
    return {line.strip()[len("package:"):] for line in text.splitlines() if line.strip().startswith("package:")}


def parse_scrcpy_apps(text):
    """`scrcpy --list-apps` -> {package: {name, system}}. App lines are ' * NAME  PACKAGE' (system) or ' - NAME  PACKAGE';
    the name is padded to a column and may hold spaces, so the package is the last word. Log lines are skipped."""
    apps = {}
    for line in text.splitlines():
        if line[:3] not in (" * ", " - "):
            continue
        name, _, pkg = line[3:].rstrip().rpartition(" ")
        if valid_package(pkg):
            apps[pkg] = {"name": name.strip(), "system": line[1] == "*"}
    return apps


def code_paths(text):
    """`dumpsys package P` -> every codePath, the installed one and a hidden factory copy of an updated system app."""
    return re.findall(r"^\s*codePath=(\S+)", text, re.M)


def has_factory_copy(text):
    """A copy outside /data survives `pm uninstall --user 0`, so install-existing can bring the app back. Not the
    SYSTEM flag: vivo installs its /system/custom preloads into /data with that flag, and removing one deleted it
    (vivo Feedback, 2026-10-28)."""
    return any(not p.startswith("/data/") for p in code_paths(text))


def parse_getprop(text):
    """`getprop` -> {key: value} from '[key]: [value]' lines."""
    props = {}
    for m in re.finditer(r"^\[([^\]]+)\]: \[(.*)\]$", text, re.M):
        props[m.group(1)] = m.group(2)
    return props


# ---------------------------------------------------------------- running and paths

class AndroidError(Exception):
    """A problem the window shows as is: no phone, phone not authorised, several phones and no --serial."""


class UsageError(Exception):
    """Wrong arguments: the usage text on stderr, exit 2."""


class InputError(Exception):
    """A bad address or pairing code typed in the window; exit 1 with {ok: false, message}."""


def run(cmd, timeout=QUICK, env=None):
    """subprocess.run with output as text; a hang gives returncode 124 and stderr "timed out" (like record.run_quick),
    a missing program 127 (scrcpy is optional: without it the names are empty)."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "timed out")
    except OSError as e:
        return subprocess.CompletedProcess(cmd, 127, "", f"{cmd[0]}: not found ({e.strerror})")


def _xdg(env, var, fallback):
    return Path(env.get(var) or Path(env.get("HOME", str(Path.home()))) / fallback)


def cache_path(env):
    return _xdg(env, "XDG_CACHE_HOME", ".cache") / "bbkos/android/uad_lists.json"


def history_path(env):
    return _xdg(env, "XDG_STATE_HOME", ".local/state") / "bbkos/android/history.jsonl"


def adb_path(env):
    return shutil.which("adb", path=env.get("PATH"))


def _adb(env, serial, *args, timeout=QUICK):
    return run(["adb", "-s", serial, *args], timeout=timeout, env=env)


# ---------------------------------------------------------------- the UAD list

def _fetch(url, timeout):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def _check_list(data):
    """The parsed list, or ValueError: a map of package -> entry with a removal field (an HTML page is not)."""
    d = json.loads(data)
    if not isinstance(d, dict) or not d or not all(isinstance(v, dict) and "removal" in v for v in d.values()):
        raise ValueError("the downloaded safety list is not in the expected format")
    return d


def update_list(env, fetch=None):
    """Download the UAD list into the cache; "" on success, else the error. A bad download never replaces the cache."""
    try:
        data = (fetch or _fetch)(LIST_URL, FETCH)
        _check_list(data)
        dest = cache_path(env)
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=".uad_lists.", suffix=".tmp")
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, dest)
        return ""
    except (OSError, ValueError, http.client.HTTPException) as e:          # IncompleteRead: a cut download
        return f"Safety list unavailable: {e}"


def load_uad(env, fetch=None):
    """(list, error): the cached list, downloaded first when there is no cache."""
    err = ""
    if not cache_path(env).exists():
        err = update_list(env, fetch)
    try:
        return _check_list(cache_path(env).read_bytes()), ""
    except (OSError, ValueError) as e:
        return {}, err or f"Safety list unavailable: {e}"


def _list_age(env):
    try:
        return int(time.time() - cache_path(env).stat().st_mtime)
    except OSError:
        return None


# ---------------------------------------------------------------- devices and packages

def devices(env):
    """The attached phones; authorised ones also get brand, Android version and SDK."""
    devs = parse_devices(run(["adb", "devices", "-l"], env=env).stdout)
    for d in devs:
        if d["state"] == "device":
            props = parse_getprop(_adb(env, d["serial"], "shell", "getprop").stdout)
            d["brand"] = props.get("ro.product.brand", "")
            d["android"] = props.get("ro.build.version.release", "")
            d["sdk"] = int(props.get("ro.build.version.sdk", "")) if props.get("ro.build.version.sdk", "").isdigit() else 0
            d["model"] = d["model"] or props.get("ro.product.model", "")
    return devs


def pick_device(devs, serial):
    """The device to act on, or AndroidError with what to do about it."""
    if serial:
        for d in devs:
            if d["serial"] == serial:
                break
        else:
            raise AndroidError(f"Phone not connected: {serial}")
    else:
        if not devs:
            raise AndroidError("No phone connected: turn on USB debugging and plug the phone in, or connect over Wi-Fi")
        ready = [d for d in devs if d["state"] == "device"]
        if len(ready) > 1:
            raise AndroidError("More than one phone connected: pick one (--serial)")
        d = ready[0] if ready else devs[0]
    if d["state"] == "unauthorized":
        raise AndroidError("Accept the USB debugging prompt on the phone")
    if d["state"] != "device":
        raise AndroidError("Phone offline: replug it or connect again")
    return d


def _pm_list(env, serial, *flags):
    r = _adb(env, serial, "shell", "pm", "list", "packages", *flags, "--user", "0", timeout=SLOW)
    if r.returncode != 0:
        raise AndroidError("Could not list the apps: " + (r.stderr.strip() or r.stdout.strip() or "adb failed"))
    return parse_packages(r.stdout)


def list_packages(env, serial=None, fetch=None):
    """Every package of user 0 with its state, name and safety rating (see the spec for the fields)."""
    dev = pick_device(devices(env), serial)
    s = dev["serial"]
    every = _pm_list(env, s, "-u")
    present = _pm_list(env, s)
    disabled = _pm_list(env, s, "-d")
    system = _pm_list(env, s, "-u", "-s")
    names = parse_scrcpy_apps(run(["scrcpy", "--serial", s, "--list-apps"], timeout=SLOW, env=env).stdout)
    uad, list_error = load_uad(env, fetch)
    rows = []
    for pkg in sorted(every):
        entry = uad.get(pkg) or {}
        rating = entry.get("removal")
        rows.append({
            "package": pkg,
            "name": names.get(pkg, {}).get("name", ""),
            "state": "removed" if pkg not in present else "disabled" if pkg in disabled else "installed",
            "system": pkg in system,
            "rating": rating if rating in RATINGS else "Unlisted",
            "list": entry.get("list", ""),
            "description": entry.get("description", "").strip(),
            "neededBy": entry.get("neededBy", []),
        })
    return {"serial": s, "model": dev["model"], "packages": rows, "listError": list_error, "listAge": _list_age(env)}


# ---------------------------------------------------------------- actions

ACTIONS = {"disable": ["pm", "disable-user"], "enable": ["pm", "enable"],
           "remove": ["pm", "uninstall"], "restore": ["cmd", "package", "install-existing"]}
NEED_FORCE = ("disable", "remove")          # Unsafe packages: refused for these without --force


def _succeeded(action, pkg, out):
    """pm's answer means done: "Success" (uninstall), "Package P new state: disabled-user" / "enabled",
    "Package P installed for user: 0" (install-existing)."""
    if action == "remove":
        return out.strip() == "Success"
    if action == "restore":
        return f"Package {pkg} installed for user: 0" in out
    want = "disabled-user" if action == "disable" else "enabled"
    return f"Package {pkg} new state: {want}" in out


def _record(env, dev, result):
    path = history_path(env)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = {"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "serial": dev["serial"], "model": dev["model"], **result}
    with open(path, "a") as f:
        f.write(json.dumps(line) + "\n")


def act(action, packages, env, serial=None, force=False):
    """Run one of ACTIONS on each package of user 0; one result per package, each also written to the history."""
    dev = pick_device(devices(env), serial)
    on_phone = _pm_list(env, dev["serial"], "-u")
    uad, _ = load_uad(env, fetch=lambda url, timeout: b"")   # never download in the middle of an action
    results = []
    for pkg in packages:
        error = ""
        if not valid_package(pkg):
            error = "invalid package name"
        elif pkg not in on_phone:
            error = "not on this phone"
        elif action in NEED_FORCE and not force and not uad:
            error = "no safety list: refused without --force"
        elif action in NEED_FORCE and not force and (uad.get(pkg) or {}).get("removal") == "Unsafe":
            error = "rated Unsafe: refused without --force"
        elif action == "remove" and not force and not has_factory_copy(
                _adb(env, dev["serial"], "shell", "dumpsys", "package", pkg, timeout=QUICK).stdout):
            error = "no factory copy on the phone: removing would delete it for good (use Disable, or --force)"
        else:
            r = _adb(env, dev["serial"], "shell", *ACTIONS[action], "--user", "0", pkg, timeout=QUICK)
            out = (r.stdout + r.stderr).strip()
            if r.returncode == 124:
                error = "timed out"
            elif r.returncode != 0 or not _succeeded(action, pkg, r.stdout):
                error = out or f"adb exited with {r.returncode}"
        result = {"package": pkg, "action": action, "ok": not error, "error": error}
        _record(env, dev, result)
        results.append(result)
    return {"serial": dev["serial"], "results": results}


# ---------------------------------------------------------------- Wi-Fi debugging

ADDR_RE = re.compile(r"(\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9][A-Za-z0-9.-]*):([0-9]{1,5})")


def valid_address(addr):
    m = ADDR_RE.fullmatch(addr or "")
    return bool(m) and 1 <= int(m.group(2)) <= 65535


def wifi(cmd, args, env):
    """adb pair HOST:PORT CODE / connect HOST:PORT / disconnect [HOST:PORT] -> {ok, message} (adb's own text)."""
    if any(not valid_address(a) for a in args[:1]):
        raise InputError("Address must look like 192.168.1.5:37000")
    if cmd == "pair" and not re.fullmatch(r"[0-9]{6}", args[1]):
        raise InputError("The pairing code has 6 digits")
    r = run(["adb", cmd, *args], timeout=NET, env=env)
    message = (r.stdout + r.stderr).strip() or ("timed out" if r.returncode == 124 else "")
    first = message.splitlines()[0] if message else ""
    if cmd == "pair":
        ok = r.returncode == 0 and first.startswith("Successfully paired")
    elif cmd == "connect":
        ok = r.returncode == 0 and (first.startswith("connected to") or first.startswith("already connected to"))
    else:
        ok = r.returncode == 0
    return {"ok": ok, "message": message}


# ---------------------------------------------------------------- command line

USAGE = ("usage: bbkos-android status | list [--serial S] | update-list\n"
         "       disable|enable|remove|restore PKG... [--serial S] [--force]\n"
         "       pair HOST:PORT CODE | connect HOST:PORT | disconnect [HOST:PORT]")


def _status(env):
    if not adb_path(env):
        return {"adb": False, "devices": [], "error": "adb not found (install android-tools)"}
    return {"adb": True, "devices": devices(env)}


def _take(args, flag, value=True):
    """Remove --flag (and its value) from args; returns the value, True, or None."""
    if flag not in args:
        return None
    i = args.index(flag)
    if not value:
        del args[i]
        return True
    if i + 1 >= len(args):
        raise UsageError(f"{flag} needs a value")
    v = args[i + 1]
    del args[i:i + 2]
    return v


def main(argv, env=None):
    env = dict(os.environ if env is None else env)
    args = list(argv)
    try:
        serial = _take(args, "--serial")
        if args == ["status"]:
            out = _status(env)
        elif args == ["list"]:
            out = list_packages(env, serial)
        elif args and args[0] in ACTIONS:
            force = _take(args, "--force", value=False) or False
            if len(args) < 2:
                raise UsageError("no packages")
            out = act(args[0], args[1:], env, serial, force)
        elif len(args) == 3 and args[0] == "pair" or len(args) == 2 and args[0] == "connect" \
                or args[:1] == ["disconnect"] and len(args) <= 2:
            out = wifi(args[0], args[1:], env)
        elif args == ["update-list"]:
            err = update_list(env)
            out = {"ok": not err, "error": err}
        else:
            raise UsageError("unknown command")
    except UsageError:
        print(USAGE, file=sys.stderr)
        return 2
    except AndroidError as e:
        print(json.dumps({"error": str(e)}))
        return 1
    except InputError as e:
        print(json.dumps({"ok": False, "message": str(e)}))
        return 1
    print(json.dumps(out))
    return 0
