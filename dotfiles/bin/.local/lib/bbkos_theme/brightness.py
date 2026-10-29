"""Per-monitor brightness: the laptop panel through brightnessctl, an external monitor through DDC/CI (ddcutil).

The external monitor's i2c bus comes from sysfs (/sys/class/drm/cardN-<connector>/ddc -> i2c-N), so the slow
`ddcutil detect` is never needed. Both backends use percentages. The backlight's percent is 1 at the lowest step we
write and 100 at the maximum, evenly spaced in perceived brightness (to_percent / to_raw).
"""
import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

TIMEOUT = 15            # one DDC transaction can take several seconds
FLOOR = 2               # lowest raw backlight value we write (0 is off, and the screen should never go black)
EXPONENT = 4            # perceived brightness ~ (raw / max) ** (1 / EXPONENT): the percent scale of the laptop panel
DDC_HINT = "ddcutil is not installed (run scripts/task16-ddcutil.sh)"


class BrightnessError(Exception):
    pass


def bus_for(name, drm_root="/sys/class/drm"):
    """i2c bus number of the connector `name` (HDMI-A-1, DP-1, ...), or None."""
    try:
        entries = list(Path(drm_root).iterdir())
    except OSError:
        return None
    for d in sorted(entries):
        m = re.fullmatch(r"card\d+-(.+)", d.name)
        if not m or m.group(1) != name:
            continue
        try:
            base = os.path.basename(os.readlink(d / "ddc"))
        except OSError:
            continue
        if re.fullmatch(r"i2c-\d+", base):
            return int(base[4:])
    return None


def _tool(env, name):
    return shutil.which(name, path=env.get("PATH", os.defpath))


def _run(exe, args, env):
    try:
        res = subprocess.run([exe, *args], env=env, capture_output=True, text=True,
                             timeout=TIMEOUT, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        raise BrightnessError(f"{os.path.basename(exe)} timed out")
    except (OSError, subprocess.SubprocessError) as e:
        raise BrightnessError(f"{os.path.basename(exe)} failed: {e}")
    if res.returncode != 0:
        for line in (res.stderr or res.stdout or "").splitlines():
            if line.strip():
                raise BrightnessError(line.strip())
        raise BrightnessError(f"{os.path.basename(exe)} exited with code {res.returncode}")
    return res.stdout


def to_percent(raw, mx):
    """The laptop panel's percent: 1 at the floor, 100 at the maximum, evenly spaced on the perceptual curve."""
    lo = (FLOOR / mx) ** (1 / EXPONENT)
    return max(1, min(100, round(1 + 99 * ((raw / mx) ** (1 / EXPONENT) - lo) / (1 - lo))))


def to_raw(percent, mx):
    lo = (FLOOR / mx) ** (1 / EXPONENT)
    raw = round(mx * (lo + (max(1, min(100, percent)) - 1) / 99 * (1 - lo)) ** EXPONENT)
    return max(FLOOR, min(mx, raw))


def key_delta(percent, direction):
    """Percent points one brightness key press changes: 1 at the dark end (up: below 5 %, down: at 5 % or below), else 5."""
    if direction == "up":
        return 1 if percent < 5 else 5
    return -1 if percent <= 5 else -5


def _backlight(env):
    """(brightnessctl path, raw value, maximum) of the laptop backlight."""
    exe = _tool(env, "brightnessctl")
    if not exe:
        raise BrightnessError("brightnessctl is not installed")
    try:
        f = _run(exe, ["-m"], env).strip().split(",")
        raw, mx = int(f[2]), int(f[4])
        if mx <= 0:
            raise ValueError
    except (IndexError, ValueError):
        raise BrightnessError("unexpected brightnessctl output")
    return exe, raw, mx


def kind(name, internal, env):
    """'backlight', 'ddc' or None: what can change this monitor's brightness, decided without touching it."""
    if internal:
        backlight = Path(env.get("BBKOS_BACKLIGHT_DIR") or "/sys/class/backlight")
        try:
            has = any(backlight.iterdir())
        except OSError:
            has = False
        return "backlight" if has and _tool(env, "brightnessctl") else None
    return "ddc" if (_tool(env, "ddcutil")
                     and bus_for(name, env.get("BBKOS_DRM_DIR") or "/sys/class/drm") is not None) else None


def _ddc(name, env):
    exe = _tool(env, "ddcutil")
    if not exe:
        raise BrightnessError(DDC_HINT)
    bus = bus_for(name, env.get("BBKOS_DRM_DIR") or "/sys/class/drm")
    if bus is None:
        raise BrightnessError(f"no DDC bus for {name}")
    return exe, str(bus)


@contextlib.contextmanager
def _ddc_lock(env):
    """One DDC job at a time: overlapping ddcutil runs (key repeat) lose the bus lock after 3 s and print diagnostics
    with exit code 0 instead of a value. Waits for the previous job, up to TIMEOUT."""
    path = Path(env.get("XDG_RUNTIME_DIR") or "/tmp") / "bbkos-ddc.lock"
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        yield
        return
    try:
        deadline = time.monotonic() + TIMEOUT
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise BrightnessError("ddcutil busy")
                time.sleep(0.05)
        yield
    finally:
        os.close(fd)


def _edid_hash(name, env):
    """A short hash of the monitor's EDID on connector `name` ("" when unreadable): tells two monitors on one port apart."""
    root = Path(env.get("BBKOS_DRM_DIR") or "/sys/class/drm")
    try:
        for d in sorted(root.iterdir()):
            m = re.fullmatch(r"card\d+-(.+)", d.name)
            if m and m.group(1) == name:
                return hashlib.sha1((d / "edid").read_bytes()).hexdigest()[:12]
    except OSError:
        pass
    return ""


def _max_cache(env):
    """The remembered VCP 10 maxima, {"<bus>:<edid hash>": max}, in the runtime dir (gone at reboot)."""
    return Path(env.get("XDG_RUNTIME_DIR") or "/tmp") / "bbkos-ddc-max.json"


def _known_max(key, env):
    try:
        v = json.loads(_max_cache(env).read_text()).get(key)
        return v if isinstance(v, int) and v > 0 else None
    except (OSError, ValueError, AttributeError):
        return None


def _remember_max(key, mx, env):
    path = _max_cache(env)
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    if data.get(key) == mx:
        return
    data[key] = mx
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        os.replace(tmp, path)
    except OSError:
        pass                                       # only a speed-up: without it each set reads first


def _ddc_read(exe, bus, env, key=None):
    out = _run(exe, ["--bus", bus, "getvcp", "10", "--brief"], env).split()
    try:
        cur, mx = int(out[3]), int(out[4])
        if mx <= 0:
            raise ValueError
    except (IndexError, ValueError):
        raise BrightnessError("unexpected ddcutil output")
    if key:
        _remember_max(key, mx, env)
    return cur, mx


def get(name, internal, env):
    if internal:
        _, raw, mx = _backlight(env)
        return {"kind": "backlight", "percent": to_percent(raw, mx)}
    exe, bus = _ddc(name, env)
    with _ddc_lock(env):
        cur, mx = _ddc_read(exe, bus, env, f"{bus}:{_edid_hash(name, env)}")
    return {"kind": "ddc", "percent": round(cur * 100 / mx)}


def set(name, internal, percent, env):
    if internal:
        exe, _, mx = _backlight(env)
        _run(exe, ["set", str(to_raw(percent, mx))], env)
        return {"kind": "backlight", "percent": percent}
    exe, bus = _ddc(name, env)
    key = f"{bus}:{_edid_hash(name, env)}"
    with _ddc_lock(env):
        mx = _known_max(key, env)              # the maximum does not change: skip the ~90 ms read once it is known
        if mx is None:
            _, mx = _ddc_read(exe, bus, env, key)
        _run(exe, ["--bus", bus, "setvcp", "10", str(round(percent * mx / 100)), "--noverify"], env)
    return {"kind": "ddc", "percent": percent}


def step(name, internal, delta, env):
    """Change the brightness by `delta` percent points (negative = darker); returns the new state."""
    if internal:
        exe, raw, mx = _backlight(env)
        target = to_raw(to_percent(raw, mx) + delta, mx)
        if delta > 0:
            target = max(target, min(raw + 1, mx))     # a press always moves at least one raw step, also where
        elif delta < 0:                                # the steps are finer than a percent (the dark end)
            target = min(target, max(raw - 1, FLOOR))
        _run(exe, ["set", str(target)], env)
        return {"kind": "backlight", "percent": to_percent(target, mx)}
    exe, bus = _ddc(name, env)
    with _ddc_lock(env):
        cur, mx = _ddc_read(exe, bus, env, f"{bus}:{_edid_hash(name, env)}")
        new = max(0, min(mx, cur + round(delta * mx / 100)))
        _run(exe, ["--bus", bus, "setvcp", "10", str(new), "--noverify"], env)
    return {"kind": "ddc", "percent": round(new * 100 / mx)}
