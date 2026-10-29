"""Network page (docs/modules/network.md): Wi-Fi on or off, the saved connections, Tailscale and the phone mirror, as JSON.
The popups in the bar are the quick version; this is where a saved network is forgotten.

    bbkos-network status | wifi on|off | forget NAME | autoconnect NAME yes|no | tailscale on|off

Tailscale on and off are `tailscale up` and `tailscale down`. tailscaled keeps the choice across reboots, so off stays off at
the next boot. Both need the CLI's operator rights for this user, given once by the owner with
`sudo tailscale set --operator=$USER`; without them the page shows that command instead of tailscale's own message.
"""
import getpass
import json
import os
import re
import subprocess
import sys

TIMEOUT = 8
SHOWN = {"802-11-wireless": "wifi", "802-3-ethernet": "ethernet", "vpn": "vpn", "wireguard": "vpn", "bluetooth": "bluetooth"}


def _run(cmd, env, check=False):
    try:
        res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as e:
        if check:
            raise ValueError(f"{cmd[0]}: {e}")
        return ""
    if res.returncode != 0:
        if check:
            raise ValueError((res.stderr or res.stdout).strip().splitlines()[0] if (res.stderr or res.stdout).strip() else f"{cmd[0]} failed")
        return ""
    return res.stdout


def split_terse(line):
    """The fields of one `nmcli -t` line: ':' separates, '\\:' and '\\\\' are literal."""
    out, cur, i = [], "", 0
    while i < len(line):
        c = line[i]
        if c == "\\" and i + 1 < len(line):
            cur += line[i + 1]
            i += 2
            continue
        if c == ":":
            out.append(cur)
            cur = ""
        else:
            cur += c
        i += 1
    out.append(cur)
    return out


def connections(env):
    active = {split_terse(l)[0] for l in _run(["nmcli", "-t", "-f", "NAME", "connection", "show", "--active"], env).splitlines() if l}
    out = []
    for line in _run(["nmcli", "-t", "-f", "NAME,TYPE,AUTOCONNECT", "connection", "show"], env).splitlines():
        f = split_terse(line)
        if len(f) == 3 and f[1] in SHOWN:
            out.append({"name": f[0], "kind": SHOWN[f[1]], "autoconnect": f[2] == "yes", "active": f[0] in active})
    out.sort(key=lambda c: (not c["active"], c["kind"], c["name"].lower()))
    return out


def tailscale(env):
    raw = _run(["tailscale", "status", "--json"], env)
    if not raw:
        return None
    try:
        d = json.loads(raw)
    except ValueError:
        return None
    ips = (d.get("Self") or {}).get("TailscaleIPs") or []
    return {"state": d.get("BackendState", ""), "address": next((i for i in ips if "." in i), ""),
            "peers": len(d.get("Peer") or {}), "operator": is_operator(env)}


def is_operator(env):
    """Whether this user may switch Tailscale on and off (the prefs' OperatorUser), read without root."""
    try:
        return json.loads(_run(["tailscale", "debug", "prefs"], env) or "{}").get("OperatorUser") == getpass.getuser()
    except ValueError:
        return False


OPERATOR_HINT = "Needs a one-time setup: sudo tailscale set --operator=$USER"


def set_tailscale(on, env):
    try:
        _run(["tailscale", "up" if on else "down"], env, check=True)
    except ValueError as e:
        raise ValueError(OPERATOR_HINT if "access denied" in str(e).lower() else str(e))


def mirror(env):
    state = _run(["bbkos-mirror", "status"], env).strip()
    return {"state": state, "address": _run(["bbkos-mirror", "address"], env).strip()} if state else None


def status(env):
    return {"wifi": _run(["nmcli", "radio", "wifi"], env).strip() == "enabled", "connections": connections(env),
            "tailscale": tailscale(env), "mirror": mirror(env)}


def check_name(name):
    if not name or len(name) > 200 or any(ord(c) < 32 for c in name) or name.startswith("-"):
        raise ValueError("not a connection name")
    return name


def main(argv, env=None):
    env = dict(os.environ if env is None else env)
    try:
        if argv == ["status"]:
            print(json.dumps(status(env)))
            return 0
        if len(argv) == 2 and argv[0] == "wifi" and argv[1] in ("on", "off"):
            _run(["nmcli", "radio", "wifi", argv[1]], env, check=True)
            return 0
        if len(argv) == 2 and argv[0] == "forget":
            _run(["nmcli", "connection", "delete", "id", check_name(argv[1])], env, check=True)
            return 0
        if len(argv) == 2 and argv[0] == "tailscale" and argv[1] in ("on", "off"):
            set_tailscale(argv[1] == "on", env)
            return 0
        if len(argv) == 3 and argv[0] == "autoconnect" and argv[2] in ("yes", "no"):
            _run(["nmcli", "connection", "modify", "id", check_name(argv[1]), "connection.autoconnect", argv[2]], env, check=True)
            return 0
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    print("usage: bbkos-network status | wifi on|off | forget NAME | autoconnect NAME yes|no | tailscale on|off", file=sys.stderr)
    return 2
